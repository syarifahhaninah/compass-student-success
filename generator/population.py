"""Population builders: postcode reference, students, unit catalogue, advisors.

Banner-shaped conventions: students carry a postcode plus the flags Banner
actually stores (First Nations, disability, NESB). Low-SES and regional status
are NOT stored on the student record — the ETL derives them from the postcode
reference, mirroring how NBF cohorts are derived from ABS IEO quartiles and
remoteness on first recorded address.
"""

import numpy as np
import pandas as pd

import config as cfg


def make_postcode_lookup(rng: np.random.Generator) -> pd.DataFrame:
    states = sorted({c[2] for c in cfg.CAMPUSES})
    rows = []
    base = {"NSW": 2100, "VIC": 3100, "QLD": 4100, "ACT": 2600}
    for state in states:
        for i in range(cfg.N_POSTCODES_PER_STATE):
            rows.append({
                "postcode": str(base.get(state, 5000) + i * 7),
                "state": state,
                "ses_quartile": int(rng.integers(1, 5)),
                "remoteness": rng.choice(
                    ["Metropolitan", "Regional", "Remote"], p=[0.62, 0.30, 0.08]
                ),
            })
    return pd.DataFrame(rows)


def _pick_postcodes(rng, lookup, states, want_low_ses, want_regional):
    """Postcode assignment honouring SES quartile and remoteness, via
    precomputed pools so assignment is O(n) rather than a filter per student."""
    pools = {}
    for state in lookup.state.unique():
        pool = lookup[lookup.state == state]
        for reg in (True, False):
            sub = pool[pool.remoteness.isin(["Regional", "Remote"])] if reg \
                else pool[pool.remoteness == "Metropolitan"]
            if len(sub) == 0:
                sub = pool
            for low in (True, False):
                cand = sub[sub.ses_quartile <= 2] if low else sub[sub.ses_quartile >= 2]
                if len(cand) == 0:
                    cand = sub
                pools[(state, reg, low)] = cand.postcode.to_numpy()
    n = len(states)
    out = np.empty(n, dtype=object)
    for i in range(n):
        cand = pools[(states[i], bool(want_regional[i]), bool(want_low_ses[i]))]
        out[i] = cand[int(rng.integers(0, len(cand)))]
    return out


