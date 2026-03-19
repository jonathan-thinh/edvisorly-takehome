"""Unit tests for normalizer and matcher."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from normalizer import normalize_school_name
from matcher import (
    InstitutionRecord, MatchInput, MatchCandidate,
    compute_name_similarity, compute_composite_score, compute_zip_proximity,
    match_institution, classify_match,
    AUTO_ACCEPT_THRESHOLD, REVIEW_THRESHOLD,
)


class TestNormalizer:
    def test_basic_abbreviations(self):
        assert normalize_school_name("St. Mary's H.S.") == "saint marys high school"

    def test_township_senior(self):
        assert normalize_school_name("JEFFERSON TWP. SR. H.S.") == "jefferson township senior high school"

    def test_mount_academy(self):
        assert normalize_school_name("Mt. Pleasant Acad.") == "mount pleasant academy"

    def test_directional_compound(self):
        result = normalize_school_name("N.E. Regional Voc. Tech. H.S.")
        assert "northeast" in result
        assert "regional" in result
        assert "vocational" in result
        assert "technical" in result
        assert "high school" in result

    def test_directional_single(self):
        result = normalize_school_name("W. Springfield Sr. H.S.")
        assert result == "west springfield senior high school"

    def test_empty_input(self):
        assert normalize_school_name("") == ""
        assert normalize_school_name(None) == ""

    def test_already_normalized(self):
        assert normalize_school_name("lincoln high school") == "lincoln high school"

    def test_possessive_removal(self):
        result = normalize_school_name("King's Academy")
        assert "'" not in result
        assert "kings" in result

    def test_junior_high_school(self):
        result = normalize_school_name("Washington Jr. H.S.")
        assert "junior high school" in result

    def test_senior_high_school(self):
        result = normalize_school_name("Central SR. H.S.")
        assert "senior high school" in result

    def test_fort_abbreviation(self):
        assert "fort" in normalize_school_name("Ft. Worth H.S.")

    def test_preserves_full_words(self):
        result = normalize_school_name("Springfield High School")
        assert result == "springfield high school"

    def test_mixed_case(self):
        assert normalize_school_name("LINCOLN HIGH SCHOOL") == "lincoln high school"


class TestNameSimilarity:
    def test_exact_match(self):
        score = compute_name_similarity("lincoln high school", "lincoln high school")
        assert score == 1.0

    def test_reordered_words(self):
        score = compute_name_similarity("high school lincoln", "lincoln high school")
        assert score > 0.9

    def test_partial_match(self):
        score = compute_name_similarity("jefferson high", "thomas jefferson high school")
        assert score > 0.6

    def test_alias_boost(self):
        score_without = compute_name_similarity("tj high", "thomas jefferson high school")
        score_with = compute_name_similarity(
            "tj high", "thomas jefferson high school",
            aliases=["tj high school"]
        )
        assert score_with >= score_without

    def test_completely_different(self):
        score = compute_name_similarity("xyz academy", "lincoln high school")
        assert score < 0.5


class TestCompositeScore:
    def test_perfect_score(self):
        score = compute_composite_score(1.0, 1.0, True, 1.0)
        assert score == 1.0

    def test_name_only(self):
        score = compute_composite_score(1.0, 0.0, False, 0.0)
        assert 0.5 < score < 0.6  # NAME_WEIGHT is 0.55

    def test_zero_score(self):
        score = compute_composite_score(0.0, 0.0, False, 0.0)
        assert score == 0.0

    def test_state_boost(self):
        without_state = compute_composite_score(0.8, 0.0, False, 0.0)
        with_state = compute_composite_score(0.8, 0.0, True, 0.0)
        assert with_state > without_state

    def test_capped_at_one(self):
        score = compute_composite_score(1.0, 1.0, True, 1.0)
        assert score <= 1.0


class TestZipProximity:
    def test_exact_match(self):
        assert compute_zip_proximity("22312", "22312") == 1.0

    def test_same_prefix(self):
        assert compute_zip_proximity("22312", "22301") == 0.5

    def test_different(self):
        assert compute_zip_proximity("22312", "90210") == 0.0

    def test_none_input(self):
        assert compute_zip_proximity(None, "22312") == 0.0

    def test_zip_plus_four(self):
        assert compute_zip_proximity("22312-1234", "22312") == 1.0


class TestMatchInstitution:
    def setup_method(self):
        self.db = [
            InstitutionRecord(
                id="1", name="Lincoln High School",
                name_normalized="lincoln high school",
                state_code="OR", zip_code="97214",
                institution_type="high_school",
                aliases=["lincoln hs"],
            ),
            InstitutionRecord(
                id="2", name="Lincoln Middle School",
                name_normalized="lincoln middle school",
                state_code="OR", zip_code="97214",
                institution_type="high_school",
            ),
            InstitutionRecord(
                id="3", name="Washington High School",
                name_normalized="washington high school",
                state_code="CA", zip_code="90047",
                institution_type="high_school",
            ),
        ]

    def test_exact_nces_match(self):
        self.db[0].nces_id = "123456"
        query = MatchInput(name="anything", name_normalized="anything", nces_id="123456")
        results = match_institution(query, self.db)
        assert len(results) == 1
        assert results[0].institution.id == "1"
        assert results[0].method == "exact_nces_id"
        assert results[0].overall_score == 0.99

    def test_exact_ceeb_match(self):
        self.db[0].ceeb_code = "AB1234"
        query = MatchInput(name="anything", name_normalized="anything", ceeb_code="AB1234")
        results = match_institution(query, self.db)
        assert len(results) == 1
        assert results[0].method == "exact_ceeb_code"
        assert results[0].overall_score == 0.98

    def test_state_filtering(self):
        query = MatchInput(
            name="Lincoln High School",
            name_normalized="lincoln high school",
            state_code="OR",
        )
        results = match_institution(query, self.db)
        assert results[0].institution.state_code == "OR"

    def test_returns_multiple_candidates(self):
        query = MatchInput(
            name="Lincoln School",
            name_normalized="lincoln school",
            state_code="OR",
        )
        results = match_institution(query, self.db, top_n=3)
        assert len(results) >= 2

    def test_classify_high_confidence(self):
        query = MatchInput(
            name="Lincoln High School",
            name_normalized="lincoln high school",
            state_code="OR", zip_code="97214",
        )
        results = match_institution(query, self.db)
        status, best = classify_match(results)
        assert status in ("auto_matched", "pending_review")
        assert best is not None
        assert best.institution.id == "1"
        assert best.overall_score > 0.75

    def test_classify_empty(self):
        status, best = classify_match([])
        assert status == "unresolved"
        assert best is None

    def test_state_fallback_when_no_state_match(self):
        query = MatchInput(
            name="Lincoln High School",
            name_normalized="lincoln high school",
            state_code="TX",  # no schools in TX
        )
        results = match_institution(query, self.db)
        assert len(results) > 0  # falls back to all candidates

    def test_score_breakdown_present(self):
        query = MatchInput(
            name="Lincoln High School",
            name_normalized="lincoln high school",
            state_code="OR",
        )
        results = match_institution(query, self.db)
        assert "name_score" in results[0].score_breakdown
        assert "address_score" in results[0].score_breakdown
        assert "state_match" in results[0].score_breakdown
        assert "zip_score" in results[0].score_breakdown
