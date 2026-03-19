# Data Flow Diagram

## How Transcript Data Flows to an Institution Record

```mermaid
flowchart TD
    subgraph Sources["Data Sources"]
        T[/"Transcript (OCR/PDF)"/]
        P[/"Partner API Feed"/]
        N[/"NCES Annual Data"/]
        M[/"Manual Entry"/]
    end

    subgraph Ingestion["Ingestion Layer"]
        PARSE["Parse & Extract<br/>school name, address,<br/>date, IDs"]
        NORM["Normalize<br/>expand abbreviations,<br/>strip punctuation,<br/>standardize"]
    end

    subgraph Resolution["Resolution Pipeline"]
        CW{"Crosswalk<br/>Lookup"}
        ID{"Authoritative<br/>ID Match?<br/>(NCES/CEEB)"}
        EXACT{"Exact Name<br/>+ State?"}
        FUZZY["Fuzzy Match<br/>(token_sort, token_set,<br/>partial_ratio)"]
        SCORE["Composite<br/>Scoring"]
        CLASSIFY{"Confidence<br/>Check"}
    end

    subgraph Outcomes["Match Outcomes"]
        AUTO["Auto-Matched<br/>(≥ 0.92)"]
        REVIEW["Pending Review<br/>(0.65 – 0.92)"]
        UNRESOLVED["Unresolved<br/>(< 0.65)"]
        MANUAL["Human Review<br/>Queue"]
    end

    subgraph Temporal["Temporal Resolution"]
        VER["Lookup Version<br/>at Transcript Date"]
        LINEAGE["Trace Merge<br/>Lineage"]
        RESULT[/"Institution Record<br/>+ Name at Date<br/>+ Current State"/]
    end

    subgraph Storage["Storage Layer"]
        DB[(Institution<br/>Database)]
        AUDIT[(Match Audit<br/>Log)]
        DW[(Data<br/>Warehouse)]
    end

    T --> PARSE
    P --> PARSE
    N --> PARSE
    M --> PARSE
    PARSE --> NORM

    NORM --> CW
    CW -->|Hit| VER
    CW -->|Miss| ID
    ID -->|Yes| VER
    ID -->|No| EXACT
    EXACT -->|Yes| VER
    EXACT -->|No| FUZZY
    FUZZY --> SCORE
    SCORE --> CLASSIFY

    CLASSIFY -->|High| AUTO
    CLASSIFY -->|Medium| REVIEW
    CLASSIFY -->|Low| UNRESOLVED

    AUTO --> VER
    REVIEW --> MANUAL
    MANUAL -->|Resolved| VER
    MANUAL -->|New School| DB
    UNRESOLVED --> MANUAL

    VER --> LINEAGE
    LINEAGE --> RESULT

    RESULT --> DB
    RESULT --> AUDIT
    RESULT --> DW

    style AUTO fill:#2d6a2d,color:#fff
    style REVIEW fill:#b8860b,color:#fff
    style UNRESOLVED fill:#8b0000,color:#fff
    style RESULT fill:#1e3a5f,color:#fff
```

## Flow Description

| Step | Description |
|------|------------|
| **Parse & Extract** | Raw data from transcripts, partner feeds, or manual entry is parsed to extract school name, address, dates, and any identifiers. |
| **Normalize** | Abbreviations expanded, punctuation removed, case standardized. This is critical for both exact and fuzzy matching. |
| **Crosswalk Lookup** | Check if this partner + school ID combination has been seen before. If yes, we have a direct mapping. |
| **Authoritative ID Match** | Check NCES ID or CEEB code for an exact match. These are high-confidence signals. |
| **Exact Name + State** | Normalized name + state is checked for an exact match against our database. |
| **Fuzzy Match** | Multiple fuzzy strategies (token_sort, token_set, partial_ratio) are combined with address and geographic signals. |
| **Composite Scoring** | Weighted combination: 55% name, 20% address, 15% state, 10% zip. |
| **Classification** | Auto-accept (≥0.92), pending review (0.65–0.92), or unresolved (<0.65). |
| **Temporal Resolution** | Once matched, find the `institution_version` active at the transcript date and trace any merge lineage. |
