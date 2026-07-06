"""Fairness audit: does the alert-and-outreach system treat equity cohorts
equitably?

The ethics note commits to auditing this in the open. The test logic:

  1. ALERT RATES may legitimately differ across cohorts — alerts track
     behaviour (inactivity, non-submission), and if a cohort genuinely
     disengages more, its alert rate will be higher. A gap here is a signal
     about need, not (by itself) bias — because demographics are never inputs
     to the alert rules.
  2. TREATMENT GIVEN AN ALERT must NOT differ by cohort. Advisors triage on
     observable severity only, so the contact rate among alerted students
     should be statistically indistinguishable across cohorts. A gap here
     WOULD be bias — students with the same behaviour receiving different
     care because of who they are.

Run after run_etl.py:  python etl/fairness_audit.py
Writes data/warehouse/mart_fairness_audit.csv
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WH = ROOT / "data" / "warehouse"


def main():
    students = pd.read_csv(WH / "dim_student.csv", dtype={"student_id": str})
    enrol = pd.read_csv(WH / "fact_enrolment.csv", dtype={"student_id": str})
    eff = pd.read_csv(WH / "mart_effectiveness_input.csv", dtype={"student_id": str})
    terms = pd.read_csv(WH / "dim_term.csv")

    past_terms = set(terms.loc[~terms.is_current, "term_code"])
    dom = students[students.citizenship == "Domestic"]

    # all past student-terms (the alert-rate denominator)
    st = (enrol[enrol.term_code.isin(past_terms)]
          .loc[:, ["student_id", "term_code"]].drop_duplicates())
    st = st.merge(dom, on="student_id", how="inner")

    # alerted student-terms with contact + next-term outcome
    al = eff.merge(dom[["student_id"]], on="student_id", how="inner")

    cohorts = {
        "Non-equity": (dom.low_ses == "No") & (dom.first_nations == "No")
                      & (dom.disability == "No") & (dom.regional_remote == "No"),
        "First Nations": dom.first_nations == "Yes",
        "Low SES": dom.low_ses == "Yes",
        "Disability": dom.disability == "Yes",
        "Regional/remote": dom.regional_remote == "Yes",
        "Online": dom["mode"] == "Online",
        "All domestic": pd.Series(True, index=dom.index),
    }

    rows = []
    for name, mask in cohorts.items():
        ids = set(dom.loc[mask, "student_id"])
        st_c = st[st.student_id.isin(ids)]
        al_c = al[al.student_id.isin(ids)]
        contacted = al_c[al_c.contacted == 1]
        uncontacted = al_c[al_c.contacted == 0]
        rows.append({
            "cohort": name,
            "student_terms": len(st_c),
            "alert_rate": round(len(al_c) / max(len(st_c), 1), 4),
            "contact_rate_given_alert": round(al_c.contacted.mean(), 4) if len(al_c) else None,
            "retained_next_term_contacted": round(contacted.retained_next_term.mean(), 4) if len(contacted) else None,
            "retained_next_term_uncontacted": round(uncontacted.retained_next_term.mean(), 4) if len(uncontacted) else None,
            "alerted_n": len(al_c),
        })
    out = pd.DataFrame(rows)

    base = out.loc[out.cohort == "Non-equity"].iloc[0]
    out["alert_rate_ratio_vs_nonequity"] = (out.alert_rate / base.alert_rate).round(2)
    out["contact_rate_gap_pp_vs_nonequity"] = (
        (out.contact_rate_given_alert - base.contact_rate_given_alert) * 100
    ).round(1)

    out.to_csv(WH / "mart_fairness_audit.csv", index=False)

    print("=== Fairness audit: alerting and outreach by equity cohort ===\n")
    print(out.to_string(index=False))
    print(
        "\nReading guide:\n"
        "  - alert_rate differences reflect behavioural need (demographics are\n"
        "    never alert inputs); higher rates for equity cohorts mirror the\n"
        "    real engagement gaps the system exists to catch.\n"
        "  - contact_rate_given_alert is the bias test: it should be flat\n"
        "    across cohorts. Gaps beyond ~2-3pp warrant investigation."
    )
    worst = out.loc[out.cohort != "All domestic", "contact_rate_gap_pp_vs_nonequity"].abs().max()
    verdict = "PASS" if worst <= 3.0 else "REVIEW REQUIRED"
    print(f"\n  Max |contact-rate gap| vs non-equity: {worst:.1f}pp -> {verdict}")


if __name__ == "__main__":
    main()
