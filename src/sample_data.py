"""
Generate sample data and run the full resolution demo.

This script demonstrates the end-to-end pipeline:
1. Normalization of messy school names
2. Fuzzy matching with confidence scores
3. School-at-date resolution with merge lineage tracing
"""

from normalizer import normalize_school_name
from matcher import (
    MatchInput, InstitutionRecord, match_institution, classify_match,
    AUTO_ACCEPT_THRESHOLD, REVIEW_THRESHOLD,
)
from resolver import build_demo_db, resolve_school_at_date, PartnerPayload
from datetime import date


def demo_normalization():
    print("=" * 90)
    print("1. NAME NORMALIZATION")
    print("=" * 90)
    print()

    test_cases = [
        ("St. Mary's H.S.", "saint marys high school"),
        ("JEFFERSON TWP. SR. H.S.", "jefferson township senior high school"),
        ("Mt. Pleasant Acad.", "mount pleasant academy"),
        ("Martin Luther King Jr. High School", "martin luther king junior high school"),
        ("N.E. Regional Voc. Tech. H.S.", "northeast regional vocational technical high school"),
        ("W. Springfield Sr. H.S.", "west springfield senior high school"),
        ("Abraham Lincoln H. S.", "abraham lincoln high school"),
        ("WASH. PREP", "wash preparatory"),  # "wash" not expanded: ambiguous truncation (Washburn? Washington?)
    ]

    for raw, expected in test_cases:
        result = normalize_school_name(raw)
        status = "OK" if result == expected else "FAIL"
        print(f"  {status} '{raw}'")
        print(f"     -> '{result}'")
        if result != expected:
            print(f"     expected: '{expected}'")
    print()


def demo_matching():
    print("=" * 90)
    print("2. FUZZY MATCHING WITH CONFIDENCE SCORES")
    print("=" * 90)
    print()
    print(f"  Thresholds: auto_accept >= {AUTO_ACCEPT_THRESHOLD}, review >= {REVIEW_THRESHOLD}")
    print()

    db_records = [
        InstitutionRecord(
            id="EDV-001", name="Thomas Jefferson High School",
            name_normalized=normalize_school_name("Thomas Jefferson High School"),
            state_code="VA", city="Alexandria", zip_code="22312",
            nces_id="510001",
            aliases=[normalize_school_name("TJ High"), normalize_school_name("Jefferson HS")],
        ),
        InstitutionRecord(
            id="EDV-002", name="Saint Mary's Academy",
            name_normalized=normalize_school_name("Saint Mary's Academy"),
            state_code="OR", city="Portland", zip_code="97201",
            aliases=[normalize_school_name("St Marys Academy")],
        ),
        InstitutionRecord(
            id="EDV-003", name="Washington Preparatory High School",
            name_normalized=normalize_school_name("Washington Preparatory High School"),
            state_code="CA", city="Los Angeles", zip_code="90047",
            aliases=[normalize_school_name("Wash Prep"), normalize_school_name("Washington Prep HS")],
        ),
        InstitutionRecord(
            id="EDV-010", name="Jefferson Community College",
            name_normalized=normalize_school_name("Jefferson Community College"),
            state_code="KY", city="Louisville", zip_code="40202",
        ),
    ]

    queries = [
        ("Exact name match", MatchInput(
            name="Thomas Jefferson High School",
            name_normalized=normalize_school_name("Thomas Jefferson High School"),
            state_code="VA", zip_code="22312",
        )),
        ("Abbreviated name", MatchInput(
            name="Jefferson H.S.",
            name_normalized=normalize_school_name("Jefferson H.S."),
            state_code="VA",
        )),
        ("OCR-corrupted name", MatchInput(
            name="St. Marys Acadmy",
            name_normalized=normalize_school_name("St. Marys Acadmy"),
            state_code="OR",
        )),
        ("Partial name (truncated)", MatchInput(
            name="Washington Prep",
            name_normalized=normalize_school_name("Washington Prep"),
            state_code="CA",
        )),
        ("ID-based match (NCES)", MatchInput(
            name="Some Random Name",
            name_normalized=normalize_school_name("Some Random Name"),
            nces_id="510001",
        )),
        ("Ambiguous (HS vs CC)", MatchInput(
            name="Jefferson School",
            name_normalized=normalize_school_name("Jefferson School"),
        )),
    ]

    for label, query in queries:
        results = match_institution(query, db_records)
        status, best = classify_match(results)
        print(f"  [{label}] Query: '{query.name}' (state={query.state_code})")
        print(f"  Decision: {status}")
        for i, r in enumerate(results[:3]):
            marker = " <-- best" if i == 0 else ""
            print(f"    #{i+1} {r.institution.name} -- score={r.overall_score:.4f} ({r.method}){marker}")
        print()


def demo_resolution():
    print("=" * 90)
    print("3. SCHOOL-AT-DATE RESOLUTION WITH MERGE LINEAGE")
    print("=" * 90)
    print()

    db = build_demo_db()

    scenarios = [
        ("Crosswalk hit + historical name",
         PartnerPayload(
             partner_code="partner_a", school_name="Jefferson H.S.",
             school_id="PA-JEF-001", state="VA",
             transcript_date=date(2010, 6, 15),
         )),
        ("Fuzzy match + school was renamed since",
         PartnerPayload(
             partner_code="unknown", school_name="Washington H.S.",
             state="CA", city="Los Angeles",
             transcript_date=date(2003, 5, 20),
         )),
        ("School has since merged (before merge date)",
         PartnerPayload(
             partner_code="partner_c", school_name="Riverside Consolidated H.S.",
             state="IL",
             transcript_date=date(2015, 6, 1),
         )),
        ("School has since merged (after merge date)",
         PartnerPayload(
             partner_code="partner_c", school_name="Riverside Consolidated H.S.",
             state="IL",
             transcript_date=date(2020, 1, 1),
         )),
    ]

    for label, payload in scenarios:
        result = resolve_school_at_date(payload, db)
        print(f"  [{label}]")
        print(f"  Input:  '{payload.school_name}' @ {payload.transcript_date}")
        print(f"  Status: {result.status} (confidence={result.match_confidence:.4f})")
        print(f"  Name at transcript date: {result.institution_name_at_date}")
        print(f"  Current name:            {result.current_institution_name}")
        if len(result.lineage_trace) > 1:
            print(f"  Merge lineage: {' -> '.join(result.lineage_trace)}")
        print()


if __name__ == "__main__":
    demo_normalization()
    demo_matching()
    demo_resolution()
    print("=" * 90)
    print("Demo complete.")
    print("=" * 90)
