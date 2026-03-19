"""Unit tests for the school-at-date resolver."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import date
from resolver import (
    PartnerPayload, InstitutionVersion, LifecycleEvent, ResolutionResult,
    InstitutionDB, resolve_school_at_date, build_demo_db,
)
from normalizer import normalize_school_name
from matcher import InstitutionRecord


class TestInstitutionDB:
    def setup_method(self):
        self.db = InstitutionDB()
        self.db.versions = [
            InstitutionVersion("A", "Alpha School", "active", date(2000, 1, 1), date(2010, 1, 1)),
            InstitutionVersion("A", "Alpha Academy", "active", date(2010, 1, 1), None),
            InstitutionVersion("B", "Beta School", "active", date(1990, 1, 1), None),
        ]
        self.db.lifecycle_events = [
            LifecycleEvent("C", "merged", date(2015, 6, 1), related_institution_id="D"),
            LifecycleEvent("D", "merged", date(2020, 6, 1), related_institution_id="E"),
        ]
        self.db.crosswalk = {("partner_x", "P-001"): "A"}

    def test_version_at_date_early(self):
        v = self.db.get_version_at_date("A", date(2005, 6, 15))
        assert v is not None
        assert v.name == "Alpha School"

    def test_version_at_date_late(self):
        v = self.db.get_version_at_date("A", date(2015, 6, 15))
        assert v is not None
        assert v.name == "Alpha Academy"

    def test_version_at_date_boundary(self):
        v = self.db.get_version_at_date("A", date(2010, 1, 1))
        assert v is not None
        assert v.name == "Alpha Academy"  # valid_from is inclusive

    def test_version_before_any(self):
        v = self.db.get_version_at_date("A", date(1990, 1, 1))
        assert v is None

    def test_current_version(self):
        v = self.db.get_current_version("A")
        assert v.name == "Alpha Academy"
        assert v.valid_to is None

    def test_crosswalk_lookup_hit(self):
        result = self.db.lookup_crosswalk("partner_x", "P-001")
        assert result == "A"

    def test_crosswalk_lookup_miss(self):
        result = self.db.lookup_crosswalk("partner_x", "P-999")
        assert result is None

    def test_crosswalk_no_school_id(self):
        result = self.db.lookup_crosswalk("partner_x", None)
        assert result is None

    def test_merge_lineage_single(self):
        chain = self.db.trace_merge_lineage("C")
        assert chain == ["C", "D", "E"]

    def test_merge_lineage_no_merge(self):
        chain = self.db.trace_merge_lineage("B")
        assert chain == ["B"]


class TestResolveSchoolAtDate:
    def setup_method(self):
        self.db = build_demo_db()

    def test_crosswalk_hit_returns_resolved(self):
        payload = PartnerPayload(
            partner_code="partner_a",
            school_name="Jefferson H.S.",
            school_id="PA-JEF-001",
            state="VA",
            transcript_date=date(2010, 6, 15),
        )
        result = resolve_school_at_date(payload, self.db)
        assert result.status == "resolved"
        assert result.match_confidence == 0.99
        assert result.match_method == "crosswalk_exact"
        assert result.institution_name_at_date == "Thomas Jefferson High School"

    def test_crosswalk_hit_shows_current_name(self):
        payload = PartnerPayload(
            partner_code="partner_a",
            school_name="Jefferson H.S.",
            school_id="PA-JEF-001",
            state="VA",
            transcript_date=date(2010, 6, 15),
        )
        result = resolve_school_at_date(payload, self.db)
        assert result.current_institution_name == "Thomas Jefferson High School for Science and Technology"

    def test_fuzzy_match_renamed_school(self):
        payload = PartnerPayload(
            partner_code="unknown",
            school_name="Washington H.S.",
            state="CA",
            city="Los Angeles",
            transcript_date=date(2003, 5, 20),
        )
        result = resolve_school_at_date(payload, self.db)
        assert result.status in ("resolved", "pending_review")
        assert result.institution_name_at_date == "Washington High School"
        assert result.current_institution_name == "Washington Preparatory High School"

    def test_merged_school_traces_lineage(self):
        payload = PartnerPayload(
            partner_code="partner_c",
            school_name="Riverside Consolidated H.S.",
            state="IL",
            transcript_date=date(2015, 6, 1),
        )
        result = resolve_school_at_date(payload, self.db)
        assert result.original_institution_id == "EDV-004"
        assert result.resolved_institution_id == "EDV-005"
        assert len(result.lineage_trace) == 2
        assert result.lineage_trace == ["EDV-004", "EDV-005"]

    def test_unresolved_no_match(self):
        payload = PartnerPayload(
            partner_code="partner_z",
            school_name="Completely Nonexistent School of Wizardry",
            state="ZZ",
        )
        result = resolve_school_at_date(payload, self.db)
        assert result.status == "unresolved"
        assert result.match_confidence == 0.0
        assert result.original_institution_id is None

    def test_default_date_is_today(self):
        payload = PartnerPayload(
            partner_code="partner_a",
            school_name="Jefferson H.S.",
            school_id="PA-JEF-001",
        )
        result = resolve_school_at_date(payload, self.db)
        assert result.transcript_date == date.today()
