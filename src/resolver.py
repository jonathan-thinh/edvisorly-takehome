"""
School-at-date resolution logic.

Given a partner payload containing a school name/identifier and a date (e.g., when
a student attended), resolves which institution record and version apply.

This is the "harder piece" called out in the case study instructions:
    "resolving 'school at date X' given a partner payload"

Resolution pipeline:
1. Parse and normalize the input
2. Check partner crosswalk for a known mapping
3. If no crosswalk hit, run fuzzy matching
4. Once we have an institution_id, find the version that was active at the given date
5. If the school has merged/renamed since, trace the lineage to the current entity
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

from normalizer import normalize_school_name
from matcher import (
    MatchInput, InstitutionRecord, MatchCandidate,
    match_institution, classify_match,
)


@dataclass
class PartnerPayload:
    """Represents incoming data from a partner about a school on a transcript."""
    partner_code: str
    school_name: str
    school_id: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    ceeb_code: Optional[str] = None
    nces_id: Optional[str] = None
    transcript_date: Optional[date] = None  # when the student attended


@dataclass
class InstitutionVersion:
    """A point-in-time snapshot of an institution's attributes."""
    institution_id: str
    name: str
    status: str
    valid_from: date
    valid_to: Optional[date] = None


@dataclass
class LifecycleEvent:
    """A lifecycle event for an institution."""
    institution_id: str
    event_type: str  # 'merged', 'renamed', 'closed', etc.
    event_date: date
    related_institution_id: Optional[str] = None


@dataclass
class ResolutionResult:
    """The outcome of resolving a school at a given date."""
    original_institution_id: Optional[str]
    resolved_institution_id: Optional[str]  # may differ if school merged/renamed
    institution_name_at_date: Optional[str]
    current_institution_name: Optional[str]
    transcript_date: Optional[date]
    match_confidence: float
    match_method: str
    lineage_trace: list[str]  # chain of IDs if merge lineage was followed
    status: str  # 'resolved', 'pending_review', 'unresolved'
    notes: str = ""


# --- Simulated database layer (in production, these would be SQL queries) ---

class InstitutionDB:
    """
    Simulated database for demonstration. In production, these methods would
    execute SQL queries against the schema defined in /schema/.
    """

    def __init__(self):
        self.institutions: list[InstitutionRecord] = []
        self.versions: list[InstitutionVersion] = []
        self.lifecycle_events: list[LifecycleEvent] = []
        self.crosswalk: dict[tuple[str, str], str] = {}  # (partner_code, school_id) → institution_id

    def lookup_crosswalk(self, partner_code: str, school_id: Optional[str]) -> Optional[str]:
        """Check if we have a known mapping for this partner + school ID."""
        if school_id:
            return self.crosswalk.get((partner_code, school_id))
        return None

    def get_version_at_date(self, institution_id: str, target_date: date) -> Optional[InstitutionVersion]:
        """
        Find the institution_version row where valid_from <= target_date < valid_to.
        This is the SQL equivalent of:
            SELECT * FROM institution_version
            WHERE institution_id = :id
              AND valid_from <= :date
              AND (valid_to IS NULL OR valid_to > :date)
        """
        for v in self.versions:
            if v.institution_id != institution_id:
                continue
            if v.valid_from <= target_date and (v.valid_to is None or v.valid_to > target_date):
                return v
        return None

    def get_current_version(self, institution_id: str) -> Optional[InstitutionVersion]:
        """Get the current (valid_to IS NULL) version."""
        for v in self.versions:
            if v.institution_id == institution_id and v.valid_to is None:
                return v
        return None

    def trace_merge_lineage(self, institution_id: str, max_depth: int = 10) -> list[str]:
        """
        If this school merged into another, follow the chain to find the
        current successor. Returns the chain of institution IDs.
        
        SQL equivalent uses the recursive CTE in v_merge_lineage.
        """
        chain = [institution_id]
        current_id = institution_id

        for _ in range(max_depth):
            merge_event = None
            for event in self.lifecycle_events:
                if (event.institution_id == current_id
                        and event.event_type == "merged"
                        and event.related_institution_id):
                    merge_event = event
                    break

            if merge_event is None:
                break

            current_id = merge_event.related_institution_id
            chain.append(current_id)

        return chain


