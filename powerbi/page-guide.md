# Power BI Page Build Guide

Five pages, each named for the decision it serves. Build 1–3 first (MVP);
4–5 before interview. Apply `theme.json` (View → Browse for themes). Footer on
every page: *Synthetic data — no real student records · Compass prototype ·
as at 27 Apr 2026 (2026S1 week 8).*

---

## Page 1 — Executive: "How are our students going?"

Audience: Director / DVC-level, non-technical. Layout: KPI row + two charts + matrix.

- **KPI cards (top row):** Headcount · EFTSL Certified · Success Rate ·
  Retention (All domestic, latest cohort — card from mart_retention_cohort filtered) ·
  Pre-Census Withdrawals.
- **Line chart:** Success Rate by dim_term[term_code], legend dim_student[mode]
  (On-campus vs Online — the online gap is the story).
- **Clustered bar:** Success Rate by dim_campus[campus_name], sorted.
- **Matrix:** rows dim_program[field] → program_name; values Headcount, Success
  Rate, Average Mark, Pre-Census Withdrawals. Conditional formatting on Success
  Rate (bad → good diverging, thresholds 0.80/0.90).
- **Slicers:** term, campus, mode.

## Page 2 — Equity & NBF: "What do we owe the funding, and is it reaching students?"

The page most applicants won't have. Audience: manager + funding accountability.

- **KPI cards:** NBF Indicative Funding (AUD) · NBF Commencing Students ·
  NBF Support Coverage · Retention Gap vs Non-Equity (First Nations selected).
- **Clustered bar:** mart_retention_cohort — retention_rate by cohort, legend
  commencing_year. Reference line at Non-equity rate. This is the ACSES-style
  "gaps in context" visual.
- **Table:** mart_nbf_funding — nbf_category, commencing_students,
  indicative_rate, indicative_funding, support_coverage (data bars).
- **Matrix (SEHEEF acquittal view):** rows seheef_activity → seheef_life_stage;
  columns year; values cases, students, reach_rate. Title it
  *"NBF activity reporting — generated from operational case data"*.
- **Text box:** one-sentence method note: low SES derived from first-address
  postcode IEO quartile per NBF guidance; institutional retention definition
  disclosed in the data dictionary.

## Page 3 — Advisor triage: "Who do I contact this Monday?"

Audience: Student Care and Success Advisors. Built entirely on mart_triage_current. RLS applies here.

- **KPI cards:** Students On Triage List · P1 Students · Alert Action Rate
  (current term) · Median Days To Action.
- **Table (the caseload):** student_name, student_id, program_name,
  home_campus_code, mode, priority_tier (sorted P1 first), reasons,
  latest_alert_week, logins_last2wk, missed_last2wk, nbf_equity_cohort,
  case_status, advisor_id. Conditional background on priority_tier
  (P1 red / P2 amber / P3 blue / P4 grey). Reasons column is plain language —
  this is the anti-black-box design.
- **Bar:** students by priority_tier by advisor_id (workload balance view).
- **Slicers:** advisor, campus, priority tier, NBF cohort, commencing students only.
- **Demo note:** capture this page twice — as Manager (all) and *View as* ADV01
  (caseload only) — for the RLS screenshot pair.

## Page 4 — Intervention effectiveness: "Is outreach working?" *(stretch)*

- **KPI cards:** alerted student-terms · contacted share · CEM estimate (pp).
- **Bar with error bars:** mart_effectiveness_results — naive vs matched
  estimates with CIs. Annotate: *"Naive comparison understates impact because
  advisors triage worst-first; matched comparison recovers the true effect —
  method validated against the generator's injected ground truth."*
- **Line:** mart_engagement_trend — avg_logins by week, legend contacted vs not
  (optional cut).

## Page 5 — Data quality: "Can we trust these numbers?" *(stretch)*

- **Table:** mart_dq_summary (rule, severity, issues) + quarantine count.
- **Cards:** total issues · quarantined rows · duplicate students merged ·
  **catch rate vs injected answer key (100%)** with a note explaining the
  answer-key scoring idea.
- **Text box:** the governance story — validation rules quarantine fatal rows,
  warnings surface without imputation, equity flags are never guessed.

---

## Assembly checklist

1. Load CSVs per model-spec.md; fix types; create relationships.
2. Create Measures table; paste measures.dax definitions one by one.
3. Apply theme.json; set page size 16:9; add footer text box (copy across pages).
4. Build pages 1→3; screenshot each at 1920×1080 into `powerbi/screenshots/`.
5. RLS roles per model-spec.md; capture the ADV01 vs Manager pair.
6. Save as `powerbi/compass.pbix` (kept out of git if >100 MB; screenshots are
   the reviewable artefact either way).
