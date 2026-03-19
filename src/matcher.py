"""
Fuzzy matching engine for high school institution records.

Implements a multi-strategy matching pipeline:
1. Exact match on authoritative IDs (NCES, CEEB)
2. Exact match on normalized name + state
3. Fuzzy match on normalized name with address boosting
4. Candidate ranking with composite confidence scores

Confidence scoring factors:
- Name similarity (token_sort_ratio for word-order independence)
- Address similarity
- State match (binary boost)
- Zip code proximity
- Presence of authoritative ID match
"""

from dataclasses import dataclass, field
from typing import Optional
from rapidfuzz import fuzz


@dataclass
class InstitutionRecord:
    """Represents an institution in our canonical database."""
    id: str
    name: str
    name_normalized: str
    state_code: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    nces_id: Optional[str] = None
    ceeb_code: Optional[str] = None
    address: Optional[str] = None
    institution_type: Optional[str] = None
    aliases: list[str] = field(default_factory=list)


@dataclass
class MatchInput:
    """Represents incoming data to match (e.g., from a transcript or partner payload)."""
    name: str
    name_normalized: str
    state_code: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    nces_id: Optional[str] = None
    ceeb_code: Optional[str] = None
    address: Optional[str] = None
    transcript_date: Optional[str] = None


@dataclass
class MatchCandidate:
    """A potential match with its confidence breakdown."""
    institution: InstitutionRecord
    overall_score: float
    name_score: float
    address_score: float
    state_match: bool
    method: str
    score_breakdown: dict = field(default_factory=dict)


# Thresholds -- tuned for high recall (the brief emphasizes recall over precision)
AUTO_ACCEPT_THRESHOLD = 0.92
REVIEW_THRESHOLD = 0.65
NAME_WEIGHT = 0.55
ADDRESS_WEIGHT = 0.20
STATE_WEIGHT = 0.15
ZIP_WEIGHT = 0.10


def compute_name_similarity(
    input_name: str, candidate_name: str, aliases: list[str] = None
) -> float:
    """
    Compute name similarity using multiple strategies and take the best score.

    Uses three complementary algorithms:
    - token_sort_ratio: word-order independent ("Lincoln High" = "High Lincoln")
    - token_set_ratio: handles extra/missing words ("Jefferson HS" ~ "Jefferson Township HS")
    - partial_ratio: handles truncation ("Martin Luther Kin" ~ "Martin Luther King")
    """
    scores = [
        fuzz.token_sort_ratio(input_name, candidate_name) / 100.0,
        fuzz.token_set_ratio(input_name, candidate_name) / 100.0,
        fuzz.partial_ratio(input_name, candidate_name) / 100.0,
    ]

    if aliases:
        for alias in aliases:
            scores.append(fuzz.token_sort_ratio(input_name, alias) / 100.0)
            scores.append(fuzz.token_set_ratio(input_name, alias) / 100.0)

    return max(scores)


def compute_address_similarity(
    input_addr: Optional[str], candidate_addr: Optional[str]
) -> float:
    """Compute address similarity. Returns 0 if either is missing."""
    if not input_addr or not candidate_addr:
        return 0.0
    return fuzz.token_sort_ratio(input_addr, candidate_addr) / 100.0


def compute_zip_proximity(
    input_zip: Optional[str], candidate_zip: Optional[str]
) -> float:
    """
    Score zip code proximity.
    - Exact 5-digit match = 1.0
    - Same 3-digit prefix = 0.5 (same metro area)
    - Otherwise = 0.0
    """
    if not input_zip or not candidate_zip:
        return 0.0
    iz = input_zip.strip().replace("-", "")[:5]
    cz = candidate_zip.strip().replace("-", "")[:5]
    if iz == cz:
        return 1.0
    if len(iz) >= 3 and len(cz) >= 3 and iz[:3] == cz[:3]:
        return 0.5
    return 0.0


def compute_composite_score(
    name_score: float,
    address_score: float,
    state_match: bool,
    zip_score: float,
) -> float:
    """
    Weighted composite of all matching signals.
    State match is a binary 0/1 boost, not a similarity score.
    """
    state_score = 1.0 if state_match else 0.0
    composite = (
        NAME_WEIGHT * name_score
        + ADDRESS_WEIGHT * address_score
        + STATE_WEIGHT * state_score
        + ZIP_WEIGHT * zip_score
    )
    return round(min(composite, 1.0), 4)


