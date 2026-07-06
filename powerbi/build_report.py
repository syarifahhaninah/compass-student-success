"""Generate the Compass report layout — visuals as code.

Writes powerbi/pbip/compass.Report/report.json (PBIR-legacy format) with all
five pages of visuals: KPI cards, charts, tables, matrices and slicers, each
with an explicit semantic query, friendly display names, the Compass theme
(registered as a report resource) and conditional formatting on the triage
priority tiers. Run AFTER build_pbip.py; this script only rewrites
report.json + the theme resource — the semantic model and its data cache are
untouched.

Usage:  python powerbi/build_report.py
Then :  open powerbi/pbip/compass.pbip in Power BI Desktop.
"""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "powerbi" / "pbip" / "compass.Report" / "report.json"
THEME = ROOT / "powerbi" / "theme.json"
THEME_RESOURCE = "CompassTheme.json"

_counter = 0


def _name():
    global _counter
    _counter += 1
    return f"vc{_counter:04d}"


# ---------------------------------------------------------------- fields --
def col(table, column):
    return {"kind": "col", "table": table, "column": column,
            "ref": f"{table}.{column}"}


def mea(table, name):
    return {"kind": "mea", "table": table, "column": name,
            "ref": f"{table}.{name}"}


def agg(table, column, fn=0):  # 0 = Sum, 1 = Avg
    label = {0: "Sum", 1: "Avg"}[fn]
    return {"kind": "agg", "table": table, "column": column, "fn": fn,
            "ref": f"{label}({table}.{column})"}


def _select(field, alias):
    src = {"Expression": {"SourceRef": {"Source": alias}},
           "Property": field["column"]}
    if field["kind"] == "col":
        expr = {"Column": src}
    elif field["kind"] == "mea":
        expr = {"Measure": src}
    else:
        expr = {"Aggregation": {"Expression": {"Column": src},
                                "Function": field["fn"]}}
    return {**expr, "Name": field["ref"]}


def visual(vtype, x, y, w, h, roles, title=None, objects=None,
           extra_selects=None, display=None):
    """roles: {"Values": [field, ...], "Category": [...], ...}
    display: {queryRef: friendly display name} rendered as columnProperties.
    extra_selects: fields added to the query but not projected (e.g. measures
    that drive conditional formatting)."""
    tables = []
    for fields in list(roles.values()) + [extra_selects or []]:
        for f in fields:
            if f["table"] not in tables:
                tables.append(f["table"])
    alias = {t: f"t{i + 1}" for i, t in enumerate(tables)}

    selects, seen = [], set()
    for fields in list(roles.values()) + [extra_selects or []]:
        for f in fields:
            if f["ref"] not in seen:
                seen.add(f["ref"])
                selects.append(_select(f, alias[f["table"]]))

    single = {
        "visualType": vtype,
        "projections": {role: [{"queryRef": f["ref"]} for f in fields]
                        for role, fields in roles.items()},
        "prototypeQuery": {
            "Version": 2,
            "From": [{"Name": a, "Entity": t, "Type": 0}
                     for t, a in alias.items()],
            "Select": selects,
        },
        "drillFilterOtherVisuals": True,
    }
    if display:
        single["columnProperties"] = {
            ref: {"displayName": name} for ref, name in display.items()
        }
    if objects:
        single["objects"] = objects
    if title:
        single["vcObjects"] = {"title": [{"properties": {
            "text": {"expr": {"Literal": {"Value": f"'{title}'"}}},
            "show": {"expr": {"Literal": {"Value": "true"}}},
        }}]}
    name = _name()
    config = {
        "name": name,
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 0,
                                           "width": w, "height": h}}],
        "singleVisual": single,
    }
    return {"x": x, "y": y, "z": 0, "width": w, "height": h,
            "config": json.dumps(config), "filters": "[]"}


def card(x, y, w, h, field, display_units=None, precision=None):
    objects = None
    if display_units is not None:
        objects = {"labels": [{"properties": {
            "labelDisplayUnits": {"expr": {"Literal": {"Value": f"{display_units}D"}}},
            **({"labelPrecision": {"expr": {"Literal": {"Value": f"{precision}D"}}}}
               if precision is not None else {}),
        }}]}
    return visual("card", x, y, w, h, {"Values": [field]}, objects=objects)


