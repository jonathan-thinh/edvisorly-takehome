-- =============================================================================
-- Useful Views for Common Queries
-- =============================================================================

-- Current state of all institutions (most recent version)
CREATE OR REPLACE VIEW v_institution_current AS
SELECT
    i.id,
    i.edvisorly_id,
    i.institution_type,
    v.name,
    v.name_normalized,
    v.address_line1,
    v.city,
    v.state_code,
    v.zip_code,
    v.nces_id,
    v.ceeb_code,
    v.status,
    v.valid_from,
    v.source,
    v.confidence
FROM institution i
JOIN institution_version v ON v.institution_id = i.id AND v.valid_to IS NULL;

-- Point-in-time lookup: pass a date to get what each institution looked like then
-- Usage: SELECT * FROM v_institution_current WHERE ... 
-- For point-in-time, use the function below instead.
CREATE OR REPLACE FUNCTION fn_institution_at_date(lookup_date DATE)
RETURNS TABLE (
    institution_id UUID,
    edvisorly_id TEXT,
    institution_type institution_type,
    name TEXT,
    address_line1 TEXT,
    city TEXT,
    state_code CHAR(2),
    zip_code TEXT,
    nces_id TEXT,
    ceeb_code TEXT,
    status institution_status
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        i.id,
        i.edvisorly_id,
        i.institution_type,
        v.name,
        v.address_line1,
        v.city,
        v.state_code,
        v.zip_code,
        v.nces_id,
        v.ceeb_code,
        v.status
    FROM institution i
    JOIN institution_version v ON v.institution_id = i.id
    WHERE v.valid_from <= lookup_date
      AND (v.valid_to IS NULL OR v.valid_to > lookup_date);
END;
$$ LANGUAGE plpgsql STABLE;

-- Full institution history with lifecycle events interleaved
CREATE OR REPLACE VIEW v_institution_timeline AS
SELECT
    i.id AS institution_id,
    i.edvisorly_id,
    'version' AS entry_type,
    v.name AS description,
    v.valid_from AS event_date,
    v.source,
    NULL AS event_type
FROM institution i
JOIN institution_version v ON v.institution_id = i.id

UNION ALL

SELECT
    le.institution_id,
    i.edvisorly_id,
    'lifecycle_event' AS entry_type,
    le.description,
    le.event_date,
    le.source,
    le.event_type::TEXT
FROM lifecycle_event le
JOIN institution i ON i.id = le.institution_id

ORDER BY institution_id, event_date;

-- Partner coverage report: how many of our institutions does each partner map to?
CREATE OR REPLACE VIEW v_partner_coverage AS
SELECT
    p.code AS partner_code,
    p.name AS partner_name,
    COUNT(DISTINCT pc.institution_id) AS mapped_institutions,
    COUNT(DISTINCT pc.institution_id) FILTER (WHERE pc.is_verified) AS verified_mappings,
    AVG(pc.match_confidence) AS avg_confidence,
    COUNT(*) FILTER (WHERE pc.match_confidence < 0.7) AS low_confidence_count
FROM partner p
LEFT JOIN partner_crosswalk pc ON pc.partner_id = p.id
GROUP BY p.id, p.code, p.name;
