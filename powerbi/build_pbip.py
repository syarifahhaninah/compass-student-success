"""Generate the Compass Power BI project (PBIP) — semantic model as code.

Emits powerbi/pbip/: a Power BI Desktop-openable project whose semantic model
(model.bim, Tabular Object Model JSON) defines every warehouse table with
typed columns and M source queries, all star-schema relationships, the
measure library, and demo RLS roles. Report pages are created empty (named
per the page guide) — visuals are assembled interactively in Desktop.

Format note: Desktop 2.155 (Store) expects `model.bim` inside a PBIP semantic
model folder; the TMDL folder format required a different project flavour, so
this generator emits the TOM JSON form Desktop asked for.

Usage:  python powerbi/build_pbip.py
Then :  open powerbi/pbip/compass.pbip in Power BI Desktop and Refresh.
"""

import json
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "powerbi" / "pbip"
DATA_FOLDER = str(ROOT / "data" / "warehouse")

S, I, D, DT, B = "string", "int64", "double", "dateTime", "boolean"
M_TYPE = {S: "type text", I: "Int64.Type", D: "type number",
          DT: "type date", B: "type logical"}

TABLES = {
    "dim_student": [
        ("student_id", S), ("first_name", S), ("last_name", S),
        ("student_name", S), ("dob", DT), ("gender", S), ("citizenship", S),
        ("postcode", S), ("state", S), ("home_campus_code", S),
        ("program_code", S), ("commencing_term", S), ("commencing_year", I),
        ("attendance_type", S), ("mode", S), ("age_group", S),
        ("basis_of_admission", S), ("atar", D), ("first_nations", S),
        ("disability", S), ("nesb", S), ("ses_quartile", I), ("remoteness", S),
        ("low_ses", S), ("regional_remote", S), ("nbf_equity_cohort", S),
        ("nbf_category", S), ("student_status", S), ("status_term", S),
    ],
    "dim_term": [
        ("term_code", S), ("term_start", DT), ("census_date", DT),
        ("teaching_weeks", I), ("year", I), ("semester", S), ("is_current", B),
    ],
    "dim_campus": [("campus_code", S), ("campus_name", S), ("state", S)],
    "dim_program": [("program_code", S), ("program_name", S), ("field", S)],
    "dim_unit": [("unit_code", S), ("unit_name", S), ("program_code", S),
                 ("year_level", I), ("eftsl", D)],
    "dim_advisor": [("advisor_id", S), ("advisor_name", S), ("covered_campuses", S)],
    "fact_enrolment": [
        ("student_id", S), ("unit_code", S), ("term_code", S),
        ("campus_code", S), ("enrolment_status", S), ("grade", S),
        ("mark", D), ("eftsl", D), ("census_date", DT), ("passed", S),
        ("eftsl_certified", D), ("eftsl_passed", D),
    ],
    "fact_engagement_week": [
        ("student_id", S), ("term_code", S), ("week_number", I),
        ("week_start", DT), ("logins", I), ("page_views", I), ("items_due", I),
        ("submitted_on_time", I), ("submitted_late", I), ("missed", I),
    ],
    "fact_case": [
        ("case_id", S), ("student_id", S), ("term_code", S),
        ("opened_date", DT), ("source", S), ("case_type", S),
        ("seheef_activity", S), ("seheef_life_stage", S), ("advisor_id", S),
        ("contact_channel", S), ("contact_outcome", S), ("status", S),
        ("closed_date", DT), ("days_open", I), ("linked_alert_id", S),
    ],
    "fact_alert": [
        ("alert_id", S), ("student_id", S), ("term_code", S),
        ("week_number", I), ("raised_date", DT), ("reason_code", S),
        ("actioned_case_id", S), ("actioned_date", DT), ("contact_outcome", S),
        ("case_status", S), ("lifecycle_status", S), ("days_to_action", I),
    ],
    "mart_triage_current": [
        ("student_id", S), ("student_name", S), ("program_code", S),
        ("program_name", S), ("home_campus_code", S), ("mode", S),
        ("attendance_type", S), ("nbf_equity_cohort", S), ("first_nations", S),
        ("disability", S), ("is_commencing", S), ("first_alert_week", I),
        ("latest_alert_week", I), ("alert_count", I), ("reasons", S),
        ("contacted", I), ("case_status", S), ("contact_outcome", S),
        ("logins_last2wk", I), ("missed_last2wk", I), ("priority_tier", S),
        ("advisor_id", S),
    ],
    "mart_retention_cohort": [
        ("cohort", S), ("commencing_year", I), ("students", I),
        ("retention_rate", D),
    ],
    "mart_nbf_funding": [
        ("commencing_year", I), ("nbf_category", S), ("indicative_rate", I),
        ("commencing_students", I), ("indicative_funding", I),
        ("students_with_support_case", I), ("support_coverage", D),
    ],
    "mart_seheef_activity": [
        ("year", I), ("seheef_activity", S), ("seheef_life_stage", S),
        ("case_type", S), ("nbf_equity_cohort", S), ("cases", I),
        ("students", I), ("reach_rate", D),
    ],
    "mart_effectiveness_results": [
        ("estimator", S), ("estimate_pp", D), ("ci_low_pp", D),
        ("ci_high_pp", D), ("note", S),
    ],
    "mart_dq_summary": [
        ("rule_id", S), ("severity", S), ("table_name", S), ("issues", I),
    ],
    "mart_engagement_trend": [
        ("term_code", S), ("week_number", I), ("mode", S),
        ("nbf_equity_cohort", S), ("students", I), ("avg_logins", D),
        ("missed_rate", D),
    ],
}