# Conditional formatting on the triage priority column, exactly as Power BI
# Desktop serialises field-value background formatting (dual selector).
TIER_CF = {"values": [
    {
        "properties": {"backColor": {"solid": {"color": {"expr": {
            "Measure": {"Expression": {"SourceRef": {"Entity": "mart_triage_current"}},
                        "Property": "Tier Colour"}}}}}},
        "selector": {"metadata": "mart_triage_current.priority_tier"},
    },
    {
        "properties": {"backColor": {"solid": {"color": {"expr": {
            "Measure": {"Expression": {"SourceRef": {"Entity": "mart_triage_current"}},
                        "Property": "Tier Colour"}}}}}},
        "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                     "metadata": "mart_triage_current.priority_tier"},
    },
]}


# ----------------------------------------------------------------- pages --
def page_executive():
    return [
        card(16, 16, 232, 92, mea("fact_enrolment", "Headcount")),
        card(264, 16, 232, 92, mea("fact_enrolment", "Success Rate")),
        card(512, 16, 232, 92, mea("fact_enrolment", "EFTSL Certified")),
        card(760, 16, 232, 92, mea("fact_enrolment", "Average Mark")),
        card(1008, 16, 256, 92, mea("fact_enrolment", "Pre-Census Withdrawals")),
        visual("lineChart", 16, 124, 620, 280, {
            "Category": [col("dim_term", "term_code")],
            "Y": [mea("fact_enrolment", "Success Rate")],
            "Series": [col("dim_student", "mode")],
        }, title="Success rate by term — on-campus vs online",
            display={"dim_term.term_code": "Term", "dim_student.mode": "Mode"}),
        visual("clusteredBarChart", 652, 124, 612, 280, {
            "Category": [col("dim_campus", "campus_name")],
            "Y": [mea("fact_enrolment", "Success Rate")],
        }, title="Success rate by campus",
            display={"dim_campus.campus_name": "Campus"}),
        visual("pivotTable", 16, 420, 1248, 284, {
            "Rows": [col("dim_program", "field"), col("dim_program", "program_name")],
            "Values": [mea("fact_enrolment", "Headcount"),
                       mea("fact_enrolment", "Success Rate"),
                       mea("fact_enrolment", "Average Mark"),
                       mea("fact_enrolment", "Pre-Census Withdrawals")],
        }, title="Program performance",
            display={"dim_program.field": "Discipline",
                     "dim_program.program_name": "Program"}),
    ]


def page_equity():
    return [
        card(16, 16, 300, 92, mea("mart_nbf_funding", "NBF Indicative Funding"),
             display_units=1000000, precision=2),
        card(332, 16, 300, 92, mea("mart_nbf_funding", "NBF Commencing Students")),
        card(648, 16, 300, 92, mea("mart_nbf_funding", "NBF Support Coverage")),
        card(964, 16, 300, 92, mea("fact_case", "Cases Opened")),
        visual("clusteredBarChart", 16, 124, 612, 280, {
            "Category": [col("mart_retention_cohort", "cohort")],
            "Y": [mea("mart_retention_cohort", "Retention Rate")],
        }, title="Year-1 retention by cohort (gaps in context)",
            display={"mart_retention_cohort.cohort": "Cohort"}),
        visual("lineChart", 652, 124, 612, 280, {
            "Category": [col("mart_retention_cohort", "commencing_year")],
            "Y": [mea("mart_retention_cohort", "Retention Rate")],
            "Series": [col("mart_retention_cohort", "cohort")],
        }, title="Retention trend by cohort",
            display={"mart_retention_cohort.commencing_year": "Commencing year",
                     "mart_retention_cohort.cohort": "Cohort"}),
        visual("tableEx", 16, 420, 612, 284, {
            "Values": [col("mart_nbf_funding", "nbf_category"),
                       agg("mart_nbf_funding", "commencing_students"),
                       col("mart_nbf_funding", "indicative_rate"),
                       agg("mart_nbf_funding", "indicative_funding"),
                       agg("mart_nbf_funding", "support_coverage", 1)],
        }, title="NBF categories — indicative funding (AUD)",
            display={
                "mart_nbf_funding.nbf_category": "NBF category",
                "Sum(mart_nbf_funding.commencing_students)": "Commencing students",
                "mart_nbf_funding.indicative_rate": "Rate (AUD)",
                "Sum(mart_nbf_funding.indicative_funding)": "Indicative funding (AUD)",
                "Avg(mart_nbf_funding.support_coverage)": "Support coverage",
            }),
        visual("pivotTable", 652, 420, 612, 284, {
            "Rows": [col("mart_seheef_activity", "seheef_activity"),
                     col("mart_seheef_activity", "seheef_life_stage")],
            "Columns": [col("mart_seheef_activity", "year")],
            "Values": [agg("mart_seheef_activity", "cases"),
                       agg("mart_seheef_activity", "students")],
        }, title="SEHEEF activity reporting — generated from case data",
            display={
                "mart_seheef_activity.seheef_activity": "SEHEEF activity",
                "mart_seheef_activity.seheef_life_stage": "Life stage",
                "mart_seheef_activity.year": "Year",
                "Sum(mart_seheef_activity.cases)": "Cases",
                "Sum(mart_seheef_activity.students)": "Students",
            }),
    ]


