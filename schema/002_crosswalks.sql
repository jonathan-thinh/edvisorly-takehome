-- =============================================================================
-- Partner Crosswalk Tables
-- =============================================================================
-- Maps partner-specific identifiers and names to our canonical institution record.
-- A partner might call a school "Jefferson HS" with code "JEF-001" while another
-- partner calls the same school "Thomas Jefferson High" with code "99042".
-- =============================================================================

CREATE TABLE partner (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code            TEXT UNIQUE NOT NULL,   -- short code, e.g. 'clearinghouse', 'partner_a'
    name            TEXT NOT NULL,
    contact_email   TEXT,
    data_format     TEXT,                   -- 'csv', 'api', 'edi', etc.
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB DEFAULT '{}'::JSONB
);

CREATE TABLE partner_crosswalk (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    partner_id          UUID NOT NULL REFERENCES partner(id),
    institution_id      UUID NOT NULL REFERENCES institution(id),
    partner_school_id   TEXT,                -- the partner's own identifier for this school
    partner_school_name TEXT,                -- the name as the partner knows it
    partner_school_name_normalized TEXT,
    partner_address     TEXT,
    partner_state_code  CHAR(2),
    partner_ceeb        TEXT,
    match_method        TEXT NOT NULL,       -- 'exact_id', 'exact_name', 'fuzzy', 'manual'
    match_confidence    NUMERIC(5,4) CHECK (match_confidence BETWEEN 0 AND 1),
    is_verified         BOOLEAN DEFAULT FALSE,
    verified_by         TEXT,
    verified_at         TIMESTAMPTZ,
    valid_from          DATE,
    valid_to            DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          TEXT NOT NULL DEFAULT 'system'
);

CREATE INDEX idx_crosswalk_partner ON partner_crosswalk(partner_id);
CREATE INDEX idx_crosswalk_institution ON partner_crosswalk(institution_id);
CREATE INDEX idx_crosswalk_partner_school_id ON partner_crosswalk(partner_id, partner_school_id);
CREATE INDEX idx_crosswalk_name ON partner_crosswalk USING gin(partner_school_name_normalized gin_trgm_ops);
CREATE UNIQUE INDEX idx_crosswalk_unique_mapping
    ON partner_crosswalk(partner_id, partner_school_id)
    WHERE partner_school_id IS NOT NULL;

-- Crosswalk audit: every change to a crosswalk mapping is logged
CREATE TABLE crosswalk_audit (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crosswalk_id    UUID NOT NULL REFERENCES partner_crosswalk(id),
    action          TEXT NOT NULL,  -- 'created', 'updated', 'verified', 'rejected', 'deactivated'
    old_values      JSONB,
    new_values      JSONB,
    reason          TEXT,
    performed_by    TEXT NOT NULL,
    performed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_crosswalk_audit_crosswalk ON crosswalk_audit(crosswalk_id);