def resolve_school_at_date(
    payload: PartnerPayload,
    db: InstitutionDB,
) -> ResolutionResult:
    """
    Main resolution function: given a partner payload, figure out:
    1. Which institution this refers to
    2. What that institution looked like at the transcript date
    3. What the current state of that institution is (including merges)

    This is the core logic that powers transcript processing.
    """
    transcript_date = payload.transcript_date or date.today()

    # Step 1: Try partner crosswalk
    crosswalk_hit = db.lookup_crosswalk(payload.partner_code, payload.school_id)
    if crosswalk_hit:
        version_at_date = db.get_version_at_date(crosswalk_hit, transcript_date)
        current_version = db.get_current_version(crosswalk_hit)
        lineage = db.trace_merge_lineage(crosswalk_hit)

        final_id = lineage[-1] if lineage else crosswalk_hit
        final_current = db.get_current_version(final_id) if final_id != crosswalk_hit else current_version

        return ResolutionResult(
            original_institution_id=crosswalk_hit,
            resolved_institution_id=final_id,
            institution_name_at_date=version_at_date.name if version_at_date else None,
            current_institution_name=final_current.name if final_current else None,
            transcript_date=transcript_date,
            match_confidence=0.99,
            match_method="crosswalk_exact",
            lineage_trace=lineage,
            status="resolved",
        )

    # Step 2: Fuzzy matching
    query = MatchInput(
        name=payload.school_name,
        name_normalized=normalize_school_name(payload.school_name),
        state_code=payload.state,
        city=payload.city,
        zip_code=payload.zip_code,
        ceeb_code=payload.ceeb_code,
        nces_id=payload.nces_id,
        address=payload.address,
        transcript_date=str(transcript_date),
    )

    candidates = match_institution(query, db.institutions)
    status, best = classify_match(candidates)

    if best is None:
        return ResolutionResult(
            original_institution_id=None,
            resolved_institution_id=None,
            institution_name_at_date=None,
            current_institution_name=None,
            transcript_date=transcript_date,
            match_confidence=0.0,
            match_method="none",
            lineage_trace=[],
            status="unresolved",
            notes=f"No candidates above threshold for '{payload.school_name}'",
        )

    inst_id = best.institution.id

    # Step 3: Get version at date and trace lineage
    version_at_date = db.get_version_at_date(inst_id, transcript_date)
    lineage = db.trace_merge_lineage(inst_id)
    final_id = lineage[-1] if lineage else inst_id
    final_current = db.get_current_version(final_id)

    return ResolutionResult(
        original_institution_id=inst_id,
        resolved_institution_id=final_id,
        institution_name_at_date=version_at_date.name if version_at_date else None,
        current_institution_name=final_current.name if final_current else None,
        transcript_date=transcript_date,
        match_confidence=best.overall_score,
        match_method=best.method,
        lineage_trace=lineage,
        status="resolved" if status == "auto_matched" else status,
        notes=f"Matched via {best.method} with score {best.overall_score:.4f}",
    )


# --- Demo ---