def page_triage():
    return [
        card(16, 16, 232, 92, mea("mart_triage_current", "Students On Triage List")),
        card(264, 16, 232, 92, mea("mart_triage_current", "P1 Students")),
        card(512, 16, 232, 92, mea("fact_alert", "Alert Action Rate")),
        card(760, 16, 232, 92, mea("fact_alert", "Median Days To Action")),
        visual("tableEx", 16, 124, 1010, 580, {
            "Values": [col("mart_triage_current", "priority_tier"),
                       col("mart_triage_current", "student_name"),
                       col("mart_triage_current", "student_id"),
                       col("mart_triage_current", "program_name"),
                       col("mart_triage_current", "home_campus_code"),
                       col("mart_triage_current", "mode"),
                       col("mart_triage_current", "reasons"),
                       col("mart_triage_current", "latest_alert_week"),
                       col("mart_triage_current", "logins_last2wk"),
                       col("mart_triage_current", "missed_last2wk"),
                       col("mart_triage_current", "nbf_equity_cohort"),
                       col("mart_triage_current", "case_status"),
                       col("mart_triage_current", "advisor_id")],
        }, title="Caseload — who to contact this week",
            extra_selects=[mea("mart_triage_current", "Tier Colour")],
            objects=TIER_CF,
            display={
                "mart_triage_current.priority_tier": "Priority",
                "mart_triage_current.student_name": "Student",
                "mart_triage_current.student_id": "ID",
                "mart_triage_current.program_name": "Program",
                "mart_triage_current.home_campus_code": "Campus",
                "mart_triage_current.mode": "Mode",
                "mart_triage_current.reasons": "Alert reasons",
                "mart_triage_current.latest_alert_week": "Latest wk",
                "mart_triage_current.logins_last2wk": "Logins (2wk)",
                "mart_triage_current.missed_last2wk": "Missed (2wk)",
                "mart_triage_current.nbf_equity_cohort": "NBF cohort",
                "mart_triage_current.case_status": "Case status",
                "mart_triage_current.advisor_id": "Advisor",
            }),
        visual("slicer", 1042, 124, 222, 180, {
            "Values": [col("mart_triage_current", "priority_tier")],
        }, display={"mart_triage_current.priority_tier": "Priority tier"}),
        visual("slicer", 1042, 316, 222, 180, {
            "Values": [col("dim_advisor", "advisor_name")],
        }, display={"dim_advisor.advisor_name": "Advisor"}),
        visual("clusteredBarChart", 1042, 508, 222, 196, {
            "Category": [col("mart_triage_current", "advisor_id")],
            "Y": [mea("mart_triage_current", "Students On Triage List")],
        }, title="Caseload balance",
            display={"mart_triage_current.advisor_id": "Advisor"}),
    ]


def page_effectiveness():
    return [
        visual("tableEx", 16, 16, 800, 180, {
            "Values": [col("mart_effectiveness_results", "estimator"),
                       agg("mart_effectiveness_results", "estimate_pp"),
                       agg("mart_effectiveness_results", "ci_low_pp"),
                       agg("mart_effectiveness_results", "ci_high_pp"),
                       col("mart_effectiveness_results", "note")],
        }, title="Effect of outreach on next-term persistence (pp)",
            display={
                "mart_effectiveness_results.estimator": "Estimator",
                "Sum(mart_effectiveness_results.estimate_pp)": "Effect (pp)",
                "Sum(mart_effectiveness_results.ci_low_pp)": "CI low",
                "Sum(mart_effectiveness_results.ci_high_pp)": "CI high",
                "mart_effectiveness_results.note": "Note",
            }),
        visual("clusteredBarChart", 16, 212, 800, 300, {
            "Category": [col("mart_effectiveness_results", "estimator")],
            "Y": [agg("mart_effectiveness_results", "estimate_pp")],
        }, title="Naive vs matched estimate — why method matters",
            display={"mart_effectiveness_results.estimator": "Estimator",
                     "Sum(mart_effectiveness_results.estimate_pp)": "Effect (pp)"}),
        visual("lineChart", 832, 16, 432, 496, {
            "Category": [col("mart_engagement_trend", "week_number")],
            "Y": [agg("mart_engagement_trend", "avg_logins", 1)],
            "Series": [col("mart_engagement_trend", "mode")],
        }, title="Weekly engagement by mode",
            display={"mart_engagement_trend.week_number": "Teaching week",
                     "Avg(mart_engagement_trend.avg_logins)": "Avg logins",
                     "mart_engagement_trend.mode": "Mode"}),
        card(16, 528, 300, 92, mea("fact_alert", "Alerts Raised")),
        card(332, 528, 300, 92, mea("fact_alert", "Alerts Actioned")),
        card(648, 528, 300, 92, mea("fact_case", "Reach Rate")),
    ]


