-- =============================================================================
-- Core Institution Tables
-- =============================================================================
-- Design: SCD Type 2 with explicit valid_from/valid_to windows.
-- An "institution" is the stable identity anchor (never changes).
-- "institution_version" captures how a school's attributes evolve over time.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- trigram index support for fuzzy search

-- Enum for institution type, supporting the HS vs CC distinction
CREATE TYPE institution_type AS ENUM (
    'high_school',
    'community_college',
    'vocational',
    'alternative',
    'charter',
    'magnet',
    'online',
    'unknown'
);

CREATE TYPE institution_status AS ENUM (
    'active',
    'closed',
    'merged',
    'renamed',
    'unknown'
);

-- Stable identity anchor — one row per logical institution across all time
CREATE TABLE institution (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    edvisorly_id    TEXT UNIQUE NOT NULL,  -- human-readable internal ID, e.g. "EDV-HS-00042"
    institution_type institution_type NOT NULL DEFAULT 'high_school',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT NOT NULL DEFAULT 'system',
    notes           TEXT
);

CREATE INDEX idx_institution_type ON institution(institution_type);
CREATE INDEX idx_institution_edvisorly_id ON institution(edvisorly_id);

-- Versioned attributes — SCD Type 2
-- Each row is a "snapshot" of the school's identity during [valid_from, valid_to)
CREATE TABLE institution_version (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id  UUID NOT NULL REFERENCES institution(id),
    name            TEXT NOT NULL,
    name_normalized TEXT NOT NULL,  -- lowercased, abbreviations expanded, punctuation stripped
    address_line1   TEXT,
    address_line2   TEXT,
    city            TEXT,
    state_code      CHAR(2),
    zip_code        TEXT,
    county          TEXT,
    country_code    CHAR(2) DEFAULT 'US',
    phone           TEXT,
    website         TEXT,
    nces_id         TEXT,            -- National Center for Education Statistics ID
    ceeb_code       TEXT,            -- College Board CEEB/ACT code
    status          institution_status NOT NULL DEFAULT 'active',
    valid_from      DATE NOT NULL,
    valid_to        DATE,            -- NULL means "current"
    is_current      BOOLEAN GENERATED ALWAYS AS (valid_to IS NULL) STORED,
    source          TEXT NOT NULL,    -- e.g. 'nces_import', 'partner_abc', 'manual_edit'
    confidence      NUMERIC(5,4) CHECK (confidence BETWEEN 0 AND 1),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT NOT NULL DEFAULT 'system',
    metadata        JSONB DEFAULT '{}'::JSONB
);

CREATE INDEX idx_version_institution ON institution_version(institution_id);
CREATE INDEX idx_version_current ON institution_version(institution_id) WHERE valid_to IS NULL;
CREATE INDEX idx_version_name_normalized ON institution_version USING gin(name_normalized gin_trgm_ops);
CREATE INDEX idx_version_nces ON institution_version(nces_id) WHERE nces_id IS NOT NULL;
CREATE INDEX idx_version_ceeb ON institution_version(ceeb_code) WHERE ceeb_code IS NOT NULL;
CREATE INDEX idx_version_state ON institution_version(state_code);
CREATE INDEX idx_version_temporal ON institution_version(institution_id, valid_from, valid_to);

-- Constraint: no overlapping validity windows for the same institution
CREATE OR REPLACE FUNCTION check_no_version_overlap()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM institution_version
        WHERE institution_id = NEW.institution_id
          AND id != NEW.id
          AND valid_from < COALESCE(NEW.valid_to, '9999-12-31'::DATE)
          AND COALESCE(valid_to, '9999-12-31'::DATE) > NEW.valid_from
    ) THEN
        RAISE EXCEPTION 'Overlapping validity window for institution %', NEW.institution_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_version_no_overlap
    BEFORE INSERT OR UPDATE ON institution_version
    FOR EACH ROW EXECUTE FUNCTION check_no_version_overlap();

-- Alias table: known alternate names, abbreviations, OCR variants
CREATE TABLE institution_alias (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id  UUID NOT NULL REFERENCES institution(id),
    alias_name      TEXT NOT NULL,
    alias_normalized TEXT NOT NULL,
    alias_type      TEXT NOT NULL DEFAULT 'alternate',  -- 'alternate', 'abbreviation', 'ocr_variant', 'former_name'
    source          TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_alias_institution ON institution_alias(institution_id);
CREATE INDEX idx_alias_normalized ON institution_alias USING gin(alias_normalized gin_trgm_ops);
