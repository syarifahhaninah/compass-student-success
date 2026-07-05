-- =========================================================================
-- 05 MARTS: decision-ready tables, one per dashboard question.
-- Metric definitions follow Department of Education methods and are
-- documented in docs/data-dictionary.md.
-- =========================================================================

-- ordered terms, for next-term lookups
CREATE OR REPLACE TABLE terms_ordered AS
SELECT term_code, row_number() OVER (ORDER BY term_start) AS term_seq, is_current
FROM dim_term;

-- ------------------------------------------------ executive overview ----
CREATE OR REPLACE TABLE mart_executive AS
SELECT
    e.term_code,
    e.campus_code,
    s.mode,
    p.field,
    count(DISTINCT e.student_id)                    AS headcount,
    round(sum(e.eftsl_certified), 1)                AS eftsl_certified,
    round(sum(e.eftsl_passed), 1)                   AS eftsl_passed,
    round(sum(e.eftsl_passed) / nullif(sum(e.eftsl_certified), 0), 4) AS success_rate,
    round(avg(CASE WHEN e.mark BETWEEN 0 AND 100 THEN e.mark END), 1) AS avg_mark,
    sum(CASE WHEN e.enrolment_status = 'Withdrawn pre-census' THEN 1 ELSE 0 END) AS withdrawals_pre_census
FROM fact_enrolment e
JOIN dim_student s USING (student_id)
JOIN dim_program p ON s.program_code = p.program_code
GROUP BY ALL;

-- --------------------------------------- retention by cohort and year ----
-- Institutional retention: commencing students in year Y with an enrolment
-- (or completion) in year Y+1. Not sector-adjusted (single institution);
-- the difference from DoE adjusted retention is documented.
CREATE OR REPLACE TABLE student_year_presence AS
SELECT student_id, CAST(substr(term_code, 1, 4) AS INTEGER) AS year
FROM fact_enrolment GROUP BY ALL;

CREATE OR REPLACE TABLE student_retention AS
SELECT
    d.student_id, d.commencing_year,
    CASE WHEN d.student_status = 'completed'
              OR EXISTS (SELECT 1 FROM student_year_presence p
                         WHERE p.student_id = d.student_id
                           AND p.year = d.commencing_year + 1)
         THEN 1 ELSE 0 END AS retained_y1
FROM dim_student d
WHERE d.citizenship = 'Domestic' AND d.commencing_year <= 2025;

CREATE OR REPLACE TABLE mart_retention_cohort AS
WITH labelled AS (
    SELECT r.*, 'All domestic' AS cohort FROM student_retention r
    UNION ALL
    SELECT r.*, 'Low SES' FROM student_retention r
    JOIN dim_student d USING (student_id) WHERE d.low_ses = 'Yes'
    UNION ALL
    SELECT r.*, 'First Nations' FROM student_retention r
    JOIN dim_student d USING (student_id) WHERE d.first_nations = 'Yes'
    UNION ALL
    SELECT r.*, 'Disability' FROM student_retention r
    JOIN dim_student d USING (student_id) WHERE d.disability = 'Yes'
    UNION ALL
    SELECT r.*, 'Regional/remote' FROM student_retention r
    JOIN dim_student d USING (student_id) WHERE d.regional_remote = 'Yes'
    UNION ALL
    SELECT r.*, 'Online' FROM student_retention r
    JOIN dim_student d USING (student_id) WHERE d.mode = 'Online'
    UNION ALL
    SELECT r.*, 'Non-equity' FROM student_retention r
    JOIN dim_student d USING (student_id)
    WHERE d.low_ses = 'No' AND d.first_nations = 'No'
      AND d.disability = 'No' AND d.regional_remote = 'No'
)
SELECT cohort, commencing_year,
       count(*) AS students,
       round(avg(retained_y1), 4) AS retention_rate
FROM labelled
GROUP BY ALL;

