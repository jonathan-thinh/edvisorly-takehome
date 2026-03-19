-- =============================================================================
-- Lifecycle Events
-- =============================================================================
-- Explicitly models what happens to schools over time: rename, merge, close, reopen.
-- This is critical for answering "what was this school in 2010?" and for tracing
-- the lineage of merged/renamed institutions.
-- =============================================================================

CREATE TYPE lifecycle_event_type AS ENUM (
    'opened',
    'renamed',
    'merged',        -- this school merged INTO another (this school ceases)
    'absorbed',      -- this school absorbed another (this school continues)
    'split',
    'closed',
    'reopened',
    'reclassified'   -- e.g. changed from community_college to high_school
);

CREATE TABLE lifecycle_event (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id      UUID NOT NULL REFERENCES institution(id),
    event_type          lifecycle_event_type NOT NULL,
    event_date          DATE NOT NULL,
    related_institution_id UUID REFERENCES institution(id),  -- for merge/absorb/split
    description         TEXT,
    source              TEXT NOT NULL,
    source_reference    TEXT,       -- link or ID to the source document
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          TEXT NOT NULL DEFAULT 'system',
    verified            BOOLEAN DEFAULT FALSE,
    verified_by         TEXT,
    verified_at         TIMESTAMPTZ,
    metadata            JSONB DEFAULT '{}'::JSONB
);

CREATE INDEX idx_lifecycle_institution ON lifecycle_event(institution_id);
CREATE INDEX idx_lifecycle_related ON lifecycle_event(related_institution_id)
    WHERE related_institution_id IS NOT NULL;
CREATE INDEX idx_lifecycle_type ON lifecycle_event(event_type);
CREATE INDEX idx_lifecycle_date ON lifecycle_event(event_date);

-- Merge lineage view: trace where a school ended up after merging
-- Example: School A merged into School B, which later merged into School C.
-- This recursive CTE traces A → B → C.
CREATE OR REPLACE VIEW v_merge_lineage AS
WITH RECURSIVE lineage AS (
    SELECT
        institution_id AS original_id,
        related_institution_id AS successor_id,
        event_date,
        1 AS depth
    FROM lifecycle_event
    WHERE event_type = 'merged'
      AND related_institution_id IS NOT NULL

    UNION ALL

    SELECT
        l.original_id,
        e.related_institution_id AS successor_id,
        e.event_date,
        l.depth + 1
    FROM lineage l
    JOIN lifecycle_event e ON e.institution_id = l.successor_id
    WHERE e.event_type = 'merged'
      AND e.related_institution_id IS NOT NULL
      AND l.depth < 10  -- safety limit
)
SELECT
    original_id,
    successor_id AS final_successor_id,
    event_date AS final_merge_date,
    depth AS merge_chain_length
FROM lineage l
WHERE NOT EXISTS (
    SELECT 1 FROM lineage l2 WHERE l2.original_id = l.original_id AND l2.depth > l.depth
);
