# High School Institution Identity and Change Over Time

**Edvisorly — Sr. Software Engineer / Data Engineer Take-Home Assessment**

## Problem Summary

Edvisorly helps transfer students complete their four-year degree by working with high school transcripts that may be many years old. Schools rename, merge, and close over time. We need a system that can reliably answer: **"What was this school when this student attended?"**

This repository presents a complete data model, matching pipeline, governance framework, and documentation for managing high school institution identity over time.

## Repository Structure

```
├── README.md                          # This file
├── docs/
│   ├── APPROACH.md                    # Design approach, tradeoffs, and decisions
│   ├── GOVERNANCE.md                  # Process and governance recommendations
│   ├── DATA_WAREHOUSE.md             # Data warehouse considerations
│   └── MATCHING.md                    # Matching strategy documentation
├── diagrams/
│   ├── er_diagram.md                  # Entity-Relationship diagram (Mermaid)
│   ├── data_flow.md                   # Data flow diagram
│   ├── matching_pipeline.md           # Matching/resolution pipeline
│   └── governance_flow.md             # Governance and review process
├── schema/
│   ├── 001_core_tables.sql            # Core institution and identity tables
│   ├── 002_crosswalks.sql             # Partner crosswalk tables
│   ├── 003_lifecycle_events.sql       # Lifecycle event tables
│   ├── 004_school_year_reports.sql    # School-by-year data tables
│   ├── 005_matching_audit.sql         # Match audit and confidence tables
│   └── 006_views.sql                  # Useful views for common queries
├── src/
│   ├── requirements.txt               # Python dependencies
│   ├── normalizer.py                  # School name normalization
│   ├── matcher.py                     # Fuzzy matching with confidence scores
│   ├── resolver.py                    # "School at date X" resolution logic
│   └── sample_data.py                 # Generate sample data for demonstration
├── dbt/
│   └── models/
│       ├── staging/
│       │   └── stg_institutions.sql   # Staging model
│       └── marts/
│           └── dim_institution_history.sql  # Dimension table for analytics
└── tests/
    └── test_matcher.py                # Unit tests for matching logic
```

## Quick Start

```bash
# Install Python dependencies
pip install -r src/requirements.txt

# Run the demo (generates sample data, runs matching, resolves school-at-date)
python src/sample_data.py

# Run tests
python -m pytest tests/ -v
```

## Key Design Decisions

1. **Temporal modeling with SCD Type 2** — Every institution attribute is versioned with `valid_from` / `valid_to` windows, enabling point-in-time queries.
2. **Separate identity from attributes** — An `institution` is the stable identity anchor; `institution_version` captures how attributes change.
3. **Explicit lifecycle events** — Renames, merges, closures, and reopenings are first-class events, not inferred.
4. **Multi-strategy matching** — Normalization -> exact match -> fuzzy match -> manual review, with confidence scores at each step.
5. **Governance by design** — Audit trails, source provenance, and review workflows are built into the schema.

## Diagrams

All diagrams use [Mermaid](https://mermaid.js.org/) syntax and can be rendered on GitHub, in VS Code (with Mermaid extension), or at [mermaid.live](https://mermaid.live).

## Technology Choices

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Schema | PostgreSQL | JSONB for flexible metadata, strong temporal support, widely adopted |
| Matching | Python (rapidfuzz, usaddress) | Mature fuzzy matching libraries, easy to iterate |
| Data Warehouse | dbt + Snowflake/BigQuery | Industry standard for analytics engineering |
| Diagrams | Mermaid | Text-based, version-controllable, renders on GitHub |
