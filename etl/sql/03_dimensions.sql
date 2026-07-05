-- =========================================================================
-- 03 DIMENSIONS: conformed dimensions with derived NBF cohort attributes.
-- Low SES and regional status are DERIVED from postcode (IEO-quartile-style
-- lookup on first recorded address), mirroring the Needs-based Funding
-- methodology — they are never taken from the student record itself.
-- =========================================================================

CREATE OR REPLACE TABLE dim_term (
    term_code VARCHAR PRIMARY KEY, term_start DATE, census_date DATE,
    teaching_weeks INTEGER, year INTEGER, semester VARCHAR, is_current BOOLEAN
);
INSERT INTO dim_term VALUES
    ('2023S1', DATE '2023-02-27', DATE '2023-03-24', 13, 2023, 'S1', false),
    ('2023S2', DATE '2023-07-24', DATE '2023-08-18', 13, 2023, 'S2', false),
    ('2024S1', DATE '2024-02-26', DATE '2024-03-22', 13, 2024, 'S1', false),
    ('2024S2', DATE '2024-07-22', DATE '2024-08-16', 13, 2024, 'S2', false),
    ('2025S1', DATE '2025-02-24', DATE '2025-03-21', 13, 2025, 'S1', false),
    ('2025S2', DATE '2025-07-21', DATE '2025-08-15', 13, 2025, 'S2', false),
    ('2026S1', DATE '2026-02-23', DATE '2026-03-20', 13, 2026, 'S1', true);

CREATE OR REPLACE TABLE dim_campus (
    campus_code VARCHAR PRIMARY KEY, campus_name VARCHAR, state VARCHAR
);
INSERT INTO dim_campus VALUES
    ('NSY', 'North Sydney', 'NSW'), ('STR', 'Strathfield', 'NSW'),
    ('BLK', 'Blacktown', 'NSW'), ('MEL', 'Melbourne', 'VIC'),
    ('BAL', 'Ballarat', 'VIC'), ('BRI', 'Brisbane', 'QLD'),
    ('CAN', 'Canberra', 'ACT'), ('ONL', 'Online', 'MULTI');

CREATE OR REPLACE TABLE dim_program (
    program_code VARCHAR PRIMARY KEY, program_name VARCHAR, field VARCHAR
);
INSERT INTO dim_program VALUES
    ('BNURS', 'Bachelor of Nursing', 'Health'),
    ('BEDPR', 'Bachelor of Education (Primary)', 'Education'),
    ('BEDSE', 'Bachelor of Education (Secondary)', 'Education'),
    ('BPHYS', 'Bachelor of Physiotherapy', 'Health'),
    ('BOCCT', 'Bachelor of Occupational Therapy', 'Health'),
    ('BSOCW', 'Bachelor of Social Work', 'Health'),
    ('BPSYC', 'Bachelor of Psychological Science', 'Health'),
    ('BEXSC', 'Bachelor of Exercise and Sports Science', 'Health'),
    ('BPARA', 'Bachelor of Paramedicine', 'Health'),
    ('BBUSI', 'Bachelor of Business Administration', 'Business'),
    ('BINFT', 'Bachelor of Information Technology', 'STEM'),
    ('BLAWS', 'Bachelor of Laws', 'Law'),
    ('BARTS', 'Bachelor of Arts', 'Arts');

CREATE OR REPLACE TABLE dim_advisor AS
SELECT advisor_id, advisor_name, campuses AS covered_campuses
FROM stg_advisors;

CREATE OR REPLACE TABLE dim_unit AS
SELECT unit_code, unit_name, program_code, year_level, eftsl FROM stg_units;

CREATE OR REPLACE TABLE dim_student AS
SELECT
    s.student_id,
    s.first_name, s.last_name,
    s.first_name || ' ' || s.last_name       AS student_name,
    s.dob, s.gender, s.citizenship, s.postcode, s.state,
    s.campus_code_raw                        AS home_campus_code,
    s.program_code, s.commencing_term,
    CAST(substr(s.commencing_term, 1, 4) AS INTEGER) AS commencing_year,
    s.attendance_type, s.mode, s.age_group, s.basis_of_admission, s.atar,
    s.first_nations, s.disability, s.nesb,
    p.ses_quartile,
    p.remoteness,
    -- NBF-style derivations from first recorded address
    CASE WHEN s.citizenship = 'Domestic' AND p.ses_quartile = 1
         THEN 'Yes' ELSE 'No' END            AS low_ses,
    CASE WHEN s.citizenship = 'Domestic'
              AND p.remoteness IN ('Regional', 'Remote')
         THEN 'Yes' ELSE 'No' END            AS regional_remote,
    CASE WHEN s.citizenship = 'Domestic'
              AND (p.ses_quartile = 1 OR s.first_nations = 'Yes')
         THEN 'Yes' ELSE 'No' END            AS nbf_equity_cohort,
    -- indicative NBF funding category (commencing rate logic)
    CASE
        WHEN s.citizenship <> 'Domestic' THEN 'Not applicable'
        WHEN p.ses_quartile = 1 AND s.first_nations = 'Yes' THEN 'Low SES + First Nations'
        WHEN s.first_nations = 'Yes' THEN 'First Nations'
        WHEN p.ses_quartile = 1 AND coalesce(s.atar, 0) >= 80 THEN 'Low SES (high preparedness)'
        WHEN p.ses_quartile = 1 THEN 'Low SES'
        ELSE 'Not applicable'
    END                                      AS nbf_category,
    s.student_status, s.status_term
FROM stg_students_dedup s
LEFT JOIN stg_postcode p ON s.postcode = p.postcode;

-- Indicative per-commencing-student NBF contribution rates (2026 guidance)
CREATE OR REPLACE TABLE ref_nbf_rates (nbf_category VARCHAR, indicative_rate INTEGER);
INSERT INTO ref_nbf_rates VALUES
    ('Low SES', 4124),
    ('Low SES (high preparedness)', 1535),
    ('First Nations', 4860),
    ('Low SES + First Nations', 5819),
    ('Not applicable', 0);