# numeric columns that must not default-summarise (they are attributes)
NO_SUM = {
    ("dim_student", "commencing_year"), ("dim_student", "atar"),
    ("dim_student", "ses_quartile"), ("dim_term", "teaching_weeks"),
    ("dim_term", "year"), ("dim_unit", "year_level"), ("dim_unit", "eftsl"),
    ("mart_retention_cohort", "commencing_year"),
    ("mart_nbf_funding", "commencing_year"), ("mart_nbf_funding", "indicative_rate"),
    ("mart_seheef_activity", "year"), ("fact_engagement_week", "week_number"),
    ("fact_alert", "week_number"), ("fact_enrolment", "mark"),
    ("mart_triage_current", "first_alert_week"),
    ("mart_triage_current", "latest_alert_week"),
    ("mart_engagement_trend", "week_number"),
}

MEASURES = {
    "fact_enrolment": [
        ("Headcount", "DISTINCTCOUNT(fact_enrolment[student_id])", "#,0"),
        ("EFTSL Certified", "SUM(fact_enrolment[eftsl_certified])", "#,0.0"),
        ("EFTSL Passed", "SUM(fact_enrolment[eftsl_passed])", "#,0.0"),
        ("Success Rate", "DIVIDE([EFTSL Passed], [EFTSL Certified])", "0.0%"),
        ("Average Mark",
         'CALCULATE(AVERAGE(fact_enrolment[mark]), fact_enrolment[mark] >= 0, fact_enrolment[mark] <= 100)',
         "0.0"),
        ("Pre-Census Withdrawals",
         'CALCULATE(COUNTROWS(fact_enrolment), fact_enrolment[enrolment_status] = "Withdrawn pre-census")',
         "#,0"),
    ],
    "fact_alert": [
        ("Alerts Raised", "COUNTROWS(fact_alert)", "#,0"),
        ("Alerts Actioned",
         'CALCULATE(COUNTROWS(fact_alert), fact_alert[lifecycle_status] IN {"Actioned - case opened", "Covered by same-term case"})',
         "#,0"),
        ("Alert Action Rate", "DIVIDE([Alerts Actioned], [Alerts Raised])", "0.0%"),
        ("Median Days To Action", "MEDIAN(fact_alert[days_to_action])", "0.0"),
    ],
    "fact_case": [
        ("Cases Opened", "COUNTROWS(fact_case)", "#,0"),
        ("Reach Rate",
         'DIVIDE(CALCULATE(COUNTROWS(fact_case), SEARCH("Reached", fact_case[contact_outcome], 1, 0) > 0), CALCULATE(COUNTROWS(fact_case), fact_case[source] = "Early alert"))',
         "0.0%"),
        ("Median Days Case Open", "MEDIAN(fact_case[days_open])", "0.0"),
    ],
    "mart_nbf_funding": [
        ("NBF Indicative Funding", "SUM(mart_nbf_funding[indicative_funding])",
         '"$"#,0'),
        ("NBF Commencing Students", "SUM(mart_nbf_funding[commencing_students])", "#,0"),
        ("NBF Support Coverage",
         "DIVIDE(SUM(mart_nbf_funding[students_with_support_case]), SUM(mart_nbf_funding[commencing_students]))",
         "0.0%"),
    ],
    "mart_retention_cohort": [
        ("Retention Rate", "AVERAGE(mart_retention_cohort[retention_rate])", "0.0%"),
        ("Retention Gap vs Non-Equity",
         'VAR NonEq = CALCULATE(AVERAGE(mart_retention_cohort[retention_rate]), mart_retention_cohort[cohort] = "Non-equity", REMOVEFILTERS(mart_retention_cohort[cohort])) RETURN AVERAGE(mart_retention_cohort[retention_rate]) - NonEq',
         "+0.0%;-0.0%;0.0%"),
    ],
    "mart_triage_current": [
        ("Students On Triage List", "DISTINCTCOUNT(mart_triage_current[student_id])", "#,0"),
        ("P1 Students",
         'CALCULATE(DISTINCTCOUNT(mart_triage_current[student_id]), LEFT(mart_triage_current[priority_tier], 2) = "P1")',
         "#,0"),
    ],
    "fact_engagement_week": [
        ("Avg Weekly Logins", "AVERAGE(fact_engagement_week[logins])", "0.0"),
        ("Missed Item Rate",
         "DIVIDE(SUM(fact_engagement_week[missed]), SUM(fact_engagement_week[items_due]))",
         "0.0%"),
    ],
}

