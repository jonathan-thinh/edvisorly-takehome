-- Mart: Full institution history as SCD Type 2 dimension
-- Joins institution identity with all historical versions and merge lineage
-- This is the primary dimension table for analytics involving historical school data

{{
  config(
    materialized='table',
    unique_key='version_id'
  )
}}

WITH institution_versions AS (
    SELECT
        v.id AS version_id,
        v.institution_id,
        i.edvisorly_id,
        i.institution_type,
        v.name,
        v.name_normalized,
        v.address_line1,
        v.city,
        v.state_code,
        v.zip_code,
        v.county,
        v.nces_id,
        v.ceeb_code,
        v.status,
        v.valid_from,
        v.valid_to,
        CASE WHEN v.valid_to IS NULL THEN TRUE ELSE FALSE END AS is_current,
        v.source AS data_source,
        v.confidence,
        v.created_at AS version_created_at
    FROM {{ source('edvisorly_operational', 'institution_version') }} v
    JOIN {{ source('edvisorly_operational', 'institution') }} i
        ON v.institution_id = i.id
),

merge_lineage AS (
    SELECT
        le.institution_id AS original_institution_id,
        le.related_institution_id AS successor_institution_id,
        le.event_date AS merge_date
    FROM {{ source('edvisorly_operational', 'lifecycle_event') }} le
    WHERE le.event_type = 'merged'
      AND le.related_institution_id IS NOT NULL
),

enriched AS (
    SELECT
        iv.*,
        ml.successor_institution_id,
        ml.merge_date,
        CASE
            WHEN ml.successor_institution_id IS NOT NULL THEN TRUE
            ELSE FALSE
        END AS has_successor,
        {{ dbt_utils.generate_surrogate_key(['iv.version_id']) }} AS institution_key
    FROM institution_versions iv
    LEFT JOIN merge_lineage ml
        ON iv.institution_id = ml.original_institution_id
)

SELECT * FROM enriched