def build_demo_db() -> InstitutionDB:
    """Build a demo database with realistic test data."""
    db = InstitutionDB()

    db.institutions = [
        InstitutionRecord(
            id="EDV-001",
            name="Thomas Jefferson High School for Science and Technology",
            name_normalized=normalize_school_name("Thomas Jefferson High School for Science and Technology"),
            state_code="VA", city="Alexandria", zip_code="22312",
            nces_id="510180001234", ceeb_code="470001",
            aliases=[
                normalize_school_name("TJ High School"),
                normalize_school_name("Jefferson High"),
            ],
        ),
        InstitutionRecord(
            id="EDV-002",
            name="Lincoln High School",
            name_normalized=normalize_school_name("Lincoln High School"),
            state_code="OR", city="Portland", zip_code="97214",
            nces_id="410180005678",
            aliases=[normalize_school_name("Lincoln HS Portland")],
        ),
        InstitutionRecord(
            id="EDV-003",
            name="Washington Preparatory High School",
            name_normalized=normalize_school_name("Washington Preparatory High School"),
            state_code="CA", city="Los Angeles", zip_code="90047",
            aliases=[
                normalize_school_name("Washington Prep"),
                normalize_school_name("Wash Prep HS"),
            ],
        ),
        InstitutionRecord(
            id="EDV-004",
            name="Riverside Consolidated High School",
            name_normalized=normalize_school_name("Riverside Consolidated High School"),
            state_code="IL", city="Riverside", zip_code="60546",
        ),
        InstitutionRecord(
            id="EDV-005",
            name="Riverside-Brookfield High School",
            name_normalized=normalize_school_name("Riverside-Brookfield High School"),
            state_code="IL", city="Riverside", zip_code="60546",
        ),
    ]

    db.versions = [
        # Jefferson: name shortened in 2015
        InstitutionVersion("EDV-001", "Thomas Jefferson High School", "active",
                           date(1985, 9, 1), date(2015, 7, 1)),
        InstitutionVersion("EDV-001", "Thomas Jefferson High School for Science and Technology", "active",
                           date(2015, 7, 1), None),
        # Lincoln: stable
        InstitutionVersion("EDV-002", "Lincoln High School", "active",
                           date(1950, 9, 1), None),
        # Washington Prep: renamed in 2005
        InstitutionVersion("EDV-003", "Washington High School", "active",
                           date(1960, 9, 1), date(2005, 8, 1)),
        InstitutionVersion("EDV-003", "Washington Preparatory High School", "active",
                           date(2005, 8, 1), None),
        # Riverside Consolidated: closed/merged in 2018
        InstitutionVersion("EDV-004", "Riverside Consolidated High School", "active",
                           date(1970, 9, 1), date(2018, 6, 15)),
        InstitutionVersion("EDV-004", "Riverside Consolidated High School", "merged",
                           date(2018, 6, 15), None),
        # Riverside-Brookfield: absorbed Riverside Consolidated
        InstitutionVersion("EDV-005", "Riverside-Brookfield High School", "active",
                           date(1950, 9, 1), None),
    ]

    db.lifecycle_events = [
        LifecycleEvent("EDV-003", "renamed", date(2005, 8, 1)),
        LifecycleEvent("EDV-004", "merged", date(2018, 6, 15), related_institution_id="EDV-005"),
        LifecycleEvent("EDV-005", "absorbed", date(2018, 6, 15), related_institution_id="EDV-004"),
    ]

    db.crosswalk = {
        ("partner_a", "PA-JEF-001"): "EDV-001",
        ("partner_a", "PA-LIN-002"): "EDV-002",
        ("partner_b", "99042"): "EDV-003",
    }

    return db


if __name__ == "__main__":
    db = build_demo_db()

    print("=" * 90)
    print("SCHOOL-AT-DATE RESOLUTION DEMO")
    print("=" * 90)

    test_payloads = [
        PartnerPayload(
            partner_code="partner_a",
            school_name="Jefferson H.S.",
            school_id="PA-JEF-001",
            state="VA",
            transcript_date=date(2010, 6, 15),
        ),
        PartnerPayload(
            partner_code="unknown_partner",
            school_name="Washington H.S.",
            state="CA",
            city="Los Angeles",
            transcript_date=date(2003, 5, 20),
        ),
        PartnerPayload(
            partner_code="partner_c",
            school_name="Riverside Consolidated H.S.",
            state="IL",
            transcript_date=date(2015, 6, 1),
        ),
        PartnerPayload(
            partner_code="partner_c",
            school_name="Riverside Consolidated H.S.",
            state="IL",
            transcript_date=date(2020, 1, 1),  # after merge
        ),
        PartnerPayload(
            partner_code="partner_d",
            school_name="St. Marys Acadmy",  # OCR typo
            state="OR",
        ),
    ]

    for payload in test_payloads:
        result = resolve_school_at_date(payload, db)
        print(f"\n--- Payload: '{payload.school_name}' (date={payload.transcript_date}, partner={payload.partner_code})")
        print(f"  Status:          {result.status}")
        print(f"  Confidence:      {result.match_confidence:.4f}")
        print(f"  Method:          {result.match_method}")
        print(f"  Name at date:    {result.institution_name_at_date}")
        print(f"  Current name:    {result.current_institution_name}")
        print(f"  Original ID:     {result.original_institution_id}")
        print(f"  Resolved ID:     {result.resolved_institution_id}")
        if len(result.lineage_trace) > 1:
            print(f"  Merge lineage:   {' -> '.join(result.lineage_trace)}")
        if result.notes:
            print(f"  Notes:           {result.notes}")
