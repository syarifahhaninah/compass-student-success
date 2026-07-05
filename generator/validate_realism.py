"""Statistical realism check for generated data.

Compares the synthetic institution against published sector benchmarks:
- Retention: sector ~86% overall; First Nations ~75%; disability ~84%;
  low SES a few points below average; a leading equity institution sits a
  couple of points above sector on each (ACSES 2026 update, 2024 data).
- First-year attrition concentrates in the commencing year.
- Fail rates: roughly 8-15% of graded units.

Run after generate.py. Purely diagnostic — prints a calibration table.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
QUALITY = ROOT / "data" / "quality"


def main():
    students = pd.read_csv(RAW / "banner_students.csv", dtype={"student_id": str})
    enrol = pd.read_csv(RAW / "banner_enrolments.csv", dtype={"student_id": str})
    truth = pd.read_csv(QUALITY / "simulation_truth_students.csv",
                        dtype={"student_id": str})
    events = pd.read_csv(QUALITY / "simulation_truth_events.csv",
                         dtype={"student_id": str})

    df = students.merge(truth, on="student_id", how="left", suffixes=("", "_t"))
    df["commencing_year"] = df.commencing_term.str[:4].astype(int)

    enrol["year"] = enrol.term_code.str[:4].astype(int)
    years_present = enrol.groupby("student_id").year.agg(["min", "max"])
    df = df.merge(years_present, left_on="student_id", right_index=True, how="left")

    def retention(sub):
        """Share of commencing students who return the following year
        (completions count as retained). Cohorts with a next year of data only."""
        sub = sub[sub.commencing_year <= 2025]
        returned = (sub["max"] > sub.commencing_year) | (sub.student_status == "completed")
        return returned.mean(), len(sub)

    dom = df[df.citizenship == "Domestic"].copy()
    groups = {
        "All domestic": dom,
        "Non-equity": dom[~(dom.low_ses_true.fillna(False))
                          & (dom.first_nations_flag != "Y")
                          & (dom.disability_flag != "Y")
                          & ~(dom.regional_true.fillna(False))],
        "Low SES": dom[dom.low_ses_true.fillna(False)],
        "First Nations": dom[dom.first_nations_flag == "Y"],
        "Disability": dom[dom.disability_flag == "Y"],
        "Regional/remote": dom[dom.regional_true.fillna(False)],
        "Online": dom[dom["mode"] == "Online"],
        "On-campus": dom[dom["mode"] == "On-campus"],
    }
    print("\n=== Year-1 retention by cohort (commencing 2023-2025) ===")
    for name, sub in groups.items():
        r, n = retention(sub)
        print(f"  {name:<18} {r:6.1%}   (n={n:,})")

    print("\n=== Grade distribution (completed graded units) ===")
    graded = enrol[enrol.grade.isin(["HD", "DI", "CR", "PA", "NN"])]
    print(graded.grade.value_counts(normalize=True).round(3).to_string())
    print(f"  mean mark: {graded.mark.clip(0, 100).mean():.1f}")

    wd = enrol.grade.value_counts()
    print(f"\n  WW (pre-census withdrawal) rows: {wd.get('WW', 0):,}"
          f"  |  WN (post-census): {wd.get('WN', 0):,}"
          f"  |  graded: {len(graded):,}")

    print("\n=== Alerts and outreach (per student-term) ===")
    ev = events.copy()
    print(f"  student-terms simulated: {len(ev):,}")
    print(f"  alerted:   {(ev.first_alert_week >= 0).mean():6.1%}")
    alerted = ev[ev.first_alert_week >= 0]
    print(f"  contacted: {alerted.contacted.mean():6.1%} of alerted")
    print(f"  reached:   {alerted.reached.mean():6.1%} of alerted")
    print(f"  effect:    {alerted.effect_applied.mean():6.1%} of alerted")

    print("\n=== Naive treated-vs-untreated persistence gap (selection-biased!) ===")
    # This intentionally naive comparison should look WRONG (treated students
    # were alerted, i.e. struggling). The ETL's matched comparison must beat it.
    ev24 = ev[ev.term_code.isin(["2024S1", "2024S2", "2025S1"])]
    merged = ev24.merge(df[["student_id", "student_status"]], on="student_id")
    for flag, name in [(True, "contacted"), (False, "not contacted")]:
        sub = merged[(merged.first_alert_week >= 0) & (merged.contacted == flag)]
        disc = (sub.student_status == "discontinued").mean()
        print(f"  alerted & {name:<14} discontinued: {disc:6.1%} (n={len(sub):,})")


if __name__ == "__main__":
    main()