def make_students(rng: np.random.Generator, lookup: pd.DataFrame):
    """Returns (students_df, truth_df). truth_df holds latent variables used by
    the simulation engine and the validation script; it is never loaded into
    the warehouse."""
    term_codes = [t["code"] for t in cfg.TERMS]
    rows_n = sum(v["total"] for v in cfg.INTAKE.values())
    rng_ids = 20000000 + np.arange(rows_n)

    commencing, online, cohort_year = [], [], []
    for year, spec in cfg.INTAKE.items():
        n = spec["total"]
        n_s2 = int(n * spec["s2_share"])
        commencing += [f"{year}S1"] * (n - n_s2) + [f"{year}S2"] * n_s2
        online += list(rng.random(n) < spec["online_share"])
        cohort_year += [year] * n
    commencing = np.array(commencing)
    online = np.array(online)
    cohort_year = np.array(cohort_year)
    n = len(commencing)

    campus_codes = np.array([c[0] for c in cfg.CAMPUSES])
    campus_w = np.array([c[3] for c in cfg.CAMPUSES])
    campus = rng.choice(campus_codes, size=n, p=campus_w / campus_w.sum())
    campus[online] = cfg.ONLINE_CAMPUS[0]
    campus_state = {c[0]: c[2] for c in cfg.CAMPUSES}
    campus_state[cfg.ONLINE_CAMPUS[0]] = None
    state = np.array([
        campus_state[c] or rng.choice(["NSW", "VIC", "QLD", "ACT"], p=[0.35, 0.3, 0.25, 0.1])
        for c in campus
    ])

    prog_codes = np.array([p[0] for p in cfg.PROGRAMS])
    prog_w = np.array([p[2] for p in cfg.PROGRAMS])
    program = rng.choice(prog_codes, size=n, p=prog_w / prog_w.sum())

    intl = rng.random(n) < cfg.P_INTERNATIONAL
    gender = rng.choice(
        ["F", "M", "X"], size=n,
        p=[cfg.P_FEMALE, 1 - cfg.P_FEMALE - cfg.P_GENDER_X, cfg.P_GENDER_X],
    )

    # Age: online cohort skews mature
    age_groups = np.array(list(cfg.AGE_MIX.keys()))
    age_p = np.array(list(cfg.AGE_MIX.values()))
    age = rng.choice(age_groups, size=n, p=age_p)
    mature_flip = online & (rng.random(n) < 0.45)
    age[mature_flip] = "25+"

    part_time = np.where(
        online,
        rng.random(n) < cfg.P_PART_TIME_ONLINE,
        rng.random(n) < cfg.P_PART_TIME,
    )

    # Equity flags (domestic only)
    dom = ~intl
    first_nations = dom & (rng.random(n) < cfg.P_FIRST_NATIONS)
    disability = dom & (rng.random(n) < cfg.P_DISABILITY)
    nesb = dom & (rng.random(n) < cfg.P_NESB)

    p_regional = np.full(n, cfg.P_REGIONAL_BASE)
    p_regional[campus == "BAL"] = 0.34
    p_regional[campus == "CAN"] = 0.18
    p_regional[online] = 0.22
    p_regional[first_nations] += 0.15
    regional = dom & (rng.random(n) < p_regional)

    p_low_ses = np.full(n, cfg.P_LOW_SES_BASE)
    p_low_ses[regional] += 0.10
    p_low_ses[first_nations] += 0.18
    p_low_ses[campus == "BLK"] += 0.12
    low_ses = dom & (rng.random(n) < p_low_ses)

    p_fif = np.full(n, cfg.P_FIRST_IN_FAMILY)
    p_fif[low_ses] += 0.12
    first_in_family = dom & (rng.random(n) < p_fif)

    # Admission basis and ATAR
    school_leaver = age == "<=19"
    atar = np.full(n, np.nan)
    atar[school_leaver] = np.clip(rng.normal(74, 12, school_leaver.sum()), 42, 99.5)
    basis = np.where(school_leaver, "ATAR", rng.choice(
        ["VET pathway", "Mature age", "Prior higher education", "Enabling program"],
        size=n))

    # Latent ability and static support-need
    z_atar = np.zeros(n)
    has_atar = ~np.isnan(atar)
    z_atar[has_atar] = (atar[has_atar] - 74) / 12
    ability = 0.5 * z_atar + rng.normal(0, 0.8, n)

    w = cfg.SUPPORT_NEED_WEIGHTS
    support_static = (
        w["low_ses"] * low_ses + w["first_nations"] * first_nations
        + w["disability"] * disability + w["regional"] * regional
        + w["nesb"] * nesb + w["first_in_family"] * first_in_family
        + w["part_time"] * part_time + w["online"] * online
    ).astype(float)

    # Identity
    first = rng.choice(np.array(cfg.FIRST_NAMES), size=n)
    last = rng.choice(np.array(cfg.LAST_NAMES), size=n)
    birth_year = np.select(
        [age == "<=19", age == "20-24"],
        [cohort_year - 18 - rng.integers(0, 2, n), cohort_year - 22 - rng.integers(0, 3, n)],
        default=cohort_year - 28 - rng.integers(0, 15, n),
    )
    dob = [
        f"{by}-{rng.integers(1, 13):02d}-{rng.integers(1, 29):02d}"
        for by in birth_year
    ]

    postcode = _pick_postcodes(rng, lookup, state, low_ses, regional)

    students = pd.DataFrame({
        "student_id": rng_ids.astype(str),
        "first_name": first,
        "last_name": last,
        "dob": dob,
        "gender": gender,
        "citizenship": np.where(intl, "International", "Domestic"),
        "postcode": postcode,
        "state": state,
        "campus_code": campus,
        "program_code": program,
        "commencing_term": commencing,
        "attendance_type": np.where(part_time, "Part-time", "Full-time"),
        "mode": np.where(online, "Online", "On-campus"),
        "age_group": age,
        "basis_of_admission": basis,
        "atar": np.round(atar, 1),
        "first_nations_flag": np.where(first_nations, "Y", "N"),
        "disability_flag": np.where(disability, "Y", "N"),
        "nesb_flag": np.where(nesb, "Y", "N"),
    })
    # International students keep flags 'N'; TCSI equity reporting is domestic-scoped.

    truth = pd.DataFrame({
        "student_id": students.student_id,
        "ability": ability,
        "support_static": support_static,
        "low_ses_true": low_ses,
        "regional_true": regional,
        "commencing_term": commencing,
    })
    assert set(commencing) <= set(term_codes)
    return students, truth


def make_unit_catalogue(rng: np.random.Generator) -> pd.DataFrame:
    themes = [
        "Foundations", "Principles", "Contexts", "Practice", "Methods",
        "Applications", "Theory", "Professional Studies",
    ]
    rows = []
    for code, name, _ in cfg.PROGRAMS:
        field = name.replace("Bachelor of ", "")
        stem = code[1:5]
        for level in (1, 2, 3):
            for i in range(cfg.UNITS_PER_LEVEL):
                rows.append({
                    "unit_code": f"{stem}{level}{i + 10}",
                    "unit_name": f"{themes[i % len(themes)]} of {field} {level}{chr(65 + i)}",
                    "program_code": code,
                    "year_level": level,
                    "eftsl": cfg.UNIT_EFTSL,
                })
    return pd.DataFrame(rows)


def make_advisors_df() -> pd.DataFrame:
    return pd.DataFrame(
        [{"advisor_id": a, "advisor_name": n, "campuses": "|".join(c)}
         for a, n, c in cfg.ADVISORS]
    )
