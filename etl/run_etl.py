"""Compass ETL orchestrator.

Runs the SQL pipeline (staging -> validation -> dimensions -> facts -> marts)
in DuckDB and exports the warehouse layer as CSVs for the Power BI model.

Usage:  python etl/run_etl.py
"""

import os
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "etl" / "sql"
WAREHOUSE = ROOT / "data" / "warehouse"
QUALITY = ROOT / "data" / "quality"

EXPORT_TABLES = [
    "dim_student", "dim_term", "dim_campus", "dim_program", "dim_unit",
    "dim_advisor", "fact_enrolment", "fact_engagement_week", "fact_case",
    "fact_alert", "mart_executive", "mart_retention_cohort",
    "mart_nbf_funding", "mart_seheef_activity", "mart_triage_current",
    "mart_effectiveness_input", "mart_dq_summary", "mart_engagement_trend",
]
QUALITY_TABLES = ["dq_issues", "rej_enrolments"]


def main():
    t0 = time.time()
    os.chdir(ROOT)  # SQL scripts use repo-relative paths
    WAREHOUSE.mkdir(parents=True, exist_ok=True)
    QUALITY.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    for script in sorted(SQL_DIR.glob("*.sql")):
        print(f"Running {script.name} ...")
        con.execute(script.read_text(encoding="utf-8"))

    print("Exporting warehouse layer ...")
    for table in EXPORT_TABLES:
        n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        con.execute(
            f"COPY (SELECT * FROM {table}) TO '{(WAREHOUSE / table).as_posix()}.csv' (HEADER)"
        )
        print(f"  {table:<28} {n:>9,} rows")
    for table in QUALITY_TABLES:
        con.execute(
            f"COPY (SELECT * FROM {table}) TO '{(QUALITY / table).as_posix()}.csv' (HEADER)"
        )

    print(f"Done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
