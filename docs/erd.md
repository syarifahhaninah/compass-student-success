# Compass Warehouse ERD

```mermaid
erDiagram
    dim_student ||--o{ fact_enrolment : "student_id"
    dim_student ||--o{ fact_engagement_week : "student_id"
    dim_student ||--o{ fact_case : "student_id"
    dim_student ||--o{ fact_alert : "student_id"
    dim_term ||--o{ fact_enrolment : "term_code"
    dim_term ||--o{ fact_engagement_week : "term_code"
    dim_term ||--o{ fact_case : "term_code"
    dim_term ||--o{ fact_alert : "term_code"
    dim_campus ||--o{ fact_enrolment : "campus_code"
    dim_unit ||--o{ fact_enrolment : "unit_code"
    dim_program ||--o{ dim_unit : "program_code"
    dim_program ||--o{ dim_student : "program_code"
    dim_advisor ||--o{ fact_case : "advisor_id"
    fact_alert ||--o| fact_case : "actioned_case_id (closed loop)"

    dim_student {
        varchar student_id PK
        varchar student_name
        varchar citizenship
        varchar postcode
        int ses_quartile "derived from postcode"
        varchar low_ses "derived, NBF method"
        varchar regional_remote "derived"
        varchar nbf_category
        varchar first_nations "E316-style"
        varchar disability "E615-style"
        varchar mode
        varchar commencing_term
        varchar student_status
    }
    fact_enrolment {
        varchar student_id FK
        varchar unit_code FK
        varchar term_code FK
        varchar grade
        double mark
        double eftsl_certified
        double eftsl_passed
    }
    fact_engagement_week {
        varchar student_id FK
        varchar term_code FK
        int week_number
        int logins
        int missed
    }
    fact_alert {
        varchar alert_id PK
        varchar student_id FK
        varchar reason_code
        varchar lifecycle_status "closed loop"
        varchar actioned_case_id FK
        int days_to_action
    }
    fact_case {
        varchar case_id PK
        varchar student_id FK
        varchar seheef_activity "tagged at entry"
        varchar seheef_life_stage
        varchar advisor_id FK
        varchar status
        varchar linked_alert_id
    }
```

**Flow:** raw extracts (Banner/Canvas/CRM-shaped) → staging (format repair,
synonym mapping, survivorship dedupe) → validation (dq_issues + quarantine) →
dimensions (NBF derivations) → facts (closed-loop alert lifecycle) → marts
(one per dashboard decision).
