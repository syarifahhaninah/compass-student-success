-- =========================================================================
-- 01 STAGING: land raw extracts, standardise formats, resolve known chaos.
-- Everything lands as VARCHAR first (institutional extracts lie about types),
-- then is cast deliberately with TRY_CAST so bad values surface as NULLs to
-- be caught by validation, never silently coerced.
-- =========================================================================

CREATE OR REPLACE TABLE stg_postcode AS
SELECT postcode, state, CAST(ses_quartile AS INTEGER) AS ses_quartile, remoteness
FROM read_csv('data/raw/ref_postcode_ses.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE stg_units AS
SELECT unit_code, unit_name, program_code,
       CAST(year_level AS INTEGER) AS year_level,
       CAST(eftsl AS DOUBLE) AS eftsl
FROM read_csv('data/raw/ref_units.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE stg_advisors AS
SELECT advisor_id, advisor_name, campuses
FROM read_csv('data/raw/ref_advisors.csv', header = true, all_varchar = true);

-- Campus synonym table: the cleansing rule set for source-system code drift.
CREATE OR REPLACE TABLE campus_synonyms (variant VARCHAR, canonical VARCHAR);
INSERT INTO campus_synonyms VALUES
    ('NSY', 'NSY'), ('NORTH SYDNEY', 'NSY'), ('NTH SYDNEY', 'NSY'),
    ('STR', 'STR'), ('STRATHFIELD', 'STR'), ('STRATH', 'STR'),
    ('BLK', 'BLK'), ('BLACKTOWN', 'BLK'),
    ('MEL', 'MEL'), ('MELBOURNE', 'MEL'), ('MELB', 'MEL'),
    ('BAL', 'BAL'), ('BALLARAT', 'BAL'),
    ('BRI', 'BRI'), ('BRISBANE', 'BRI'), ('BRIS', 'BRI'),
    ('CAN', 'CAN'), ('CANBERRA', 'CAN'),
    ('ONL', 'ONL'), ('ONLINE', 'ONL');

CREATE OR REPLACE MACRO proper_case(s) AS
    upper(substr(lower(trim(s)), 1, 1)) || substr(lower(trim(s)), 2);

CREATE OR REPLACE TABLE stg_students AS
SELECT
    trim(student_id)                                   AS student_id,
    -- names arrive with stray whitespace and case noise
    proper_case(first_name)                            AS first_name,
    trim(last_name)                                    AS last_name,
    -- dob arrives in two formats (ISO and DD/MM/YYYY)
    CASE
        WHEN dob LIKE '%/%' THEN TRY_CAST(strptime(dob, '%d/%m/%Y') AS DATE)
        ELSE TRY_CAST(dob AS DATE)
    END                                                AS dob,
    gender, citizenship, postcode, state,
    upper(trim(campus_code))                           AS campus_code_raw,
    program_code, commencing_term, attendance_type, mode, age_group,
    basis_of_admission,
    TRY_CAST(atar AS DOUBLE)                           AS atar,
    CASE first_nations_flag WHEN 'Y' THEN 'Yes' WHEN 'N' THEN 'No'
         ELSE 'Unknown' END                            AS first_nations,
    CASE disability_flag WHEN 'Y' THEN 'Yes' WHEN 'N' THEN 'No'
         ELSE 'Unknown' END                            AS disability,
    CASE nesb_flag WHEN 'Y' THEN 'Yes' WHEN 'N' THEN 'No'
         ELSE 'Unknown' END                            AS nesb,
    student_status, status_term
FROM read_csv('data/raw/banner_students.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE stg_enrolments AS
SELECT
    trim(e.student_id)                                 AS student_id,
    e.unit_code, e.term_code,
    coalesce(cs.canonical, upper(trim(e.campus_code))) AS campus_code,
    upper(trim(e.campus_code))                         AS campus_code_raw,
    e.enrolment_status, e.grade,
    TRY_CAST(e.mark AS DOUBLE)                         AS mark,
    TRY_CAST(e.eftsl AS DOUBLE)                        AS eftsl,
    TRY_CAST(e.census_date AS DATE)                    AS census_date
FROM read_csv('data/raw/banner_enrolments.csv', header = true, all_varchar = true) e
LEFT JOIN campus_synonyms cs ON upper(trim(e.campus_code)) = cs.variant;

CREATE OR REPLACE TABLE stg_activity AS
SELECT
    student_id, term_code,
    CAST(week_number AS INTEGER)        AS week_number,
    CAST(week_start AS DATE)            AS week_start,
    CAST(logins AS INTEGER)             AS logins,
    CAST(page_views AS INTEGER)         AS page_views,
    CAST(items_due AS INTEGER)          AS items_due,
    CAST(submitted_on_time AS INTEGER)  AS submitted_on_time,
    CAST(submitted_late AS INTEGER)     AS submitted_late,
    CAST(missed AS INTEGER)             AS missed
FROM read_csv('data/raw/canvas_activity.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE stg_cases AS
SELECT
    case_id, student_id, term_code,
    TRY_CAST(opened_date AS DATE)       AS opened_date,
    source, case_type, seheef_activity, seheef_life_stage,
    advisor_id, contact_channel, contact_outcome, status,
    TRY_CAST(closed_date AS DATE)       AS closed_date,
    nullif(linked_alert_id, '')         AS linked_alert_id
FROM read_csv('data/raw/crm_cases.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE stg_alerts AS
SELECT
    alert_id, student_id, term_code,
    CAST(week_number AS INTEGER)        AS week_number,
    TRY_CAST(raised_date AS DATE)       AS raised_date,
    reason_code
FROM read_csv('data/raw/alerts_history.csv', header = true, all_varchar = true);

-- ------------------------------------------------------- deduplication ----
-- Shell duplicate person records: same (name, dob, program, commencing term),
-- different IDs. Keep the ID that actually has enrolments (or the lowest ID),
-- map the rest to it. Real Banner cleanups follow the same survivorship rule.
CREATE OR REPLACE TABLE student_dupe_groups AS
SELECT first_name, last_name, dob, program_code, commencing_term,
       list(student_id ORDER BY student_id) AS ids
FROM stg_students
GROUP BY ALL
HAVING count(*) > 1;

CREATE OR REPLACE TABLE student_id_survivorship AS
WITH exploded AS (
    SELECT unnest(ids) AS student_id, ids FROM student_dupe_groups
), scored AS (
    SELECT e.student_id, e.ids,
           EXISTS (SELECT 1 FROM stg_enrolments en
                   WHERE en.student_id = e.student_id) AS has_enrolments
    FROM exploded e
)
SELECT s.student_id AS duplicate_id,
       coalesce(
           (SELECT min(s2.student_id) FROM scored s2
            WHERE s2.ids = s.ids AND s2.has_enrolments),
           list_min(s.ids)
       ) AS surviving_id
FROM scored s
WHERE s.student_id <> coalesce(
    (SELECT min(s2.student_id) FROM scored s2
     WHERE s2.ids = s.ids AND s2.has_enrolments),
    list_min(s.ids));

CREATE OR REPLACE TABLE stg_students_dedup AS
SELECT * FROM stg_students
WHERE student_id NOT IN (SELECT duplicate_id FROM student_id_survivorship);
