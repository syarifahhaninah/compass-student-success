# Compass Data Dictionary

One metric, one definition. Every measure names its method and its source
authority. Equity attributes reference the HEIMS/TCSI-style element they
correspond to (verify exact element numbers against the current TCSI data
dictionary before production use).

## Metric definitions

| Metric | Definition | Authority / notes |
|---|---|---|
| **Success rate** | EFTSL passed ÷ EFTSL certified, per year/term/cohort. Certified = census-date load (excludes pre-census withdrawals); passed = units graded HD/DI/CR/PA. | Department of Education Higher Education Statistics method ("success rate" / progress rate) |
| **Institutional retention rate (Y1)** | Commencing domestic students in year Y with any enrolment in year Y+1, or completion. | Single-institution variant of the DoE retention rate. **Not** the sector-adjusted ("new adjusted") rate — cross-institution transfers cannot be observed from inside one provider; the difference is disclosed wherever the metric is shown |
| **Attrition** | 1 − retention (institutional). | Same caveat as above |
| **Completion** | Student flagged completed on meeting program unit requirements. Prototype simplification: all programs modelled as 3-year/24-unit | — |
| **Alert action rate** | Alerts with lifecycle status "Actioned – case opened" or "Covered by same-term case" ÷ all alerts, per term. | Internal; the Support for Students Policy evidence metric |
| **Days to action** | Case opened date − alert raised date. | Internal SLA metric |
| **Support coverage (NBF)** | NBF-cohort students with ≥1 support case ÷ NBF-cohort students. | Feeds NBF acquittal narrative |
| **Intervention effect** | Matched-comparison (CEM) difference in next-term persistence, contacted vs uncontacted alerted students; naive difference shown only as an anti-example. | Civitas-style matched evaluation; never raw before/after |

## Equity attribute derivations

| Attribute | Derivation | Element reference |
|---|---|---|
| First Nations | Flag from student record; `Unknown` when source flag missing (never imputed) | ATSI code (HEIMS E316-style) |
| Disability | Flag from student record; `Unknown` when missing | Disability code (E615-style) |
| Low SES | **Derived**: postcode of first recorded address → SES (IEO-style) quartile lookup; quartile 1 = low SES. Never stored on the student record | Postcode (E320-style) + ABS IEO methodology per NBF guidance |
| Regional/remote | Derived: postcode → remoteness classification | ASGS remoteness structure |
| NBF category | Low SES / First Nations / both / low SES high-preparedness (ATAR ≥ 80), domestic CSP only | Needs-based Funding guidance, 2026 commencing rates |
| NESB | Flag from student record | Language element (E348-style) |

## Alert reason codes (leading indicators)

| Code | Rule | Rationale |
|---|---|---|
| `INACTIVITY_14D` | Rolling 2-week LMS logins ≤ 2 | Strongest single early disengagement signal in Australian research |
| `NON_SUBMISSION` | Cumulative missed assessment items ≥ 3 | Early non-submission precedes failure |
| `LOW_ONTIME_RATE` | On-time submission rate < 40% by week 6+ (≥3 items due) | Pattern, not one-off |

Alert lifecycle states: `Open – awaiting triage` → `Actioned – case opened` /
`Covered by same-term case` / `Monitored – no contact`. Every alert reaches a
terminal state; none disappears — this is the Support for Students Policy
evidence chain.

## Table glossary (warehouse layer)

**dim_student** — one row per person (post-survivorship). Names are synthetic.
Key derived columns: `ses_quartile`, `low_ses`, `regional_remote`,
`nbf_equity_cohort`, `nbf_category`, `student_status` (active / discontinued /
completed), `commencing_year`.

**dim_term / dim_campus / dim_program / dim_unit / dim_advisor** — conformed
reference dimensions. `dim_term.is_current` drives the triage page.

**fact_enrolment** — student × unit × term. Grades HD/DI/CR/PA/NN/WN/WW/IP;
`eftsl_certified` and `eftsl_passed` precomputed for the success-rate measure.

**fact_engagement_week** — student × term × week LMS aggregates: logins, page
views, items due/submitted on time/late/missed.

**fact_case** — case-management records with SEHEEF `seheef_activity` and
`seheef_life_stage` tagged at point of entry, advisor, channel, outcome,
status, `days_open`, and `linked_alert_id` for the closed loop.

**fact_alert** — every raised alert with reason code and `lifecycle_status`.

**Marts** — one per dashboard question: `mart_executive`,
`mart_retention_cohort`, `mart_nbf_funding`, `mart_seheef_activity`,
`mart_triage_current`, `mart_effectiveness_input` (+ `_results`),
`mart_dq_summary`, `mart_engagement_trend`.

**Quality layer** (`data/quality/`) — `dq_issues` (every validation finding),
`rej_enrolments` (quarantine), `injected_defects` (the generator's answer key,
used only to score the pipeline's catch rate — 100% in the current build).

## Known limitations

1. Synthetic behaviour is simpler than reality (weekly grain; single-effect
   intervention model; all programs 3-year).
2. Institutional retention cannot see cross-provider transfers (disclosed).
3. Element numbers are HEIMS/TCSI-style references, to be verified against the
   current TCSI data dictionary in production.
4. Cohorts commencing before 2023 are out of scope of the simulation window.
5. Indicator thresholds are illustrative; production thresholds would be
   co-designed with advisors and validated against historical outcomes.
