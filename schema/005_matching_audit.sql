-- =============================================================================
-- Matching & Resolution Audit Tables
-- =============================================================================
-- Tracks every matching attempt: what came in, what strategies were tried,
-- what confidence was assigned, and what decision was made. Critical for
-- debugging, improving the matcher, and governance/compliance.
-- =============================================================================

CREATE TYPE match_status AS ENUM (
    'auto_matched',     -- high confidence, automatically accepted
    'pending_review',   -- moderate confidence, needs human review
    'manually_matched', -- human resolved
    'rejected',         -- human determined no match
    'unresolved'        -- no match candidates found
);

CREATE TABLE match_attempt (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    input_name          TEXT NOT NULL,
    input_name_normalized TEXT NOT NULL,
    input_address       TEXT,
    input_city          TEXT,
    input_state         TEXT,
    input_zip           TEXT,
    input_ceeb          TEXT,
    input_nces_id       TEXT,
    partner_id          UUID REFERENCES partner(id),
    transcript_date     DATE,

    matched_institution_id UUID REFERENCES institution(id),
    match_status        match_status NOT NULL,
    match_method        TEXT,            -- 'exact_ceeb', 'exact_nces', 'exact_name', 'fuzzy_name_address', etc.
    confidence_score    NUMERIC(5,4) CHECK (confidence_score BETWEEN 0 AND 1),
    confidence_details  JSONB,           -- breakdown of scoring factors

    candidates          JSONB,           -- top N candidates with scores, for review
    resolution_notes    TEXT,
    resolved_by         TEXT,
    resolved_at         TIMESTAMPTZ,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_match_status ON match_attempt(match_status);
CREATE INDEX idx_match_institution ON match_attempt(matched_institution_id)
    WHERE matched_institution_id IS NOT NULL;
CREATE INDEX idx_match_partner ON match_attempt(partner_id)
    WHERE partner_id IS NOT NULL;
CREATE INDEX idx_match_pending ON match_attempt(created_at)
    WHERE match_status = 'pending_review';

-- Aggregate stats for monitoring match quality
CREATE OR REPLACE VIEW v_match_quality_stats AS
SELECT
    DATE_TRUNC('week', created_at) AS week,
    partner_id,
    match_status,
    COUNT(*) AS attempt_count,
    AVG(confidence_score) AS avg_confidence,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY confidence_score) AS median_confidence
FROM match_attempt
GROUP BY 1, 2, 3;
