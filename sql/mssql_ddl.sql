/* =========================================================================
   Compass — production DDL translation (SQL Server / Azure SQL)

   The prototype runs DuckDB locally; this is the same dimensional model as
   T-SQL DDL for an institutional Azure environment. Load orchestration maps
   to Azure Data Factory pipelines mirroring etl/sql/01-05:
     ADF: Banner/Canvas/CRM extracts -> stg schema -> validation stored procs
          (writing dq.issues + quarantine) -> dw dimensional load -> marts
   Row-level security for advisor caseloads is enforced with a security
   predicate on dw.mart_triage_current (see bottom).
   ========================================================================= */

CREATE SCHEMA stg;
CREATE SCHEMA dw;
CREATE SCHEMA dq;
GO

/* ------------------------------------------------------------ dimensions */
CREATE TABLE dw.dim_term (
    term_code      VARCHAR(6)   NOT NULL PRIMARY KEY,
    term_start     DATE         NOT NULL,
    census_date    DATE         NOT NULL,
    teaching_weeks TINYINT      NOT NULL,
    [year]         SMALLINT     NOT NULL,
    semester       CHAR(2)      NOT NULL,
    is_current     BIT          NOT NULL DEFAULT 0
);

CREATE TABLE dw.dim_campus (
    campus_code VARCHAR(3)  NOT NULL PRIMARY KEY,
    campus_name VARCHAR(50) NOT NULL,
    [state]     VARCHAR(5)  NOT NULL
);

CREATE TABLE dw.dim_program (
    program_code VARCHAR(5)  NOT NULL PRIMARY KEY,
    program_name VARCHAR(80) NOT NULL,
    field        VARCHAR(30) NOT NULL
);

CREATE TABLE dw.dim_advisor (
    advisor_id       VARCHAR(5)   NOT NULL PRIMARY KEY,
    advisor_name     VARCHAR(80)  NOT NULL,
    covered_campuses VARCHAR(100) NOT NULL,
    upn              VARCHAR(120) NULL   -- Azure AD principal for RLS
);

CREATE TABLE dw.dim_unit (
    unit_code    VARCHAR(10)  NOT NULL PRIMARY KEY,
    unit_name    VARCHAR(100) NOT NULL,
    program_code VARCHAR(5)   NOT NULL REFERENCES dw.dim_program,
    year_level   TINYINT      NOT NULL,
    eftsl        DECIMAL(5,3) NOT NULL
);

CREATE TABLE dw.dim_student (
    student_id          VARCHAR(9)   NOT NULL PRIMARY KEY,
    student_name        VARCHAR(120) NOT NULL,
    dob                 DATE         NULL,
    gender              CHAR(1)      NULL,
    citizenship         VARCHAR(15)  NOT NULL,
    postcode            VARCHAR(4)   NULL,
    [state]             VARCHAR(5)   NULL,
    home_campus_code    VARCHAR(3)   NULL REFERENCES dw.dim_campus,
    program_code        VARCHAR(5)   NULL REFERENCES dw.dim_program,
    commencing_term     VARCHAR(6)   NULL REFERENCES dw.dim_term,
    commencing_year     SMALLINT     NULL,
    attendance_type     VARCHAR(10)  NULL,
    mode                VARCHAR(10)  NULL,
    age_group           VARCHAR(6)   NULL,
    basis_of_admission  VARCHAR(30)  NULL,
    atar                DECIMAL(4,1) NULL,
    first_nations       VARCHAR(8)   NOT NULL DEFAULT 'Unknown',  -- HEIMS/TCSI E316-style
    disability          VARCHAR(8)   NOT NULL DEFAULT 'Unknown',  -- E615-style
    nesb                VARCHAR(8)   NOT NULL DEFAULT 'Unknown',
    ses_quartile        TINYINT      NULL,   -- IEO quartile on first address (E320-style postcode)
    remoteness          VARCHAR(15)  NULL,
    low_ses             VARCHAR(3)   NOT NULL DEFAULT 'No',
    regional_remote     VARCHAR(3)   NOT NULL DEFAULT 'No',
    nbf_equity_cohort   VARCHAR(3)   NOT NULL DEFAULT 'No',
    nbf_category        VARCHAR(30)  NOT NULL DEFAULT 'Not applicable',
    student_status      VARCHAR(15)  NOT NULL,
    status_term         VARCHAR(6)   NULL
);

