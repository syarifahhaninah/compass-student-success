# Power BI Semantic Model Specification

## Load

Get Data → Text/CSV, from `data/warehouse/`. Import mode for everything.

| Table | Role |
|---|---|
| dim_student, dim_term, dim_campus, dim_program, dim_unit, dim_advisor | Dimensions |
| fact_enrolment, fact_engagement_week, fact_case, fact_alert | Facts |
| mart_retention_cohort, mart_nbf_funding, mart_seheef_activity, mart_triage_current, mart_effectiveness_results, mart_dq_summary, mart_engagement_trend | Pre-aggregated marts (no relationships needed except noted) |

Power Query steps to apply: set `student_id` columns to Text everywhere
(leading-zero safety); `dob`, dates to Date; promote headers.

## Relationships (star, single direction, dims filter facts)

- dim_student[student_id] 1→* fact_enrolment / fact_engagement_week / fact_case / fact_alert / mart_triage_current[student_id]
- dim_term[term_code] 1→* fact_enrolment / fact_engagement_week / fact_case / fact_alert
- dim_campus[campus_code] 1→* fact_enrolment[campus_code]
- dim_unit[unit_code] 1→* fact_enrolment[unit_code]
- dim_program[program_code] 1→* dim_student[program_code] (and dim_unit)
- dim_advisor[advisor_id] 1→* mart_triage_current[advisor_id] and fact_case[advisor_id]

Do NOT relate marts that carry their own cohort/year columns
(mart_retention_cohort, mart_nbf_funding, mart_seheef_activity,
mart_effectiveness_results, mart_dq_summary) — they are self-contained.

## Row-level security

Role **Advisor** on dim_advisor:
```dax
[advisor_id] = LOOKUPVALUE(dim_advisor[advisor_id], dim_advisor[advisor_name], USERPRINCIPALNAME())
```
For the demo (no tenant), create one role per advisor instead, e.g. role
`ADV01` with filter `dim_advisor[advisor_id] = "ADV01"`, and use *View as* to
screenshot the advisor-scoped triage page. Role **Manager**: no filter.
The point being demonstrated: advisors see their caseload, managers see all —
data minimisation as a model feature, mirrored by the SQL Server security
policy in `sql/mssql_ddl.sql`.

## Display folders and formats

- Success/retention/coverage rates: percentage, 1 decimal.
- indicative_funding: currency AUD, 0 decimals ("$#,0").
- Never display USD anywhere.

## Sensitivity / footer

Every page footer: `Synthetic data — no real student records | Compass prototype | as at 27 Apr 2026 (2026S1 week 8)`
