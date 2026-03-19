-- =============================================================================
-- School-by-Year Data (School Reports)
-- =============================================================================
-- Supports attaching per-year data to institutions: AP offerings, demographics,
-- class statistics, etc. Uses a flexible approach: a typed report table with
-- JSONB payload for extensibility, plus structured tables for common report types.
-- =============================================================================

CREATE TYPE report_type AS ENUM (
    'demographics',
    'ap_offerings',
    'class_statistics',
    'graduation_rates',
    'enrollment',
    'accreditation',
    'custom'
);

-- Flexible school-year report: one row per institution × year × report type
CREATE TABLE school_year_report (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id      UUID NOT NULL REFERENCES institution(id),
    academic_year       INT NOT NULL,  -- e.g. 2023 means the 2023-2024 academic year
    report_type         report_type NOT NULL,
    data                JSONB NOT NULL,
    source              TEXT NOT NULL,
    source_reference    TEXT,
    is_verified         BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          TEXT NOT NULL DEFAULT 'system'
);

CREATE INDEX idx_report_institution_year ON school_year_report(institution_id, academic_year);
CREATE INDEX idx_report_type ON school_year_report(report_type);
CREATE UNIQUE INDEX idx_report_unique
    ON school_year_report(institution_id, academic_year, report_type);

-- Structured demographics table for the most common use case
CREATE TABLE school_demographics (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id      UUID NOT NULL REFERENCES institution(id),
    academic_year       INT NOT NULL,
    total_enrollment    INT,
    grade_9_enrollment  INT,
    grade_10_enrollment INT,
    grade_11_enrollment INT,
    grade_12_enrollment INT,
    pct_free_reduced_lunch NUMERIC(5,2),
    pct_title_i        NUMERIC(5,2),
    locale_code         TEXT,          -- NCES locale code
    source              TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_demographics_unique
    ON school_demographics(institution_id, academic_year);
