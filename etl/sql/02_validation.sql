-- =========================================================================
-- 02 VALIDATION: every rule writes to dq_issues; fatal rows are quarantined
-- to rej_* tables and excluded from facts. Nothing is silently dropped —
-- the data-quality page reports every issue and the quarantine counts.
-- =========================================================================

CREATE OR REPLACE TABLE dq_issues (
    rule_id     VARCHAR,
    severity    VARCHAR,   -- FATAL row quarantined | WARN row kept, flagged
    table_name  VARCHAR,
    row_key     VARCHAR,
    detail      VARCHAR
);

-- R01: duplicate person records (from survivorship analysis)
INSERT INTO dq_issues
SELECT 'R01_duplicate_student', 'FATAL', 'banner_students',
       duplicate_id, 'merged into ' || surviving_id
FROM student_id_survivorship;

-- R02: mark outside 0-100 on a graded record
INSERT INTO dq_issues
SELECT 'R02_mark_out_of_range', 'FATAL', 'banner_enrolments',
       student_id || '|' || unit_code || '|' || term_code,
       'mark=' || CAST(mark AS VARCHAR)
FROM stg_enrolments
WHERE mark IS NOT NULL AND (mark < 0 OR mark > 100);

-- R03: campus code not resolvable to a canonical campus
INSERT INTO dq_issues
SELECT 'R03_unknown_campus', 'FATAL', 'banner_enrolments',
       student_id || '|' || unit_code || '|' || term_code,
       'campus_code=' || campus_code_raw
FROM stg_enrolments
WHERE campus_code NOT IN (SELECT DISTINCT canonical FROM campus_synonyms);

-- R04: missing equity flag (kept, reported as Unknown — never guessed)
INSERT INTO dq_issues
SELECT 'R04_missing_equity_flag', 'WARN', 'banner_students', student_id,
       CASE WHEN first_nations = 'Unknown' THEN 'first_nations_flag' ELSE 'disability_flag' END
FROM stg_students_dedup
WHERE first_nations = 'Unknown' OR disability = 'Unknown';

-- R05: unparseable or implausible date of birth
INSERT INTO dq_issues
SELECT 'R05_dob_implausible', 'WARN', 'banner_students', student_id,
       coalesce(CAST(dob AS VARCHAR), 'unparseable')
FROM stg_students_dedup
WHERE dob IS NULL OR dob > DATE '2011-01-01' OR dob < DATE '1936-01-01';

-- R06: enrolment rows for students missing from the student extract
INSERT INTO dq_issues
SELECT 'R06_orphan_enrolment', 'FATAL', 'banner_enrolments',
       e.student_id || '|' || e.unit_code || '|' || e.term_code, 'no student record'
FROM stg_enrolments e
LEFT JOIN stg_students s ON e.student_id = s.student_id
WHERE s.student_id IS NULL;

-- R07: activity rows referencing unknown students (referential integrity)
INSERT INTO dq_issues
SELECT 'R07_orphan_activity', 'FATAL', 'canvas_activity',
       a.student_id || '|' || a.term_code || '|' || CAST(a.week_number AS VARCHAR),
       'no student record'
FROM stg_activity a
LEFT JOIN stg_students s ON a.student_id = s.student_id
WHERE s.student_id IS NULL;

-- Quarantine fatal enrolment rows
CREATE OR REPLACE TABLE rej_enrolments AS
SELECT e.*,
       CASE
           WHEN e.mark IS NOT NULL AND (e.mark < 0 OR e.mark > 100) THEN 'R02_mark_out_of_range'
           WHEN e.campus_code NOT IN (SELECT DISTINCT canonical FROM campus_synonyms) THEN 'R03_unknown_campus'
           ELSE 'R06_orphan_enrolment'
       END AS reject_rule
FROM stg_enrolments e
LEFT JOIN stg_students s ON e.student_id = s.student_id
WHERE (e.mark IS NOT NULL AND (e.mark < 0 OR e.mark > 100))
   OR e.campus_code NOT IN (SELECT DISTINCT canonical FROM campus_synonyms)
   OR s.student_id IS NULL;

CREATE OR REPLACE TABLE stg_enrolments_clean AS
SELECT e.* FROM stg_enrolments e
ANTI JOIN rej_enrolments r
    ON e.student_id = r.student_id AND e.unit_code = r.unit_code
   AND e.term_code = r.term_code;
