"""Warehouse validation: integrity checks, headline metrics, and the
data-quality CATCH-RATE score — the pipeline's validation layer graded
against the generator's injected-defect answer key.

Run after run_etl.py:  python etl/validate_output.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WH = ROOT / "data" / "warehouse"
QUALITY = ROOT / "data" / "quality"


def main():
    dim_student = pd.read_csv(WH / "dim_student.csv", dtype={"student_id": str})
    fact_enrol = pd.read_csv(WH / "fact_enrolment.csv", dtype={"student_id": str})
    retention = pd.read_csv(WH / "mart_retention_cohort.csv")
    triage = pd.read_csv(WH / "mart_triage_current.csv")
    nbf = pd.read_csv(WH / "mart_nbf_funding.csv")
    dq = pd.read_csv(QUALITY / "dq_issues.csv")
    injected = pd.read_csv(QUALITY / "injected_defects.csv")

    print("=== Referential integrity ===")
    orphans = ~fact_enrol.student_id.isin(set(dim_student.student_id))
    print(f"  enrolment rows with unknown student: {orphans.sum()}")
    assert orphans.sum() == 0, "orphan enrolments in warehouse!"

    print("\n=== Headline metrics ===")
    r = retention[retention.cohort == "All domestic"]
    for _, row in r.sort_values("commencing_year").iterrows():
        print(f"  retention {int(row.commencing_year)} commencers: {row.retention_rate:.1%}")
    print(f"  triage list size (current term): {len(triage):,}")
    print(triage.priority_tier.value_counts().to_string())
    print(f"  NBF indicative funding (2026 commencers): "
          f"${nbf[nbf.commencing_year == 2026].indicative_funding.sum():,.0f}")

    print("\n=== Data-quality catch rate (pipeline vs injected answer key) ===")
    checks = []

    inj = injected[injected.defect_type == "duplicate_student"]
    caught = dq[dq.rule_id == "R01_duplicate_student"].row_key.astype(str)
    checks.append(("duplicate_student", len(inj),
                   inj.row_key.astype(str).isin(set(caught)).sum()))

    inj = injected[injected.defect_type == "mark_out_of_range"]
    caught = dq[dq.rule_id == "R02_mark_out_of_range"].row_key.astype(str)
    checks.append(("mark_out_of_range", len(inj),
                   inj.row_key.astype(str).isin(set(caught)).sum()))

    # campus variants: handled == resolved by the synonym map (i.e. NOT left
    # unresolved in R03). Unresolved ones are quarantined, which also counts
    # as caught — but resolved is the better outcome, so report both.
    inj = injected[injected.defect_type == "campus_code_variant"]
    unresolved = set(dq[dq.rule_id == "R03_unknown_campus"].row_key.astype(str))
    handled = (~inj.row_key.astype(str).isin(unresolved)).sum()
    checks.append(("campus_code_variant", len(inj), handled))

    inj = injected[injected.defect_type == "missing_equity_flag"]
    caught = dq[dq.rule_id == "R04_missing_equity_flag"].row_key.astype(str)
    checks.append(("missing_equity_flag", len(inj),
                   inj.row_key.astype(str).isin(set(caught)).sum()))

    # names and dates: handled = silently repaired by staging, verify state
    students_wh = dim_student
    inj = injected[injected.defect_type == "name_whitespace_case"]
    bad_names = students_wh.first_name.str.startswith(" ").sum() \
        + students_wh.first_name.str.endswith(" ").sum()
    checks.append(("name_whitespace_case", len(inj), len(inj) if bad_names == 0 else 0))

    inj = injected[injected.defect_type == "dob_format_dmy"]
    unparsed = students_wh.dob.isna().sum()
    checks.append(("dob_format_dmy", len(inj), len(inj) if unparsed == 0 else 0))

    total_inj = total_caught = 0
    for name, n_inj, n_caught in checks:
        total_inj += n_inj
        total_caught += n_caught
        print(f"  {name:<24} injected {n_inj:>5,}   handled {n_caught:>5,}   "
              f"({(n_caught / n_inj if n_inj else 1):6.1%})")
    print(f"  {'TOTAL':<24} injected {total_inj:>5,}   handled {total_caught:>5,}   "
          f"({total_caught / total_inj:6.1%})")


if __name__ == "__main__":
    main()