RELATIONSHIPS = [
    ("fact_enrolment", "student_id", "dim_student", "student_id"),
    ("fact_engagement_week", "student_id", "dim_student", "student_id"),
    ("fact_case", "student_id", "dim_student", "student_id"),
    ("fact_alert", "student_id", "dim_student", "student_id"),
    ("mart_triage_current", "student_id", "dim_student", "student_id"),
    ("fact_enrolment", "term_code", "dim_term", "term_code"),
    ("fact_engagement_week", "term_code", "dim_term", "term_code"),
    ("fact_case", "term_code", "dim_term", "term_code"),
    ("fact_alert", "term_code", "dim_term", "term_code"),
    ("fact_enrolment", "campus_code", "dim_campus", "campus_code"),
    ("fact_enrolment", "unit_code", "dim_unit", "unit_code"),
    ("dim_student", "program_code", "dim_program", "program_code"),
    ("fact_case", "advisor_id", "dim_advisor", "advisor_id"),
    ("mart_triage_current", "advisor_id", "dim_advisor", "advisor_id"),
]

ROLES = {
    "Manager": None,
    "Advisor_ADV01": ("dim_advisor", '[advisor_id] = "ADV01"'),
    "Advisor_ADV09_Online": ("dim_advisor", '[advisor_id] = "ADV09"'),
}

PAGES = ["Executive", "Equity and NBF", "Advisor triage",
         "Intervention effectiveness", "Data quality"]


def m_source(name, cols):
    sel = ", ".join(f'"{c}"' for c, _ in cols)
    typed = ", ".join("{" + f'"{c}", {M_TYPE[t]}' + "}" for c, t in cols)
    return [
        "let",
        f"    Source = Csv.Document(File.Contents(DataFolder & \"\\{name}.csv\"), "
        "[Delimiter = \",\", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),",
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        f"    Selected = Table.SelectColumns(Promoted, {{{sel}}}),",
        f"    Typed = Table.TransformColumnTypes(Selected, {{{typed}}})",
        "in",
        "    Typed",
    ]


