# Traceability Matrix — Selection Criteria → Compass Artefacts

Position 10613480, Data Analyst, Student Care and Success (HEW 7). Each selection criterion in the position description maps to a concrete, inspectable artefact in this repository. Written **before** the build (test-driven): anything that doesn't serve a criterion is out of scope.

| # | Selection criterion (abridged) | Compass evidence | Where |
|---|---|---|---|
| 1 | Degree in data analytics / IS / CS / statistics or equivalent combination of education, training and experience | Master of IT (ACU) + this end-to-end build demonstrating the applied combination | Whole repository |
| 2 | Advanced analytical, problem-solving and technical skills: interrogate complex datasets, identify trends and risks, develop meaningful performance measures, communicate to technical and non-technical audiences | Reason-coded indicator engine; DoE-definition measure library; executive page designed for non-technical readers vs repo/docs for technical readers (layered disclosure) | `etl/` indicator engine · `powerbi/measures.dax` · dashboard pages |
| 3 | Build effective working relationships and collaborate across functional, technical and operational areas | Advisor-facing triage designed around case-management workflow; "one metric, one definition" dictionary written for alignment with a central data team; limitations section explicitly listing what must be co-designed with advisors and Indigenous education units | `docs/data-dictionary.md` · README limitations · triage page spec |
| 4 | Understanding of student information systems, CRM systems and higher-education data environments (Banner, CRM platforms, Microsoft data technologies, data warehouses) | Source extracts shaped as Banner SIS / Canvas LMS / CRM case data; DuckDB prototype with production T-SQL translation targeting an Azure + Power BI environment | `generator/` · `sql/mssql_ddl.sql` · README architecture |
| 5 | Analysing complex datasets and translating data into actionable insights supporting operational decision-making and service improvement | Every dashboard page is named for the operational decision it serves (who to contact this week; what to report; is it working) — decision-led design | `powerbi/page-guide.md` |
| 6 | Experience with higher-education data: student lifecycle, retention, progression, completion, enrolment, engagement, equity datasets | Full student-lifecycle dimensional model; retention/progression/completion/success measures per Department of Education definitions; TCSI-style equity flags (First Nations, low SES via IEO quartile, disability, regional/remote, NESB, first-in-family) | `etl/` star schema · `docs/data-dictionary.md` |
| 7 | Developing dashboards, visualisations and reporting solutions with Power BI, Tableau or equivalent | Five-page Power BI suite: executive, equity/NBF acquittal, advisor triage (with row-level security), intervention effectiveness, data quality | `powerbi/` |
| 8 | Integrating, extracting, transforming and managing data from multiple systems; data warehousing, system integration, data modelling | Three heterogeneous source systems → staged, validated (rejected-rows log) → conformed star schema; documented ERD; defect injection + quality reporting demonstrating governance controls | `etl/` · `data/quality/` · `docs/erd.md` |

## Core competencies and essential attributes

| Competency | Compass evidence |
|---|---|
| Connect work to ACU's Mission, Vision and Values | Ethics note framing analytics as an instrument of care ("support-first, not deficit-labelling"), aligned to the dignity of the human person and Vision 2033 |
| Collaborate to capitalise on available expertise | Design provenance: every decision cites documented sector practice rather than invented from scratch |
| Communicate with purpose to technical and non-technical audiences | Layered disclosure: one-page summary → README + video → full repo |
| Plan work, prioritise time and resources | Two-stage build plan with self-contained deliverables at each stage (documented in project approach) |
| Make informed, evidence-based decisions | `docs/design-provenance.md` — the decision log with sources |
| Commitment to cultural diversity and ethical practice | Fairness audit across equity cohorts; UNE/Oorala co-design precedent acknowledged as a prototype limitation; synthetic-data privacy stance |

## Regulatory obligations → artefacts

| Obligation | Compass evidence |
|---|---|
| Support for Students Policy (HEP Guidelines Ch 10A) — identify at-risk students, evidence support delivered | Closed-loop alert lifecycle: every alert carries states raised → triaged → contacted → outcome → re-assessed |
| TEQSA compliance focus — leading indicators, not post-mortems | Weekly engagement-based indicators (non-submission, inactivity) rather than end-of-semester grades |
| NBF acquittal (due early 2027) per SEHEEF program logic | Every case record tagged to a SEHEEF activity type and student life stage at point of entry; acquittal page aggregates directly from operational data |
| Data governance / definition alignment | Data dictionary with TCSI-style element references and DoE metric methods |
