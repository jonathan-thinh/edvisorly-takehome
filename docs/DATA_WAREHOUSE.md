# Data Warehouse Considerations

## How Institutional Data Flows to the Warehouse

The institutional data model is designed as an **operational data store (ODS)** — it's the system of record for institution identity. The data warehouse consumes this data for reporting and analytics.

## Architecture Overview

```
┌────────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  Operational DB    │     │  ELT Pipeline    │     │  Data Warehouse   │
│  (PostgreSQL)      │────▶│  (dbt + Airflow) │────▶│  (Snowflake/BQ)   │
│                    │     │                  │     │                   │
│  institution       │     │  staging models  │     │  dim_institution  │
│  institution_ver.  │     │  transform + test│     │  dim_inst_history │
│  lifecycle_event   │     │  incremental     │     │  fact_match       │
│  partner_crosswalk │     │  loads           │     │  fact_transcript  │
│  match_attempt     │     │                  │     │  rpt_data_quality │
└────────────────────┘     └──────────────────┘     └───────────────────┘
```

## Key Warehouse Tables

### dim_institution (Type 2 SCD)

The primary dimension table, directly mirroring our `institution_version` model:

| Column | Type | Description |
|--------|------|-------------|
| institution_key | INT (surrogate) | Warehouse surrogate key |
| institution_id | UUID | Natural key from operational DB |
| edvisorly_id | TEXT | Human-readable ID |
| name | TEXT | School name for this version |
| institution_type | TEXT | high_school, community_college, etc. |
| state_code | CHAR(2) | State |
| city | TEXT | City |
| zip_code | TEXT | Zip |
| nces_id | TEXT | NCES identifier |
| status | TEXT | active, closed, merged |
| valid_from | DATE | Version start |
| valid_to | DATE | Version end (NULL = current) |
| is_current | BOOLEAN | Convenience flag |
| row_hash | TEXT | For change detection |

### dim_institution_current (Convenience view)

A filtered view of `dim_institution` where `is_current = TRUE`. This is what most analysts will query.

### fact_match_attempt

Tracks matching activity for quality reporting:

| Column | Type | Description |
|--------|------|-------------|
| match_id | UUID | Natural key |
| partner_key | INT | FK to dim_partner |
| institution_key | INT | FK to dim_institution |
| match_date | DATE | When the match was attempted |
| match_status | TEXT | auto_matched, pending_review, etc. |
| match_method | TEXT | exact_nces, fuzzy_composite, etc. |
| confidence_score | NUMERIC | 0-1 |
| resolution_time_hours | NUMERIC | Time from attempt to resolution |

### rpt_data_quality (Materialized report)

Pre-computed data quality metrics:

| Metric | Grain | Description |
|--------|-------|-------------|
| match_rate | partner × week | % of attempts that resolved |
| auto_match_rate | partner × week | % that auto-matched |
| avg_confidence | partner × week | Mean confidence score |
| unresolved_count | partner × week | Count of unresolved |
| queue_depth | daily | Pending review items |
| avg_resolution_hours | partner × week | Time to resolve |

## dbt Model Organization

```
models/
├── staging/
│   ├── stg_institutions.sql          # Clean + rename from source
│   ├── stg_institution_versions.sql  # Deduplicate, validate dates
│   ├── stg_lifecycle_events.sql      # Parse event types
│   ├── stg_partner_crosswalks.sql    # Clean partner mappings
│   └── stg_match_attempts.sql        # Standardize match data
├── intermediate/
│   ├── int_institution_with_lineage.sql   # Join institution + merge chain
│   └── int_match_with_resolution.sql      # Match + resolution details
└── marts/
    ├── dim_institution_history.sql        # Full SCD2 dimension
    ├── dim_institution_current.sql        # Current-only convenience
    ├── dim_partner.sql                    # Partner dimension
    ├── fact_match_attempt.sql             # Match fact table
    ├── fact_school_year_report.sql        # School reports fact
    └── rpt_data_quality_weekly.sql        # Quality metrics
```

## Incremental Loading Strategy

For the operational-to-warehouse pipeline:

1. **Full refresh (small tables):** `institution`, `partner`, `lifecycle_event` — small enough to reload fully.
2. **Incremental (large tables):** `institution_version`, `partner_crosswalk`, `match_attempt` — use `updated_at` or `created_at` as the incremental key.
3. **Snapshot (SCD2 in warehouse):** Use dbt snapshots for `dim_institution` to detect changes even if the operational DB doesn't use SCD2 for all fields.

```sql
-- dbt incremental model example
{{
  config(
    materialized='incremental',
    unique_key='id',
    incremental_strategy='merge'
  )
}}

SELECT *
FROM {{ source('edvisorly', 'institution_version') }}
{% if is_incremental() %}
WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
```

## Query Patterns for Analysts

### "What school reports are available for a student's school at their attendance date?"

```sql
SELECT
    r.academic_year,
    r.report_type,
    r.data
FROM fact_school_year_report r
JOIN dim_institution_history d ON r.institution_key = d.institution_key
WHERE d.institution_id = :institution_id
  AND r.academic_year BETWEEN YEAR(:attendance_start) AND YEAR(:attendance_end)
  AND d.valid_from <= :attendance_date
  AND (d.valid_to IS NULL OR d.valid_to > :attendance_date);
```

### "How is our match quality trending by partner?"

```sql
SELECT
    p.partner_name,
    DATE_TRUNC('week', m.match_date) AS week,
    COUNT(*) AS total_attempts,
    AVG(CASE WHEN m.match_status = 'auto_matched' THEN 1 ELSE 0 END) AS auto_match_rate,
    AVG(m.confidence_score) AS avg_confidence
FROM fact_match_attempt m
JOIN dim_partner p ON m.partner_key = p.partner_key
GROUP BY 1, 2
ORDER BY 1, 2;
```

## Performance Considerations

1. **Partition `dim_institution_history`** by `state_code` for geographic queries.
2. **Cluster `fact_match_attempt`** by `match_date` for time-series quality analysis.
3. **Materialize `dim_institution_current`** as a table (not view) for performance on joins.
4. **Pre-aggregate** data quality metrics weekly to avoid expensive full-scan queries.
5. **Index** `institution_id` and `edvisorly_id` in the warehouse for API-driven lookups.