def table_tom(name, cols):
    columns = []
    for col, typ in cols:
        summarize = "none"
        if typ in (I, D) and name.startswith(("fact_", "mart_")) \
                and (name, col) not in NO_SUM:
            summarize = "sum"
        columns.append({
            "name": col, "dataType": typ, "sourceColumn": col,
            "summarizeBy": summarize,
        })
    table = {
        "name": name,
        "columns": columns,
        "partitions": [{
            "name": name, "mode": "import",
            "source": {"type": "m", "expression": m_source(name, cols)},
        }],
    }
    measures = [
        {"name": mname, "expression": dax, **({"formatString": fmt} if fmt else {})}
        for mname, dax, fmt in MEASURES.get(name, [])
    ]
    if measures:
        table["measures"] = measures
    return table


def model_bim():
    roles = []
    for role, perm in ROLES.items():
        r = {"name": role, "modelPermission": "read"}
        if perm:
            r["tablePermissions"] = [{"name": perm[0], "filterExpression": perm[1]}]
        roles.append(r)
    return {
        "name": str(uuid.uuid4()),
        "compatibilityLevel": 1567,
        "model": {
            "culture": "en-US",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-AU",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True,
            },
            "expressions": [{
                "name": "DataFolder",
                "kind": "m",
                "expression": f"\"{DATA_FOLDER}\" meta [IsParameterQuery=true, "
                              "Type=\"Text\", IsParameterQueryRequired=true]",
            }],
            "tables": [table_tom(n, c) for n, c in TABLES.items()],
            "relationships": [
                {"name": f"rel{i:02d}", "fromTable": ft, "fromColumn": fc,
                 "toTable": tt, "toColumn": tc}
                for i, (ft, fc, tt, tc) in enumerate(RELATIONSHIPS, 1)
            ],
            "roles": roles,
            "annotations": [
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
            ],
        },
    }


def platform_file(item_type, name):
    return json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": item_type, "displayName": name},
        "config": {"version": "2.0", "logicalId": str(uuid.uuid4())},
    }, indent=2)


def report_json():
    sections = []
    for i, p in enumerate(PAGES):
        sections.append({
            "name": f"page{i}", "displayName": p, "displayOption": 1,
            "height": 720.0, "width": 1280.0,
            "visualContainers": [], "config": "{}", "filters": "[]",
        })
    return json.dumps({
        "config": json.dumps({"version": "5.43", "themeCollection": {}}),
        "layoutOptimization": 0,
        "sections": sections,
        "publicCustomVisuals": [],
    }, indent=2)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    sm = OUT / "compass.SemanticModel"
    rp = OUT / "compass.Report"
    sm.mkdir(parents=True)
    rp.mkdir(parents=True)

    (OUT / "compass.pbip").write_text(json.dumps({
        "version": "1.0",
        "artifacts": [{"report": {"path": "compass.Report"}}],
        "settings": {"enableAutoRecovery": True},
    }, indent=2), encoding="utf-8")

    (sm / ".platform").write_text(platform_file("SemanticModel", "compass"), encoding="utf-8")
    (sm / "definition.pbism").write_text(json.dumps({"version": "1.0"}), encoding="utf-8")
    (sm / "model.bim").write_text(json.dumps(model_bim(), indent=2), encoding="utf-8")

    (rp / ".platform").write_text(platform_file("Report", "compass"), encoding="utf-8")
    (rp / "definition.pbir").write_text(json.dumps({
        "version": "1.0",
        "datasetReference": {"byPath": {"path": "../compass.SemanticModel"}},
    }, indent=2), encoding="utf-8")
    (rp / "report.json").write_text(report_json(), encoding="utf-8")

    n_measures = sum(len(v) for v in MEASURES.values())
    print(f"PBIP written to {OUT}")
    print(f"  {len(TABLES)} tables, {len(RELATIONSHIPS)} relationships, "
          f"{n_measures} measures, {len(ROLES)} RLS roles, {len(PAGES)} pages")
    print("Open compass.pbip in Power BI Desktop, then Home -> Refresh to load "
          "data. Edit the DataFolder parameter if the repo lives elsewhere.")


if __name__ == "__main__":
    main()
