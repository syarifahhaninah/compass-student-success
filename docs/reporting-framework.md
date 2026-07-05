# Compass Reporting Framework

*How one data environment serves three reporting obligations — operational,
regulatory, and funding — without anyone writing a report twice.*

## 1. The obligations

| Obligation | Instrument | What must be evidenced | When |
|---|---|---|---|
| Identify and support students at risk | Support for Students Policy (HEP Guidelines Ch 10A); HESF 1.3.3; TEQSA compliance focus | Documented identification processes using leading indicators; evidence identified students were offered support; outcomes recorded | Continuous; annual policy review |
| Account for equity funding | Needs-based Funding (from 1 Jan 2026), HEPPP-style activity reporting per SEHEEF program logic | Activities delivered, cohorts reached, expenditure alignment, outcomes | First report early 2027 for calendar 2026 |
| Institutional performance monitoring | Internal (directorate/DVC-E); Accord/ATEC context | Retention, progression, success, completion by equity cohort; intervention effectiveness | Term and annual cycles |

## 2. The design principle: reporting as a by-product

The traditional failure mode is three separate reporting exercises reconstructed
from memory and spreadsheets months after the fact. Compass inverts this: the
**operational workflow writes the compliance evidence as it happens.**

- Every alert is a record with a lifecycle (`raised → actioned/monitored →
  outcome`). The Support for Students evidence chain **is** the alert table —
  an auditor's query, not a retrospective narrative.
- Every case is tagged with a **SEHEEF activity type and student life stage at
  point of entry** (a two-field dropdown for the advisor, not a form). The NBF
  activity report **is** an aggregation of `fact_case` — see
  `mart_seheef_activity`.
- Every metric has **one definition** (docs/data-dictionary.md), aligned to
  Department of Education methods, so directorate numbers reconcile with
  institutional reporting by construction rather than negotiation.

## 3. The reporting stack

| Layer | Cadence | Audience | Compass artefact |
|---|---|---|---|
| Triage | Weekly | Advisors | `mart_triage_current` — page 3; RLS-scoped caseloads |
| Service operations | Fortnightly/monthly | Manager, Student Care and Success | Alert action rates, days-to-action, caseload balance, reach rates |
| Performance & equity | Term | Director / DVC-E | Executive + equity pages: success, retention, gaps in demographic context |
| Intervention effectiveness | Term/annual | Manager, program review | Matched-comparison estimates (`mart_effectiveness_results`) — never raw before/after |
| NBF acquittal | Annual (first: early 2027) | Department of Education | `mart_seheef_activity` + `mart_nbf_funding` + expenditure mapping |
| Data quality & governance | Continuous | Data Excellence liaison | `mart_dq_summary`, quarantine, definitions register |

## 4. Metric governance

1. **Definitions live in one place** (the data dictionary) with authority
   citations; dashboard tooltips link to them.
2. **Institutional vs sector definitions are disclosed** wherever they differ
   (e.g. institutional retention cannot observe cross-provider transfer; the
   DoE adjusted rate can).
3. **Equity flags are never imputed.** Missing flags surface as `Unknown` and
   as data-quality work items — a student's identity is not a guess.
4. **Benchmarks are demographically contextualised** (ACSES method): compare
   against institutions with comparable equity share, not raw league tables.

## 5. Evaluation approach

Following the SEHEEF program logic: activities → outputs (students reached) →
outcomes (persistence, success) → impact (completion, equity-gap movement).
Attribution uses matched comparison (coarsened exact matching on the observable
triage variables), with the naive estimate shown only as an anti-example. In
Compass the method is validated against injected ground truth; in production,
the equivalent validation is a staged rollout or waitlist design agreed with
the evaluation owner.

## 6. What this framework asks of people (the honest part)

- **Advisors:** two extra dropdowns per case (SEHEEF activity, life stage) and
  an outcome field per contact. Everything else is derived.
- **Manager:** owns the definitions register and the alert-threshold review
  each term (thresholds are policy, not physics).
- **Data Excellence / IT:** source-extract schedules and a shared definitions
  alignment — the framework deliberately reuses institutional metric methods
  so there is nothing to arbitrate.
- **First Nations stakeholders:** any Indigenous-specific indicator or report
  view is co-designed, not defaulted (UNE/Oorala precedent; Indigenous Data
  Sovereignty principles).
