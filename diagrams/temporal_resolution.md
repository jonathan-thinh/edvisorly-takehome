# Temporal Resolution: "School at Date X"

## How We Answer "What was this school when the student attended?"

```mermaid
sequenceDiagram
    participant C as Client/API
    participant R as Resolver
    participant CW as Crosswalk Table
    participant M as Matcher
    participant V as Version Table
    participant L as Lifecycle Events
    
    C->>R: Resolve("Jefferson H.S.", partner_a, "PA-JEF-001", date=2010-06-15)
    
    Note over R: Step 1: Crosswalk Lookup
    R->>CW: lookup(partner=partner_a, school_id=PA-JEF-001)
    CW-->>R: institution_id = EDV-001 ✓

    alt Crosswalk miss
        Note over R: Step 2: Fuzzy Matching
        R->>M: match("jefferson high school", state=VA)
        M-->>R: candidates with scores
        R->>R: classify(best_score)
        alt Auto-matched (≥0.92)
            R->>R: Use matched institution_id
        else Pending review (0.65-0.92)
            R-->>C: pending_review + candidates
        else Unresolved (<0.65)
            R-->>C: unresolved
        end
    end

    Note over R: Step 3: Get Version at Date
    R->>V: get_version(EDV-001, date=2010-06-15)
    V-->>R: "Thomas Jefferson High School" (valid 1985–2015) ✓

    Note over R: Step 4: Trace Merge Lineage
    R->>L: trace_merges(EDV-001)
    L-->>R: No merges (still active) ✓

    R-->>C: Result: name_at_date="Thomas Jefferson High School"<br/>current_name="Thomas Jefferson HS for Science & Tech"<br/>status=resolved, confidence=0.99
```

## Merge Lineage Tracing Example

```mermaid
flowchart LR
    subgraph "2015"
        A["Riverside Consolidated HS<br/>(EDV-004)<br/>Active"]
    end
    
    subgraph "2018 – Merge Event"
        A2["Riverside Consolidated HS<br/>(EDV-004)<br/>Merged"]
        MERGE(("Merged<br/>2018-06-15"))
        B["Riverside-Brookfield HS<br/>(EDV-005)<br/>Absorbed EDV-004"]
    end
    
    subgraph "2020"
        B2["Riverside-Brookfield HS<br/>(EDV-005)<br/>Active — includes<br/>former Riverside Consolidated"]
    end

    A -->|"Student attended 2015"| A2
    A2 --> MERGE
    MERGE --> B
    B --> B2

    style A fill:#1e3a5f,color:#fff
    style A2 fill:#8b0000,color:#fff
    style MERGE fill:#b8860b,color:#fff
    style B fill:#2d6a2d,color:#fff
    style B2 fill:#2d6a2d,color:#fff
```

### Resolution for a 2015 Transcript from Riverside Consolidated:

| Field | Value |
|-------|-------|
| **Input** | "Riverside Consolidated H.S.", transcript date = 2015-06-01 |
| **Matched Institution** | EDV-004 (Riverside Consolidated High School) |
| **Name at Date** | "Riverside Consolidated High School" (active version 1970–2018) |
| **Current Successor** | EDV-005 (Riverside-Brookfield High School) |
| **Merge Lineage** | EDV-004 → EDV-005 |
| **Note** | School reports for 2015 should be pulled from EDV-004; current-year reports from EDV-005 |
