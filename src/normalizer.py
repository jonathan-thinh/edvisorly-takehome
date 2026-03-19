"""
School name and address normalization.

Transforms raw, inconsistent school names into a canonical form suitable for
matching. Handles common abbreviations, punctuation, OCR artifacts, and
directional prefixes.

The abbreviation map is ordered carefully: multi-word patterns (e.g. "sr h s")
come before their sub-patterns (e.g. "h s") to prevent partial matching.
Compound directionals (e.g. "n e" -> "northeast") come before single-letter
directionals (e.g. "n" -> "north").
"""

import re
from typing import Optional

# Multi-word patterns MUST come before their single-word sub-patterns.
# "sr h s" must match before "h s" can consume "h s" alone.
# Compound directionals must precede single-letter directionals.
ABBREVIATION_MAP = [
    # Multi-word school type patterns (longest first)
    (r"\bsr\.?\s*h\.?\s*s\.?\b", "senior high school"),
    (r"\bjr\.?\s*h\.?\s*s\.?\b", "junior high school"),
    (r"\bh\.?\s*s\.?\b", "high school"),
    (r"\bm\.?\s*s\.?\b", "middle school"),
    # School type single-word abbreviations
    (r"\belem\.?\b", "elementary"),
    (r"\bprep\.?\b", "preparatory"),
    (r"\bacad\.?\b", "academy"),
    (r"\btech\.?\b", "technical"),
    (r"\bvoc\.?\b", "vocational"),
    (r"\binst\.?\b", "institute"),
    (r"\bint'?l\.?\b", "international"),
    # Institutional abbreviations
    (r"\bcomm\.?\b", "community"),
    (r"\bcoll\.?\b", "college"),
    (r"\buniv\.?\b", "university"),
    # Prefix/title abbreviations
    (r"\bst\.?\b", "saint"),
    (r"\bmt\.?\b", "mount"),
    (r"\bft\.?\b", "fort"),
    (r"\bdr\.?\b", "doctor"),
    (r"\bjr\.?\b", "junior"),
    (r"\bsr\.?\b", "senior"),
    # Geographic abbreviations
    (r"\btwp\.?\b", "township"),
    (r"\bco\.?\b", "county"),
    (r"\bctr\.?\b", "center"),
    (r"\bregn?l\.?\b", "regional"),
    (r"\bvly\.?\b", "valley"),
    (r"\bdist\.?\b", "district"),
    (r"\bhts\.?\b", "heights"),
    (r"\bspgs?\.?\b", "springs"),
    # Compound directionals before single-letter
    (r"\bn\.?\s*w\.?\b", "northwest"),
    (r"\bn\.?\s*e\.?\b", "northeast"),
    (r"\bs\.?\s*w\.?\b", "southwest"),
    (r"\bs\.?\s*e\.?\b", "southeast"),
    # Single-letter directionals (applied last; only match isolated letters)
    (r"(?<![a-z])\bn\.?\b(?![a-z])", "north"),
    (r"(?<![a-z])\be\.?\b(?![a-z])", "east"),
    (r"(?<![a-z])\bw\.?\b(?![a-z])", "west"),
    # "s" is intentionally omitted as a standalone directional because it
    # collides too often with trailing "s" from possessives and plurals.
    # If "South" is abbreviated, it typically appears as "So." which we can add.
    (r"\bso\.?\b", "south"),
]


def normalize_school_name(name: Optional[str]) -> str:
    """
    Normalize a school name for matching.

    Steps:
    1. Lowercase
    2. Remove possessives
    3. Remove non-alphanumeric characters (keep spaces)
    4. Expand known abbreviations
    5. Collapse whitespace

    Examples:
        >>> normalize_school_name("St. Mary's H.S.")
        'saint marys high school'
        >>> normalize_school_name("JEFFERSON TWP. SR. H.S.")
        'jefferson township senior high school'
        >>> normalize_school_name("Mt. Pleasant Acad.")
        'mount pleasant academy'
    """
    if not name:
        return ""

    text = name.lower().strip()

    # Remove possessives before stripping punctuation
    text = re.sub(r"'s\b", "s", text)

    # Remove punctuation but keep spaces and alphanumeric
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Expand abbreviations (order matters — see ABBREVIATION_MAP docstring)
    for pattern, replacement in ABBREVIATION_MAP:
        text = re.sub(pattern, replacement, text)

    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text


def normalize_address(
    address: Optional[str],
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip_code: Optional[str] = None,
) -> str:
    """
    Normalize address components into a single comparable string.
    Strips punctuation, lowercases, and concatenates non-empty parts.
    """
    parts = []
    for part in [address, city, state, zip_code]:
        if part:
            cleaned = re.sub(r"[^a-z0-9\s]", " ", part.lower().strip())
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if cleaned:
                parts.append(cleaned)
    return " ".join(parts)


def extract_state_from_name(name: str) -> Optional[str]:
    """
    Attempt to extract a US state abbreviation if it appears at the end of the name.
    Only matches when the last token is a known 2-letter state code.
    """
    states = {
        "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga",
        "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md",
        "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
        "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
        "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy",
    }
    tokens = name.lower().split()
    if tokens and tokens[-1] in states:
        return tokens[-1].upper()
    return None


if __name__ == "__main__":
    test_names = [
        "St. Mary's H.S.",
        "JEFFERSON TWP. SR. H.S.",
        "Mt. Pleasant Acad.",
        "Martin Luther King Jr. High School",
        "N.E. Regional Voc. Tech. H.S.",
        "Abraham Lincoln H. S.",
        "W. Springfield Sr. H.S.",
    ]
    for name in test_names:
        print(f"  {name:45s} -> {normalize_school_name(name)}")