-- --------------------------------------------- NBF funding accountability ----
CREATE OR REPLACE TABLE mart_nbf_funding AS
WITH has_case AS (SELECT DISTINCT student_id FROM fact_case)
SELECT
    d.commencing_year,
    d.nbf_category,
    r.indicative_rate,
    count(*)                                    AS commencing_students,
    count(*) * r.indicative_rate                AS indicative_funding,
    sum(CASE WHEN h.student_id IS NOT NULL THEN 1 ELSE 0 END)
                                                AS students_with_support_case,
    round(avg(CASE WHEN h.student_id IS NOT NULL THEN 1.0 ELSE 0 END), 4)
                                                AS support_coverage
FROM dim_student d
JOIN ref_nbf_rates r USING (nbf_category)
LEFT JOIN has_case h ON d.student_id = h.student_id
WHERE d.nbf_category <> 'Not applicable'
GROUP BY d.commencing_year, d.nbf_category, r.indicative_rate;

-- SEHEEF program-logic rollup: acquittal reporting as a by-product
CREATE OR REPLACE TABLE mart_seheef_activity AS
SELECT
    CAST(substr(c.term_code, 1, 4) AS INTEGER)  AS year,
    c.seheef_activity,
    c.seheef_life_stage,
    c.case_type,
    d.nbf_equity_cohort,
    count(*)                                    AS cases,
    count(DISTINCT c.student_id)                AS students,
    round(avg(CASE WHEN c.contact_outcome LIKE 'Reached%' THEN 1.0 ELSE 0 END), 4)
                                                AS reach_rate
FROM fact_case c
JOIN dim_student d USING (student_id)
GROUP BY ALL;

-- ------------------------------------------------- advisor triage list ----
-- The Monday-morning question: who does each advisor contact this week?
CREATE OR REPLACE TABLE mart_triage_current AS
WITH cur AS (SELECT term_code FROM dim_term WHERE is_current),
alerts_cur AS (
    SELECT student_id,
           min(week_number)                          AS first_alert_week,
           max(week_number)                          AS latest_alert_week,
           count(*)                                  AS alert_count,
           string_agg(DISTINCT reason_code, ', ')    AS reasons,
           max(CASE WHEN lifecycle_status IN
               ('Actioned - case opened', 'Covered by same-term case')
               THEN 1 ELSE 0 END)                    AS contacted,
           max(case_status)                          AS case_status,
           max(contact_outcome)                      AS contact_outcome
    FROM fact_alert WHERE term_code IN (SELECT term_code FROM cur)
    GROUP BY student_id
),
recent AS (
    SELECT student_id,
           sum(logins)  AS logins_last2wk,
           sum(missed)  AS missed_last2wk
    FROM fact_engagement_week
    WHERE term_code IN (SELECT term_code FROM cur)
      AND week_number >= (SELECT max(week_number) - 1 FROM fact_engagement_week
                          WHERE term_code IN (SELECT term_code FROM cur))
    GROUP BY student_id
)
SELECT
    a.student_id,
    d.student_name, d.program_code, p.program_name,
    d.home_campus_code, d.mode, d.attendance_type,
    d.nbf_equity_cohort, d.first_nations, d.disability,
    (d.commencing_term = (SELECT term_code FROM cur)) AS is_commencing,
    a.first_alert_week, a.latest_alert_week, a.alert_count, a.reasons,
    a.contacted, a.case_status, a.contact_outcome,
    coalesce(r.logins_last2wk, 0)  AS logins_last2wk,
    coalesce(r.missed_last2wk, 0)  AS missed_last2wk,
    CASE
        WHEN a.contacted = 0 AND a.alert_count >= 2 THEN 'P1 - multiple signals, not yet contacted'
        WHEN a.contacted = 0 THEN 'P2 - single signal, not yet contacted'
        WHEN a.case_status IN ('Open', 'In progress') THEN 'P3 - support in progress'
        ELSE 'P4 - resolved / monitoring'
    END AS priority_tier,
    -- deterministic advisor assignment by campus coverage for uncontacted students
    coalesce(
        (SELECT c.advisor_id FROM fact_case c
         WHERE c.student_id = a.student_id
           AND c.term_code IN (SELECT term_code FROM cur)
         ORDER BY c.opened_date DESC LIMIT 1),
        (SELECT min(v.advisor_id) FROM dim_advisor v
         WHERE list_contains(string_split(v.covered_campuses, '|'), d.home_campus_code))
    ) AS advisor_id
