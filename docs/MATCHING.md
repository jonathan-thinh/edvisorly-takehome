# Matching Strategy: Handling Inconsistent and Noisy Data

## The Problem

Partner data is messy:
- **Abbreviations:** "St." vs "Saint", "H.S." vs "High School", "Mt." vs "Mount"
- **OCR errors:** "Acadmy" instead of "Academy", "Llncoln" instead of "Lincoln"
- **Truncation:** "Martin Luther Kin" instead of "Martin Luther King Jr."
- **Word order:** "Lincoln High School" vs "High School Lincoln"
- **Missing data:** Address might be partial, state might be absent
- **Ambiguity:** "Jefferson School" could be Jefferson High School in Virginia or Jefferson Community College in Kentucky

## Our Multi-Layer Approach

### Layer 1: Normalization (pre-matching)

Before any matching, we normalize both the input and our database records:

```
Input:  "St. Mary's H.S."
Step 1: lowercase           → "st. mary's h.s."
Step 2: remove possessives  → "st. marys h.s."
Step 3: strip punctuation   → "st marys h s"
Step 4: expand abbreviations→ "saint marys high school"
Step 5: collapse whitespace → "saint marys high school"
```

The abbreviation map covers 30+ common patterns, ordered from longest to shortest to avoid partial replacements. See `src/normalizer.py` for the full implementation.

**Why normalize before matching?** Because it dramatically reduces the search space for fuzzy matching. "St. Mary's H.S." and "Saint Mary's High School" become identical after normalization — no fuzzy matching needed.

### Layer 2: Authoritative ID Matching

If the input includes an NCES ID or CEEB code, we check for an exact match first. These are the highest-confidence signals:
- **NCES ID:** Assigned by the Department of Education, unique per school
- **CEEB code:** Assigned by College Board, used in SAT/AP reporting

An exact ID match gets **0.99 confidence** and bypasses fuzzy matching entirely.

### Layer 3: Fuzzy Name Matching

When IDs are absent, we use three complementary fuzzy strategies:

| Strategy | Handles | Example |
|----------|---------|---------|
| `token_sort_ratio` | Word reordering | "Lincoln High School" ≈ "High School Lincoln" |
| `token_set_ratio` | Extra/missing words | "Jefferson Township HS" ≈ "Jefferson HS" |
| `partial_ratio` | Truncation/substring | "Martin Luther Kin" ≈ "Martin Luther King" |

We take the **maximum score** across all strategies, including checks against known aliases. This ensures we don't miss a match just because one strategy doesn't handle a particular type of noise.

### Layer 4: Alias Matching

Each institution can have multiple aliases: abbreviations, former names, OCR variants. The matcher checks the input against all aliases using the same fuzzy strategies. This catches cases like:
- "TJ" → "Thomas Jefferson"
- "Wash Prep" → "Washington Preparatory"

Aliases are populated from:
- Historical names (from lifecycle events)
- Partner-provided alternate names
- Manually added variants discovered during review

### Layer 5: Composite Scoring

Individual signals are combined into a composite score:

```
composite = 0.55 × name_score
          + 0.20 × address_score
          + 0.15 × state_match
          + 0.10 × zip_proximity
```

**Weight rationale:**
- **Name (55%):** The strongest signal, but not sufficient alone (many schools share similar names)
- **Address (20%):** Disambiguates same-name schools in different locations
- **State (15%):** A binary boost — very reliable when available
- **Zip (10%):** Provides geo-proximity signal; exact = 1.0, same 3-digit prefix = 0.5

### Layer 6: Classification

| Composite Score | Decision | Rationale |
|----------------|----------|-----------|
| ≥ 0.92 | **Auto-accept** | High confidence across multiple signals |
| 0.65 – 0.92 | **Pending review** | Plausible match, needs human confirmation |
| < 0.65 | **Unresolved** | No strong candidates; queued for manual research |

**Why 0.92 for auto-accept?** The brief emphasizes recall. A lower auto-accept threshold (e.g., 0.85) would increase automation but risk false positives. We chose 0.92 as a balance point and set the review threshold low (0.65) to ensure we catch fuzzy matches.

## Handling Specific Challenges

### OCR Errors

OCR errors are character-level noise (substitutions, deletions, insertions). Our approach:
1. `partial_ratio` handles single-character errors well (it finds the best substring match)
2. Known OCR patterns (e.g., "l" ↔ "h", "0" ↔ "o") could be added as alias variants
3. For severe OCR corruption, the address and geographic signals become more important

### Ambiguity (HS vs Community College)

When a name like "Jefferson School" matches both a high school and a community college:
1. The `institution_type` field distinguishes them
2. Context clues help: transcript date, student age, course-level information
3. If ambiguous, both candidates surface in the review queue with their types displayed
4. The composite score treats them equally — disambiguation is a human decision or a downstream business rule

### Stale Partner Data

A partner may have outdated school information (e.g., still using a pre-rename name):
1. Crosswalk temporal validity (`valid_from` / `valid_to`) tracks when a partner mapping was valid
2. The matcher checks aliases including former names
3. If a crosswalk hit points to a school that has since renamed/merged, the temporal resolution step handles it correctly

## Future Improvements

1. **Phonetic matching (Soundex/Metaphone):** Would help with pronunciation-similar misspellings
2. **ML-based scoring:** Train a classifier on historical match decisions to learn partner-specific patterns
3. **Address parsing with `usaddress`:** Structured address comparison (number, street, city) instead of string similarity
4. **Geographic distance scoring:** Using geocoded lat/long instead of zip code prefix matching
5. **Ensemble scoring:** Learn optimal weights from reviewer feedback, potentially per-partner