def match_institution(
    query: MatchInput,
    candidates: list[InstitutionRecord],
    top_n: int = 5,
) -> list[MatchCandidate]:
    """
    Match an input against a list of candidate institutions.

    Strategy (executed in order, short-circuits on exact ID match):
    1. If NCES ID or CEEB code matches exactly, return immediately (confidence 0.99)
    2. Pre-filter by state if available (fall back to all candidates)
    3. Compute fuzzy composite scores for remaining candidates
    4. Return top N candidates sorted by composite score
    """
    results: list[MatchCandidate] = []

    # Strategy 1: Exact authoritative ID match
    for candidate in candidates:
        if query.nces_id and candidate.nces_id and query.nces_id == candidate.nces_id:
            return [MatchCandidate(
                institution=candidate,
                overall_score=0.99,
                name_score=1.0,
                address_score=1.0,
                state_match=True,
                method="exact_nces_id",
                score_breakdown={"nces_id_match": True},
            )]
        if query.ceeb_code and candidate.ceeb_code and query.ceeb_code == candidate.ceeb_code:
            return [MatchCandidate(
                institution=candidate,
                overall_score=0.98,
                name_score=1.0,
                address_score=1.0,
                state_match=True,
                method="exact_ceeb_code",
                score_breakdown={"ceeb_code_match": True},
            )]

    # Strategy 2: State pre-filter to narrow search space
    if query.state_code:
        state_filtered = [c for c in candidates if c.state_code == query.state_code]
        search_set = state_filtered if state_filtered else candidates
    else:
        search_set = candidates

    # Strategy 3: Fuzzy matching with composite scoring
    for candidate in search_set:
        name_score = compute_name_similarity(
            query.name_normalized, candidate.name_normalized, candidate.aliases
        )
        address_score = compute_address_similarity(query.address, candidate.address)
        state_match = (
            query.state_code is not None
            and candidate.state_code is not None
            and query.state_code == candidate.state_code
        )
        zip_score = compute_zip_proximity(query.zip_code, candidate.zip_code)

        overall = compute_composite_score(name_score, address_score, state_match, zip_score)

        results.append(MatchCandidate(
            institution=candidate,
            overall_score=overall,
            name_score=name_score,
            address_score=address_score,
            state_match=state_match,
            method="fuzzy_composite",
            score_breakdown={
                "name_score": round(name_score, 4),
                "address_score": round(address_score, 4),
                "state_match": state_match,
                "zip_score": round(zip_score, 4),
                "weights": {
                    "name": NAME_WEIGHT,
                    "address": ADDRESS_WEIGHT,
                    "state": STATE_WEIGHT,
                    "zip": ZIP_WEIGHT,
                },
            },
        ))

    results.sort(key=lambda x: x.overall_score, reverse=True)
    return results[:top_n]


def classify_match(
    candidates: list[MatchCandidate],
) -> tuple[str, Optional[MatchCandidate]]:
    """
    Classify the best match result and decide the routing action.

    Returns:
        (status, best_candidate) where status is one of:
        - 'auto_matched': confidence >= AUTO_ACCEPT_THRESHOLD, safe to accept
        - 'pending_review': confidence in [REVIEW_THRESHOLD, AUTO_ACCEPT_THRESHOLD)
        - 'unresolved': no candidates above REVIEW_THRESHOLD
    """
    if not candidates:
        return "unresolved", None

    best = candidates[0]

    if best.overall_score >= AUTO_ACCEPT_THRESHOLD:
        return "auto_matched", best
    elif best.overall_score >= REVIEW_THRESHOLD:
        return "pending_review", best
    else:
        return "unresolved", None


if __name__ == "__main__":
    from normalizer import normalize_school_name

    db = [
        InstitutionRecord(
            id="EDV-001", name="Thomas Jefferson High School",
            name_normalized=normalize_school_name("Thomas Jefferson High School"),
            state_code="VA", city="Alexandria", zip_code="22312",
            nces_id="510001", ceeb_code="470001",
            aliases=["jefferson high", "tj high school"],
        ),
        InstitutionRecord(
            id="EDV-002", name="Saint Mary's Academy",
            name_normalized=normalize_school_name("Saint Mary's Academy"),
            state_code="OR", city="Portland", zip_code="97201",
            aliases=["st marys academy", "st. mary's"],
        ),
        InstitutionRecord(
            id="EDV-003", name="Martin Luther King Jr. High School",
            name_normalized=normalize_school_name("Martin Luther King Jr. High School"),
            state_code="CA", city="Sacramento", zip_code="95820",
        ),
    ]

    test_queries = [
        MatchInput(
            name="Jefferson H.S.", name_normalized=normalize_school_name("Jefferson H.S."),
            state_code="VA", zip_code="22312",
        ),
        MatchInput(
            name="St. Mary's H.S.", name_normalized=normalize_school_name("St. Mary's H.S."),
            state_code="OR",
        ),
        MatchInput(
            name="MLK High School", name_normalized=normalize_school_name("MLK High School"),
            state_code="CA",
        ),
        MatchInput(
            name="Jefferson H.S.", name_normalized=normalize_school_name("Jefferson H.S."),
            nces_id="510001",
        ),
    ]

    print("=" * 80)
    print("MATCHING DEMO")
    print("=" * 80)

    for query in test_queries:
        print(f"\nQuery: '{query.name}' (state={query.state_code}, nces={query.nces_id})")
        results = match_institution(query, db)
        status, best = classify_match(results)
        print(f"  Status: {status}")
        if best:
            print(f"  Best match: {best.institution.name} (score={best.overall_score:.4f}, method={best.method})")
            print(f"  Breakdown: {best.score_breakdown}")
        for i, r in enumerate(results):
            print(f"  #{i+1}: {r.institution.name} -- score={r.overall_score:.4f}")
