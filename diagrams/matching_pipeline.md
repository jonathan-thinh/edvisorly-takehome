# Matching Pipeline Detail

## Multi-Strategy Matching Architecture

```mermaid
flowchart LR
    subgraph Input["Input Processing"]
        RAW["Raw School Name<br/>'St. Mary's H.S.'"]
        NORM["Normalized Name<br/>'saint marys high school'"]
        META["Metadata<br/>state, zip, address"]
    end

    subgraph Strategy["Match Strategies (cascading)"]
        direction TB
        S1["Strategy 1:<br/>Exact ID Match<br/>(NCES / CEEB)"]
        S2["Strategy 2:<br/>Exact Normalized<br/>Name + State"]
        S3["Strategy 3:<br/>Fuzzy Name Match<br/>+ Alias Check"]
        S4["Strategy 4:<br/>Phonetic Match<br/>(Soundex / Metaphone)"]
        S1 -->|Miss| S2
        S2 -->|Miss| S3
        S3 -->|Miss| S4
    end

    subgraph Scoring["Confidence Scoring"]
        direction TB
        NS["Name Score<br/>max(token_sort,<br/>token_set,<br/>partial_ratio)"]
        AS["Address Score<br/>token_sort_ratio"]
        SS["State Match<br/>binary 0 / 1"]
        ZS["Zip Proximity<br/>exact=1, prefix=0.5"]
        COMP["Composite Score<br/>= 0.55×name<br/>+ 0.20×addr<br/>+ 0.15×state<br/>+ 0.10×zip"]
    end

    subgraph Decision["Decision"]
        direction TB
        D1["≥ 0.92 → Auto Accept"]
        D2["0.65–0.92 → Human Review"]
        D3["< 0.65 → Unresolved"]
    end

    RAW --> NORM
    NORM --> S1
    META --> S1
    S1 -->|Hit| D1
    S4 --> NS
    NS --> COMP
    AS --> COMP
    SS --> COMP
    ZS --> COMP
    COMP --> D1
    COMP --> D2
    COMP --> D3

    style D1 fill:#2d6a2d,color:#fff
    style D2 fill:#b8860b,color:#fff
    style D3 fill:#8b0000,color:#fff
```

## Fuzzy Matching Strategies Compared

```mermaid
graph TD
    subgraph Strategies["Name Matching Strategies"]
        TSR["token_sort_ratio<br/>Sorts words alphabetically<br/>then compares<br/><br/>✓ Word order independence<br/>'Lincoln High School'<br/>= 'High School Lincoln'"]
        
        TSETR["token_set_ratio<br/>Compares intersection vs union<br/>of word sets<br/><br/>✓ Extra/missing words<br/>'Jefferson Township HS'<br/>≈ 'Jefferson HS'"]
        
        PR["partial_ratio<br/>Best substring match<br/><br/>✓ Truncated names<br/>'Martin Luther Kin'<br/>≈ 'Martin Luther King'"]
        
        ALIAS["Alias Lookup<br/>Compare against known<br/>alternate names<br/><br/>✓ Non-obvious aliases<br/>'TJ' → 'Thomas Jefferson'"]
    end

    BEST["Best Score = max(all strategies)"]
    
    TSR --> BEST
    TSETR --> BEST
    PR --> BEST
    ALIAS --> BEST

    style BEST fill:#1e3a5f,color:#fff
```

## Confidence Score Breakdown Example

| Signal | Weight | Example Value | Contribution |
|--------|--------|---------------|-------------|
| Name similarity | 0.55 | 0.88 | 0.484 |
| Address similarity | 0.20 | 0.72 | 0.144 |
| State match | 0.15 | 1.00 (yes) | 0.150 |
| Zip proximity | 0.10 | 1.00 (exact) | 0.100 |
| **Composite** | | | **0.878** |
| **Decision** | | | **Pending Review** (0.65 ≤ 0.878 < 0.92) |