FROM alerts_cur a
JOIN dim_student d USING (student_id)
JOIN dim_program p ON d.program_code = p.program_code
LEFT JOIN recent r ON a.student_id = r.student_id
WHERE d.student_status <> 'discontinued';

-- ------------------------------------- intervention effectiveness input ----
-- Past-term alerted student-terms with pre-alert covariates and next-term
-- outcome. Consumed by etl/effectiveness.py (coarsened exact matching).
-- Covariates are strictly PRE-treatment and include the observable triage
-- inputs (simultaneous reasons at first alert, inactivity at the alert) so
-- matching conditions on the actual assignment mechanism. Total alert count
-- is deliberately excluded: it is post-treatment.
CREATE OR REPLACE TABLE mart_effectiveness_input AS
WITH first_alert AS (
    SELECT a.student_id, a.term_code, min(a.week_number) AS alert_week
    FROM fact_alert a
    JOIN terms_ordered t USING (term_code)
    WHERE NOT t.is_current
    GROUP BY a.student_id, a.term_code
),
alerted AS (
    SELECT f.student_id, f.term_code, f.alert_week,
           count(*) FILTER (WHERE a.week_number = f.alert_week) AS reasons_at_alert,
           max(CASE WHEN a.lifecycle_status IN
               ('Actioned - case opened', 'Covered by same-term case')
               THEN 1 ELSE 0 END) AS contacted
    FROM first_alert f
    JOIN fact_alert a
      ON a.student_id = f.student_id AND a.term_code = f.term_code
    GROUP BY f.student_id, f.term_code, f.alert_week
),
at_alert AS (
    SELECT al.student_id, al.term_code,
           sum(CASE WHEN w.week_number >= al.alert_week - 1 THEN w.logins END)
                                        AS logins_2wk_at_alert,
           sum(CASE WHEN w.week_number < al.alert_week THEN w.missed ELSE 0 END)
                                        AS pre_missed
    FROM alerted al
    JOIN fact_engagement_week w
      ON w.student_id = al.student_id AND w.term_code = al.term_code
     AND w.week_number <= al.alert_week
    GROUP BY al.student_id, al.term_code
)
SELECT
    al.student_id, al.term_code, al.alert_week, al.reasons_at_alert, al.contacted,
    coalesce(x.logins_2wk_at_alert, 0)  AS logins_2wk_at_alert,
    coalesce(x.pre_missed, 0)           AS pre_missed,
    (d.mode = 'Online')                 AS online,
    (d.nbf_equity_cohort = 'Yes')       AS nbf_equity,
    (d.commencing_term = al.term_code)  AS first_term,
    CASE WHEN d.student_status = 'completed' THEN 1
         WHEN EXISTS (SELECT 1 FROM fact_enrolment e
                      JOIN terms_ordered t2 ON e.term_code = t2.term_code
                      WHERE e.student_id = al.student_id
                        AND t2.term_seq = t.term_seq + 1)
         THEN 1 ELSE 0 END              AS retained_next_term
FROM alerted al
JOIN terms_ordered t ON al.term_code = t.term_code
JOIN dim_student d ON al.student_id = d.student_id
LEFT JOIN at_alert x ON al.student_id = x.student_id AND al.term_code = x.term_code;

-- ----------------------------------------------------- data quality mart ----
CREATE OR REPLACE TABLE mart_dq_summary AS
SELECT rule_id, severity, table_name, count(*) AS issues
FROM dq_issues GROUP BY ALL
UNION ALL
SELECT 'quarantined_enrolment_rows', 'FATAL', 'banner_enrolments', count(*)
FROM rej_enrolments;

-- weekly engagement rollup for trend visuals
CREATE OR REPLACE TABLE mart_engagement_trend AS
SELECT w.term_code, w.week_number,
       d.mode, d.nbf_equity_cohort,
       count(DISTINCT w.student_id)        AS students,
       round(avg(w.logins), 2)             AS avg_logins,
       round(sum(w.missed) * 1.0 / nullif(sum(w.items_due), 0), 4) AS missed_rate
FROM fact_engagement_week w
JOIN dim_student d USING (student_id)
GROUP BY ALL;
