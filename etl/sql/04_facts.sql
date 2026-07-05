-- =========================================================================
-- 04 FACTS: conformed fact tables. Duplicate student IDs are remapped to
-- their surviving ID everywhere, so downstream joins never see the merge.
-- =========================================================================

CREATE OR REPLACE MACRO surviving(sid) AS
    coalesce((SELECT surviving_id FROM student_id_survivorship WHERE duplicate_id = sid), sid);

CREATE OR REPLACE TABLE fact_enrolment AS
SELECT
    surviving(e.student_id)               AS student_id,
    e.unit_code, e.term_code, e.campus_code,
    e.enrolment_status, e.grade, e.mark, e.eftsl, e.census_date,
    CASE WHEN e.grade IN ('HD', 'DI', 'CR', 'PA') THEN true
         WHEN e.grade IN ('NN', 'WN') THEN false END          AS passed,
    -- EFTSL certified at census: everything except pre-census withdrawal
    CASE WHEN e.enrolment_status <> 'Withdrawn pre-census'
         THEN e.eftsl ELSE 0 END                              AS eftsl_certified,
    CASE WHEN e.grade IN ('HD', 'DI', 'CR', 'PA')
         THEN e.eftsl ELSE 0 END                              AS eftsl_passed
FROM stg_enrolments_clean e;

CREATE OR REPLACE TABLE fact_engagement_week AS
SELECT
    surviving(a.student_id) AS student_id,
    a.term_code, a.week_number, a.week_start,
    a.logins, a.page_views, a.items_due,
    a.submitted_on_time, a.submitted_late, a.missed
FROM stg_activity a
SEMI JOIN stg_students s ON a.student_id = s.student_id;

CREATE OR REPLACE TABLE fact_case AS
SELECT
    c.case_id,
    surviving(c.student_id) AS student_id,
    c.term_code, c.opened_date, c.source, c.case_type,
    c.seheef_activity, c.seheef_life_stage,
    c.advisor_id, c.contact_channel, c.contact_outcome, c.status,
    c.closed_date,
    CASE WHEN c.closed_date IS NOT NULL
         THEN c.closed_date - c.opened_date END AS days_open,
    c.linked_alert_id
FROM stg_cases c;

-- Closed-loop alert lifecycle: every alert carries its follow-through state.
CREATE OR REPLACE TABLE fact_alert AS
WITH case_by_alert AS (
    SELECT linked_alert_id, min(case_id) AS case_id
    FROM stg_cases WHERE linked_alert_id IS NOT NULL
    GROUP BY linked_alert_id
),
-- a student-term counts as contacted if ANY of its alerts led to a case
contacted_terms AS (
    SELECT DISTINCT surviving(c.student_id) AS student_id, c.term_code
    FROM stg_cases c WHERE c.source = 'Early alert'
)
SELECT
    a.alert_id,
    surviving(a.student_id)  AS student_id,
    a.term_code, a.week_number, a.raised_date, a.reason_code,
    cb.case_id               AS actioned_case_id,
    fc.opened_date           AS actioned_date,
    fc.contact_outcome,
    fc.status                AS case_status,
    CASE
        WHEN cb.case_id IS NOT NULL THEN 'Actioned - case opened'
        WHEN ct.student_id IS NOT NULL THEN 'Covered by same-term case'
        WHEN t.is_current THEN 'Open - awaiting triage'
        ELSE 'Monitored - no contact'
    END                      AS lifecycle_status,
    CASE WHEN fc.opened_date IS NOT NULL
         THEN fc.opened_date - a.raised_date END AS days_to_action
FROM stg_alerts a
LEFT JOIN case_by_alert cb ON a.alert_id = cb.linked_alert_id
LEFT JOIN fact_case fc ON cb.case_id = fc.case_id
LEFT JOIN contacted_terms ct
       ON surviving(a.student_id) = ct.student_id AND a.term_code = ct.term_code
JOIN dim_term t ON a.term_code = t.term_code;
