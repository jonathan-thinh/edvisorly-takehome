# Entity-Relationship Diagram

## Core Data Model

```mermaid
erDiagram
    INSTITUTION {
        uuid id PK
        text edvisorly_id UK
        enum institution_type
        timestamptz created_at
        text created_by
        text notes
    }

    INSTITUTION_VERSION {
        uuid id PK
        uuid institution_id FK
        text name
        text name_normalized
        text address_line1
        text city
        char state_code
        text zip_code
        text nces_id
        text ceeb_code
        enum status
        date valid_from
        date valid_to
        boolean is_current
        text source
        numeric confidence
        timestamptz updated_at
        jsonb metadata
    }

    INSTITUTION_ALIAS {
        uuid id PK
        uuid institution_id FK
        text alias_name
        text alias_normalized
        text alias_type
        text source
    }

    PARTNER {
        uuid id PK
        text code UK
        text name
        text data_format
        boolean is_active
    }

    PARTNER_CROSSWALK {
        uuid id PK
        uuid partner_id FK
        uuid institution_id FK
        text partner_school_id
        text partner_school_name
        text match_method
        numeric match_confidence
        boolean is_verified
        date valid_from
        date valid_to
    }

    CROSSWALK_AUDIT {
        uuid id PK
        uuid crosswalk_id FK
        text action
        jsonb old_values
        jsonb new_values
        text reason
        text performed_by
    }

    LIFECYCLE_EVENT {
        uuid id PK
        uuid institution_id FK
        enum event_type
        date event_date
        uuid related_institution_id FK
        text description
        text source
        boolean verified
    }

    SCHOOL_YEAR_REPORT {
        uuid id PK
        uuid institution_id FK
        int academic_year
        enum report_type
        jsonb data
        text source
        boolean is_verified
    }

    SCHOOL_DEMOGRAPHICS {
        uuid id PK
        uuid institution_id FK
        int academic_year
        int total_enrollment
        numeric pct_free_reduced_lunch
        text locale_code
    }

    MATCH_ATTEMPT {
        uuid id PK
        text input_name
        text input_name_normalized
        text input_state
        uuid partner_id FK
        date transcript_date
        uuid matched_institution_id FK
        enum match_status
        text match_method
        numeric confidence_score
        jsonb candidates
    }

    INSTITUTION ||--o{ INSTITUTION_VERSION : "has versions"
    INSTITUTION ||--o{ INSTITUTION_ALIAS : "has aliases"
    INSTITUTION ||--o{ PARTNER_CROSSWALK : "mapped by"
    INSTITUTION ||--o{ LIFECYCLE_EVENT : "has events"
    INSTITUTION ||--o{ SCHOOL_YEAR_REPORT : "has reports"
    INSTITUTION ||--o{ SCHOOL_DEMOGRAPHICS : "has demographics"
    INSTITUTION ||--o{ MATCH_ATTEMPT : "matched to"
    PARTNER ||--o{ PARTNER_CROSSWALK : "provides"
    PARTNER ||--o{ MATCH_ATTEMPT : "submits"
    PARTNER_CROSSWALK ||--o{ CROSSWALK_AUDIT : "audited by"
    LIFECYCLE_EVENT }o--|| INSTITUTION : "related to"
```

## Key Design Notes

1. **INSTITUTION** is the stable identity anchor — it never changes, only accumulates versions.
2. **INSTITUTION_VERSION** uses SCD Type 2 with `[valid_from, valid_to)` windows. `valid_to = NULL` means current.
3. **LIFECYCLE_EVENT** links institutions through merges/renames via `related_institution_id`.
4. **PARTNER_CROSSWALK** maps each partner's identifier to our canonical record, with confidence and verification tracking.
5. **MATCH_ATTEMPT** logs every matching attempt for auditability and model improvement.