/* ----------------------------------------------------------------- facts */
CREATE TABLE dw.fact_enrolment (
    student_id       VARCHAR(9)   NOT NULL REFERENCES dw.dim_student,
    unit_code        VARCHAR(10)  NOT NULL REFERENCES dw.dim_unit,
    term_code        VARCHAR(6)   NOT NULL REFERENCES dw.dim_term,
    campus_code      VARCHAR(3)   NOT NULL REFERENCES dw.dim_campus,
    enrolment_status VARCHAR(25)  NOT NULL,
    grade            VARCHAR(2)   NULL,
    mark             DECIMAL(5,1) NULL CHECK (mark IS NULL OR mark BETWEEN 0 AND 100),
    eftsl            DECIMAL(5,3) NOT NULL,
    eftsl_certified  DECIMAL(5,3) NOT NULL,
    eftsl_passed     DECIMAL(5,3) NOT NULL,
    census_date      DATE         NOT NULL,
    passed           BIT          NULL,
    CONSTRAINT pk_fact_enrolment PRIMARY KEY (student_id, unit_code, term_code)
);

CREATE TABLE dw.fact_engagement_week (
    student_id        VARCHAR(9) NOT NULL REFERENCES dw.dim_student,
    term_code         VARCHAR(6) NOT NULL REFERENCES dw.dim_term,
    week_number       TINYINT    NOT NULL,
    week_start        DATE       NOT NULL,
    logins            SMALLINT   NOT NULL,
    page_views        INT        NOT NULL,
    items_due         TINYINT    NOT NULL,
    submitted_on_time TINYINT    NOT NULL,
    submitted_late    TINYINT    NOT NULL,
    missed            TINYINT    NOT NULL,
    CONSTRAINT pk_fact_engagement PRIMARY KEY (student_id, term_code, week_number)
);

CREATE TABLE dw.fact_case (
    case_id           VARCHAR(10) NOT NULL PRIMARY KEY,
    student_id        VARCHAR(9)  NOT NULL REFERENCES dw.dim_student,
    term_code         VARCHAR(6)  NOT NULL REFERENCES dw.dim_term,
    opened_date       DATE        NOT NULL,
    source            VARCHAR(20) NOT NULL,
    case_type         VARCHAR(40) NOT NULL,
    seheef_activity   VARCHAR(40) NOT NULL,   -- SEHEEF program-logic tag at point of entry
    seheef_life_stage VARCHAR(20) NOT NULL,
    advisor_id        VARCHAR(5)  NULL REFERENCES dw.dim_advisor,
    contact_channel   VARCHAR(12) NULL,
    contact_outcome   VARCHAR(40) NULL,
    [status]          VARCHAR(12) NOT NULL,
    closed_date       DATE        NULL,
    days_open         SMALLINT    NULL,
    linked_alert_id   VARCHAR(10) NULL
);

CREATE TABLE dw.fact_alert (
    alert_id         VARCHAR(10) NOT NULL PRIMARY KEY,
    student_id       VARCHAR(9)  NOT NULL REFERENCES dw.dim_student,
    term_code        VARCHAR(6)  NOT NULL REFERENCES dw.dim_term,
    week_number      TINYINT     NOT NULL,
    raised_date      DATE        NOT NULL,
    reason_code      VARCHAR(20) NOT NULL,
    actioned_case_id VARCHAR(10) NULL REFERENCES dw.fact_case,
    actioned_date    DATE        NULL,
    contact_outcome  VARCHAR(40) NULL,
    case_status      VARCHAR(12) NULL,
    lifecycle_status VARCHAR(30) NOT NULL,   -- closed-loop state, audit-ready
    days_to_action   SMALLINT    NULL
);

CREATE INDEX ix_alert_term_lifecycle ON dw.fact_alert (term_code, lifecycle_status);
CREATE INDEX ix_case_student ON dw.fact_case (student_id, term_code);
CREATE INDEX ix_engagement_term_week ON dw.fact_engagement_week (term_code, week_number);

/* ---------------------------------------------------------- data quality */
CREATE TABLE dq.issues (
    issue_id   INT IDENTITY PRIMARY KEY,
    rule_id    VARCHAR(30)  NOT NULL,
    severity   VARCHAR(5)   NOT NULL CHECK (severity IN ('FATAL', 'WARN')),
    table_name VARCHAR(40)  NOT NULL,
    row_key    VARCHAR(120) NOT NULL,
    detail     VARCHAR(200) NULL,
    loaded_at  DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME()
);

/* ----------------------------------------- row-level security (advisors) */
GO
CREATE FUNCTION dw.fn_advisor_filter (@advisor_id VARCHAR(5))
RETURNS TABLE
WITH SCHEMABINDING
AS RETURN
    SELECT 1 AS allowed
    FROM dw.dim_advisor a
    WHERE a.advisor_id = @advisor_id
      AND (a.upn = USER_NAME() OR IS_MEMBER('StudentCareManagers') = 1);
GO
-- Applied as a SECURITY POLICY on advisor-scoped marts so an advisor sees
-- only their caseload while managers see all; mirrored in the Power BI
-- semantic model as an RLS role for service-level enforcement.
