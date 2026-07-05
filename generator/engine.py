"""Term-by-term simulation engine.

Simulates each teaching week: engagement (latent AR(1) with disengagement
cliffs), observable LMS behaviour, assessment submissions, alert rules,
advisor outreach with a *known injected intervention effect* (so the
matched-comparison evaluation can later be validated against ground truth),
withdrawals, grades, persistence and completion.
"""

from datetime import timedelta

import numpy as np
import pandas as pd

import config as cfg


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


ASSESSMENT_WEEKS = {3, 5, 7, 9, 11}
CASE_TYPE_BY_REASON = {
    "INACTIVITY_14D": "Early intervention outreach",
    "NON_SUBMISSION": "Early intervention outreach",
    "LOW_ONTIME_RATE": "Academic recovery support",
}
SELF_REFERRAL_TYPES = [
    "Financial hardship support", "Wellbeing referral",
    "Disability support plan", "Peer mentoring referral", "Progression advising",
]


class Simulator:
    def __init__(self, students, truth, catalogue, rng):
        self.rng = rng
        self.students = students.reset_index(drop=True)
        n = len(students)
        term_index = {t["code"]: i for i, t in enumerate(cfg.TERMS)}
        self.commence_idx = students.commencing_term.map(term_index).to_numpy()
        self.ability = truth.ability.to_numpy()
        self.support_static = truth.support_static.to_numpy()
        self.online = (students["mode"] == "Online").to_numpy()
        self.part_time = (students.attendance_type == "Part-time").to_numpy()
        self.intl = (students.citizenship == "International").to_numpy()
        self.campus = students.campus_code.to_numpy()
        self.program = students.program_code.to_numpy()
        self.sid = students.student_id.to_numpy()

        self.status = np.full(n, "pre", dtype=object)      # pre|active|discontinued|completed
        self.status_term = np.full(n, "", dtype=object)
        self.terms_done = np.zeros(n, dtype=int)
        self.cum_passed = np.zeros(n, dtype=int)

        self.unit_pools = {
            (p, lv): g.unit_code.to_numpy()
            for (p, lv), g in catalogue.groupby(["program_code", "year_level"])
        }
        self.advisors_by_campus = {}
        for aid, _, camps in cfg.ADVISORS:
            for c in camps:
                self.advisors_by_campus.setdefault(c, []).append(aid)

        self.enrolments, self.weekly, self.alerts, self.cases, self.truth_events = [], [], [], [], []
        self._alert_seq = 0
        self._case_seq = 0

    # ------------------------------------------------------------------ ids
    def _alert_id(self):
        self._alert_seq += 1
        return f"AL{self._alert_seq:07d}"

    def _case_id(self):
        self._case_seq += 1
        return f"CS{self._case_seq:07d}"

    # ---------------------------------------------------------------- units
    def _assign_units(self, idx, units_n):
        year_level = np.clip(self.terms_done[idx] // 2 + 1, 1, 3)
        chosen = np.empty((len(idx), cfg.FT_UNITS), dtype=object)
        keys = pd.Series(list(zip(self.program[idx], year_level)))
        for key, grp in keys.groupby(keys):
            pool = self.unit_pools[key]
            rows = grp.index.to_numpy()
            order = np.argsort(self.rng.random((len(rows), len(pool))), axis=1)
            picks = pool[order[:, :cfg.FT_UNITS]]
            chosen[rows] = picks
        return chosen, year_level  # callers mask columns beyond units_n

    # ----------------------------------------------------------------- term
    def run(self):
        for t_idx, term in enumerate(cfg.TERMS):
            self._run_term(t_idx, term)

    def _run_term(self, t_idx, term):
        rng = self.rng
        commencing = (self.commence_idx == t_idx) & (self.status == "pre")
        self.status[commencing] = "active"
        idx = np.where(self.status == "active")[0]
        if len(idx) == 0:
            return
        m = len(idx)
        is_current = term["code"] == cfg.CURRENT_TERM
        weeks_eff = cfg.AS_OF_WEEK if is_current else term["weeks"]
        start = term["start"]

        first_year = (t_idx - self.commence_idx[idx]) < 2
        need = self.support_static[idx] + cfg.SUPPORT_NEED_WEIGHTS["first_year"] * first_year
        ability = self.ability[idx]
        units_n = np.where(self.part_time[idx], cfg.PT_UNITS, cfg.FT_UNITS)
        unit_matrix, year_level = self._assign_units(idx, units_n)

        e_base = cfg.ENG_INTERCEPT + cfg.ENG_ABILITY * ability \
            - cfg.ENG_NEED * need + rng.normal(0, cfg.ENG_NOISE_SD, m)
        p_cliff = sigmoid(cfg.CLIFF_BASE + cfg.CLIFF_NEED * need - 0.30 * ability)
        cliff_week = np.where(rng.random(m) < p_cliff, rng.integers(2, 11, m), 99)

        s = np.zeros(m)
        uplift = np.zeros(m)
        in_term = np.ones(m, dtype=bool)
        withdrawn_pre = np.zeros(m, dtype=bool)
        withdrawn_post = np.zeros(m, dtype=bool)
        cum_due = np.zeros(m, dtype=int)
        cum_missed = np.zeros(m, dtype=int)
        cum_ontime = np.zeros(m, dtype=int)
        logins_prev = np.full(m, 5)
        flagged = {r: np.zeros(m, dtype=bool) for r in CASE_TYPE_BY_REASON}
        first_alert_week = np.full(m, -1)
        first_alert_id = np.full(m, "", dtype=object)
        first_reason = np.full(m, "", dtype=object)
        contact_week = np.full(m, -1)
        contacted = np.zeros(m, dtype=bool)
        reached = np.zeros(m, dtype=bool)
        effected = np.zeros(m, dtype=bool)
        sumE = np.zeros(m)
        cntE = np.zeros(m, dtype=int)
        E_last = np.zeros(m)

        weekly_frames = []
        for w in range(1, weeks_eff + 1):
            s = cfg.AR_RHO * s + rng.normal(0, cfg.AR_SD, m)
            E = np.clip(
                e_base + s - cfg.CLIFF_DROP * (w >= cliff_week) + uplift, -4, 4
            )
            act = in_term
            sumE += np.where(act, E, 0.0)
            cntE += act
            E_last = np.where(act, E, E_last)

            logins = np.minimum(rng.poisson(np.exp(1.30 + 0.55 * E)), 45)
            logins = np.where(act, logins, 0)
            page_views = np.where(act, (logins * rng.uniform(3, 9, m)).astype(int), 0)

            if w in ASSESSMENT_WEEKS:
                items_due = np.where(act, rng.binomial(units_n, 0.45), 0)
            else:
                items_due = np.zeros(m, dtype=int)
            p_on = sigmoid(cfg.ONTIME_INTERCEPT + 1.15 * E)
            sub_on = rng.binomial(items_due, p_on)
            late = rng.binomial(items_due - sub_on, 0.45)
            missed = items_due - sub_on - late
            cum_due += items_due
            cum_ontime += sub_on
            cum_missed += missed

            weekly_frames.append(pd.DataFrame({
                "student_id": self.sid[idx][act],
                "term_code": term["code"],
                "week_number": w,
                "week_start": start + timedelta(days=7 * (w - 1)),
                "logins": logins[act],
                "page_views": page_views[act],
                "items_due": items_due[act],
                "submitted_on_time": sub_on[act],
                "submitted_late": late[act],
                "missed": missed[act],
            }))

            # ----- alert rules (leading indicators, evaluated weekly) -----
            if cfg.ALERT_START_WEEK <= w <= min(cfg.ALERT_END_WEEK, weeks_eff):
                rolling2 = logins + logins_prev
                new = {
                    "INACTIVITY_14D": act & (rolling2 <= cfg.INACTIVITY_LOGINS_2WK)
                    & ~flagged["INACTIVITY_14D"],
                    "NON_SUBMISSION": act & (cum_missed >= cfg.NON_SUBMISSION_MISSED)
                    & ~flagged["NON_SUBMISSION"],
                    "LOW_ONTIME_RATE": act & (w >= 6) & (cum_due >= 3)
                    & (cum_ontime < cfg.ONTIME_RATE_FLOOR * cum_due)
                    & ~flagged["LOW_ONTIME_RATE"],
                }
                for reason, mask in new.items():
                    flagged[reason] |= mask
                    for j in np.where(mask)[0]:
                        aid = self._alert_id()
                        self.alerts.append({
                            "alert_id": aid,
                            "student_id": self.sid[idx][j],
                            "term_code": term["code"],
                            "week_number": w,
                            "raised_date": start + timedelta(days=7 * (w - 1) + 2),
                            "reason_code": reason,
                        })
                        if first_alert_week[j] < 0:
                            first_alert_week[j] = w
                            first_alert_id[j] = aid
                            first_reason[j] = reason
                # capacity-constrained outreach, triaged worst-first on
                # OBSERVABLE severity: simultaneous reasons + current inactivity.
                # Confounds naive comparisons, but matchable from the warehouse.
                newly = (first_alert_week == w)
                reasons_now = sum(mk.astype(int) for mk in new.values())
                low_login = (rolling2 <= cfg.INACTIVITY_LOGINS_2WK)
                p_contact = np.clip(
                    cfg.P_CONTACT_BASE
                    + cfg.P_CONTACT_PER_REASON * np.maximum(reasons_now - 1, 0)
                    + cfg.P_CONTACT_LOWLOGIN * low_login,
                    cfg.P_CONTACT_MIN, cfg.P_CONTACT_MAX,
                )
                pick = newly & (rng.random(m) < p_contact)
                contact_week[pick] = w + 1
                contacted |= pick

            # ----- outreach resolution (injected ground-truth effect) -----
            due_now = contacted & (contact_week == w) & in_term
            if due_now.any():
                r = rng.random(m)
                got_through = due_now & (r < cfg.P_REACHED)
                voicemail = due_now & ~got_through & (r < cfg.P_REACHED + cfg.P_VOICEMAIL)
                reached |= got_through
                eff = got_through & (rng.random(m) < cfg.P_EFFECT_IF_REACHED)
                effected |= eff
                uplift[eff] += cfg.EFFECT_ENGAGE_UPLIFT
                for j in np.where(due_now)[0]:
                    if got_through[j] and effected[j]:
                        outcome, status = "Reached - support plan agreed", "In progress"
                    elif got_through[j]:
                        outcome, status = "Reached - declined support", "Closed"
                    elif voicemail[j]:
                        outcome, status = "Voicemail left", "Closed"
                    else:
                        outcome, status = "No response after 3 attempts", "Closed"
                    opened = start + timedelta(days=7 * (w - 1) + int(rng.integers(0, 4)))
                    if is_current and w >= weeks_eff - 2:
                        status = "Open"
                    closed = "" if status != "Closed" else str(
                        opened + timedelta(days=int(rng.integers(3, 21))))
                    ctype = CASE_TYPE_BY_REASON[first_reason[j]]
                    seheef = cfg.SEHEEF_BY_CASE_TYPE[ctype]
                    self.cases.append({
                        "case_id": self._case_id(),
                        "student_id": self.sid[idx][j],
                        "term_code": term["code"],
                        "opened_date": opened,
                        "source": "Early alert",
                        "case_type": ctype,
                        "seheef_activity": seheef[0],
                        "seheef_life_stage": seheef[1],
                        "advisor_id": rng.choice(
                            self.advisors_by_campus[self.campus[idx][j]]),
                        "contact_channel": rng.choice(
                            ["Phone", "Email", "SMS"], p=[0.6, 0.3, 0.1]),
                        "contact_outcome": outcome,
                        "status": status,
                        "closed_date": closed,
                        "linked_alert_id": first_alert_id[j],
                    })

            # ----- withdrawals -----
            meanE = np.divide(sumE, np.maximum(cntE, 1))
            if w == cfg.CENSUS_WEEK:
                cand = in_term & (meanE < cfg.WITHDRAW_PRE_MEANE)
                out = cand & (rng.random(m) < cfg.WITHDRAW_PRE_P)
                withdrawn_pre |= out
                in_term &= ~out
            if w == 9 and weeks_eff >= 9:
                cand = in_term & (E < cfg.WITHDRAW_POST_E)
                out = cand & (rng.random(m) < cfg.WITHDRAW_POST_P)
                withdrawn_post |= out
                in_term &= ~out

            logins_prev = logins

        self.weekly.append(pd.concat(weekly_frames, ignore_index=True))
        self._self_referrals(idx, term, weeks_eff, start)
        self._finish_term(idx, term, is_current, unit_matrix, units_n, year_level,
                          sumE, cntE, E_last, first_year, need, withdrawn_pre,
                          withdrawn_post, effected, start)
        self.truth_events.append(pd.DataFrame({
            "student_id": self.sid[idx],
            "term_code": term["code"],
            "first_alert_week": first_alert_week,
            "contacted": contacted,
            "reached": reached,
            "effect_applied": effected,
        }))

    # ------------------------------------------------------ self-referrals
    def _self_referrals(self, idx, term, weeks_eff, start):
        rng = self.rng
        pick = rng.random(len(idx)) < cfg.P_SELF_REFERRAL
        for j in np.where(pick)[0]:
            ctype = rng.choice(SELF_REFERRAL_TYPES)
            seheef = cfg.SEHEEF_BY_CASE_TYPE[ctype]
            opened = start + timedelta(days=int(rng.integers(0, 7 * weeks_eff)))
            status = rng.choice(["Closed", "In progress"], p=[0.85, 0.15])
            self.cases.append({
                "case_id": self._case_id(),
                "student_id": self.sid[idx][j],
                "term_code": term["code"],
                "opened_date": opened,
                "source": rng.choice(["Self-referral", "Staff referral"], p=[0.7, 0.3]),
                "case_type": ctype,
                "seheef_activity": seheef[0],
                "seheef_life_stage": seheef[1],
                "advisor_id": rng.choice(self.advisors_by_campus[self.campus[idx][j]]),
                "contact_channel": rng.choice(["Phone", "Email", "In person"]),
                "contact_outcome": "Service provided",
                "status": status,
                "closed_date": "" if status != "Closed" else str(
                    opened + timedelta(days=int(rng.integers(5, 30)))),
                "linked_alert_id": "",
            })

    # ------------------------------------------------------------- wrap-up
    def _finish_term(self, idx, term, is_current, unit_matrix, units_n, year_level,
                     sumE, cntE, E_last, first_year, need, withdrawn_pre,
                     withdrawn_post, effected, start):
        rng = self.rng
        m = len(idx)
        meanE = sumE / np.maximum(cntE, 1)
        census = start + timedelta(days=7 * cfg.CENSUS_WEEK - 3)

        marks = rng.normal(
            cfg.MARK_INTERCEPT + cfg.MARK_ENGAGE * meanE[:, None]
            + cfg.MARK_ABILITY * self.ability[idx][:, None],
            cfg.MARK_SD, size=(m, cfg.FT_UNITS),
        ).round().clip(5, 98)

        rows = []
        passed_units = np.zeros(m, dtype=int)
        for j in range(m):
            for u in range(units_n[j]):
                unit = unit_matrix[j, u]
                if withdrawn_pre[j]:
                    stat, grade, mark, eftsl = "Withdrawn pre-census", "WW", None, 0.0
                elif withdrawn_post[j]:
                    stat, grade, mark, eftsl = "Withdrawn post-census", "WN", None, cfg.UNIT_EFTSL
                elif is_current:
                    stat, grade, mark, eftsl = "In progress", "IP", None, cfg.UNIT_EFTSL
                else:
                    mk = marks[j, u]
                    grade = ("HD" if mk >= 85 else "DI" if mk >= 75 else
                             "CR" if mk >= 65 else "PA" if mk >= 50 else "NN")
                    stat, mark, eftsl = "Completed", mk, cfg.UNIT_EFTSL
                    if mk >= 50:
                        passed_units[j] += 1
                rows.append((
                    self.sid[idx][j], unit, term["code"], self.campus[idx][j],
                    stat, grade, mark, eftsl, str(census),
                ))
        self.enrolments.append(pd.DataFrame(rows, columns=[
            "student_id", "unit_code", "term_code", "campus_code",
            "enrolment_status", "grade", "mark", "eftsl", "census_date",
        ]))

        if is_current:
            # current term: withdrawn-pre-census students discontinue; the rest stay
            gone = withdrawn_pre
            self.status[idx[gone]] = "discontinued"
            self.status_term[idx[gone]] = term["code"]
            return

        self.cum_passed[idx] += passed_units
        pass_share = np.where(
            withdrawn_pre | withdrawn_post, 0.0,
            passed_units / np.maximum(units_n, 1),
        )
        logit = (
            cfg.RET_INTERCEPT
            + cfg.RET_ENGAGE * E_last
            + cfg.RET_PASS * (pass_share - 0.7) * 5
            + cfg.RET_FIRST_YEAR * first_year
            + cfg.RET_NEED * need
            + cfg.RET_ONLINE * self.online[idx]
            + cfg.RET_INTL * self.intl[idx]
            + cfg.EFFECT_RETENTION_LOGIT * effected
            - 2.2 * withdrawn_pre - 1.6 * withdrawn_post
        )
        stay = rng.random(m) < sigmoid(logit)
        self.terms_done[idx] += 1

        completing = (
            stay & (self.terms_done[idx] >= 6) & ~self.part_time[idx]
            & (self.cum_passed[idx] >= 20)
        )
        self.status[idx[completing]] = "completed"
        self.status_term[idx[completing]] = term["code"]
        leaving = ~stay & ~completing
        self.status[idx[leaving]] = "discontinued"
        self.status_term[idx[leaving]] = term["code"]

    # -------------------------------------------------------------- output
    def outputs(self):
        students = self.students.copy()
        students["student_status"] = self.status
        students["status_term"] = self.status_term
        return {
            "banner_students": students,
            "banner_enrolments": pd.concat(self.enrolments, ignore_index=True),
            "canvas_activity": pd.concat(self.weekly, ignore_index=True),
            "crm_cases": pd.DataFrame(self.cases),
            "alerts_history": pd.DataFrame(self.alerts),
            "simulation_truth_events": pd.concat(self.truth_events, ignore_index=True),
        }
