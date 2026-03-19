-- Staging model: clean and rename source institution data
-- Deduplicates and applies basic data quality checks

{{
  config(
    materialized='view'
  )
}}

WITH source AS (
    SELECT
        id,
        edvisorly_id,
        institution_type,
        created_at,
        created_by,
        notes,
        ROW_NUMBER() OVER (PARTITION BY id ORDER BY created_at DESC) AS rn
    FROM {{ source('edvisorly_operational', 'institution') }}
),

cleaned AS (
    SELECT
        id AS institution_id,
        edvisorly_id,
        COALESCE(institution_type, 'unknown') AS institution_type,
        created_at,
        created_by
    FROM source
    WHERE rn = 1
)

SELECT * FROM cleaned
