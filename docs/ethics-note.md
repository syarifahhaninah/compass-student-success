# Data Ethics and the Dignity of the Person

*How Compass treats students in data — one page, written before the first row was generated.*

Student-success analytics sits inside a duty of care. A university that watches its students' data owes them more, not less, respect than one that doesn't. Compass adopts seven commitments, drawn from the Jisc Code of Practice for Learning Analytics, the ethics-of-care literature (Prinsloo & Slade), and the lessons of documented failures in the sector.

**1. Support-first, never deficit-labelling.** The system never describes a student as "likely to fail." Indicators identify students *who may benefit from support*, and the advisor-facing language reflects that. Labels shape belonging; belonging shapes outcomes.

**2. Transparent reasons, not opaque scores.** Every alert carries plain-language reason codes an advisor can read aloud to the student ("we noticed you haven't submitted assessment 2"). No single-number risk scores. The 2021 Markup investigation — where an advising platform used race as a predictor and no advisor knew — is the permanent counterexample.

**3. Behaviour predicts; demographics never do.** Engagement and academic behaviour drive indicators. Equity attributes (First Nations status, SES, disability, regional/remote) are used only to contextualise support offers, weight funding accountability, and audit fairness — never as inputs to risk flags.

**4. Fairness is audited in the open.** Alert rates, contact rates and post-contact outcomes are reported by equity cohort inside the reporting suite itself. Disparate impact should be discovered by the team, on purpose, before anyone else discovers it by accident. *(Implemented: `etl/fairness_audit.py` → `mart_fairness_audit.csv` — alert rates track behavioural need; treatment given an alert is flat across cohorts, max gap 0.9pp.)*

**5. A human decides; the system remembers.** Alerts prompt human judgment — they never trigger automated consequences. What the system does enforce is memory: every alert has a recorded outcome, because unactioned care is the sector's most common failure and an audit risk under the Support for Students Policy.

**6. Data minimisation and role-based visibility.** Advisors see their own caseload; managers see aggregates; identified wellbeing detail stays in the case-management layer. The prototype demonstrates row-level security for exactly this reason.

**7. First Nations data requires First Nations governance.** Following the UNE/Oorala precedent and Indigenous Data Sovereignty principles, any Indigenous-specific indicator design belongs to consultation with Indigenous education units and communities — a prototype can flag the need but must not pre-empt the design.

*And one meta-commitment:* this entire repository runs on synthetic data. Real student records are too sensitive for a portfolio artefact; demonstrating that judgment is part of demonstrating fitness for the role.