def page_dq():
    return [
        card(16, 16, 300, 92, agg("mart_dq_summary", "issues")),
        visual("tableEx", 16, 124, 612, 300, {
            "Values": [col("mart_dq_summary", "rule_id"),
                       col("mart_dq_summary", "severity"),
                       col("mart_dq_summary", "table_name"),
                       agg("mart_dq_summary", "issues")],
        }, title="Validation findings by rule",
            display={
                "mart_dq_summary.rule_id": "Rule",
                "mart_dq_summary.severity": "Severity",
                "mart_dq_summary.table_name": "Source table",
                "Sum(mart_dq_summary.issues)": "Findings",
            }),
        visual("clusteredBarChart", 652, 124, 612, 300, {
            "Category": [col("mart_dq_summary", "rule_id")],
            "Y": [agg("mart_dq_summary", "issues")],
        }, title="Findings by rule",
            display={"mart_dq_summary.rule_id": "Rule",
                     "Sum(mart_dq_summary.issues)": "Findings"}),
    ]


# Page-level filter: NBF figures are meaningful for the funded (2026)
# commencing cohort only. Applies to mart_nbf_funding visuals; unrelated
# marts on the page (retention, SEHEEF) are untouched.
NBF_2026_FILTER = [{
    "name": "pf_nbf_2026",
    "expression": {"Column": {
        "Expression": {"SourceRef": {"Entity": "mart_nbf_funding"}},
        "Property": "commencing_year"}},
    "filter": {
        "Version": 2,
        "From": [{"Name": "m", "Entity": "mart_nbf_funding", "Type": 0}],
        "Where": [{"Condition": {"In": {
            "Expressions": [{"Column": {
                "Expression": {"SourceRef": {"Source": "m"}},
                "Property": "commencing_year"}}],
            "Values": [[{"Literal": {"Value": "2026L"}}]],
        }}}],
    },
    "type": "Categorical",
    "howCreated": 1,
}]

PAGES = [
    ("Executive", page_executive, None),
    ("Equity and NBF", page_equity, NBF_2026_FILTER),
    ("Advisor triage", page_triage, None),
    ("Intervention effectiveness", page_effectiveness, None),
    ("Data quality", page_dq, None),
]


def main():
    sections = []
    for i, (display_name, builder, page_filters) in enumerate(PAGES):
        sections.append({
            "name": f"page{i}", "displayName": display_name, "displayOption": 1,
            "height": 720.0, "width": 1280.0,
            "visualContainers": builder(),
            "config": "{}",
            "filters": json.dumps(page_filters) if page_filters else "[]",
        })

    # Register the Compass theme as a report resource (type codes as Power BI
    # Desktop serialises them: resource item type 201, customTheme type 1).
    res_dir = REPORT.parent / "StaticResources" / "RegisteredResources"
    res_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(THEME, res_dir / THEME_RESOURCE)

    doc = {
        "config": json.dumps({
            "version": "5.66",
            "themeCollection": {"customTheme": {"name": THEME_RESOURCE, "type": 1}},
        }),
        "layoutOptimization": 0,
        "resourcePackages": [{"resourcePackage": {
            "name": "RegisteredResources", "type": 1, "disabled": False,
            "items": [{"name": THEME_RESOURCE, "path": THEME_RESOURCE, "type": 201}],
        }}],
        "sections": sections,
        "publicCustomVisuals": [],
    }
    REPORT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    n = sum(len(s["visualContainers"]) for s in sections)
    print(f"Wrote {REPORT}")
    print(f"  {len(sections)} pages, {n} visuals, theme + tier formatting included")


if __name__ == "__main__":
    main()
