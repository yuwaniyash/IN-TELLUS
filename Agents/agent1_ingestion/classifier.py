"""
classifier.py
Person 3 -- NLP component of Agent 1.

Classifies a raw text fragment extracted from a bill into one of:
    quantity | unit | date | site_name | unknown

Uses a 3-tier cascade:
    1. Rule-based (regex) -- fast, free, handles predictable formats
    2. spaCy NER          -- real NLP model, catches proper nouns (site/org names)
    3. LLM fallback (stub) -- last resort for genuinely ambiguous fragments,
                              to be replaced with a real LLM call by Person 4
"""

import re
import spacy
from dateutil import parser as dateutil_parser
from dateutil.parser import ParserError

from unit_lookup import lookup_unit
from site_lookup import normalize_site_name

# Load once at module level -- loading per-call would be extremely slow.
_NLP = spacy.load("en_core_web_sm")

# Words that must NEVER be classified as a site/org name, even if spaCy's
# NER model tags them as one. Found via real testing: spaCy tagged the
# single capitalized word "DIESEL" as an ORG entity (false positive).
NON_SITE_DENYLIST = {
    "diesel", "petrol", "electricity", "fuel", "water", "gas",
    "kwh", "litres", "liters", "gallons", "units",
    # Missing-data markers -- spaCy's NER has a known quirk of tagging
    # "N/A" as an ORG entity, which would otherwise slip through as a
    # false-positive site-name. Real bills/logs use these often (seen in
    # the team's own fuel CSV, e.g. blank Supplier/DriverOperator cells).
    "n/a", "na", "none", "null", "-",
}

# Regex patterns for the predictable, structured fields.
# Quantity: handles comma thousands-separators (e.g. "4,500").
# Deliberately does NOT match a leading "-": negative consumption values
# are data-entry errors, not valid quantities (see _looks_like_negative_number).
QUANTITY_PATTERN = re.compile(r"^[\d,]+(\.\d+)?$")

# Matched separately from QUANTITY_PATTERN and checked FIRST in the cascade.
# This matters: without an early, dedicated check, a negative number like
# "-38.93" would fail QUANTITY_PATTERN and then get handed to dateutil's
# date parser, which will happily (and wrongly) parse it as a real date
# (e.g. "-38.93" -> 2038-09-08). Catching it here stops that misparse and
# correctly routes it to the LLM tier as a flagged, unresolved value instead.
NEGATIVE_NUMBER_PATTERN = re.compile(r"^-[\d,]+(\.\d+)?$")

# A conservative set of known unit words/abbreviations, used to short-circuit
# unit detection before falling through to NLP/LLM.
UNIT_WORDS = {
    "kwh", "units", "l", "litre", "litres", "liter", "liters",
    "gallon", "gallons", "gal", "m3",
}


def _looks_like_quantity(text: str) -> bool:
    return bool(QUANTITY_PATTERN.match(text.strip()))


def _looks_like_negative_number(text: str) -> bool:
    return bool(NEGATIVE_NUMBER_PATTERN.match(text.strip()))


def _looks_like_unit(text: str) -> bool:
    return text.strip().lower() in UNIT_WORDS


def _looks_like_date(text: str) -> dict | None:
    """
    Attempts to parse text as a date using dateutil, which handles the
    wide variety of real-world formats found in actual bills
    (e.g. "03-Jul-2026", "23.07.2026", "20 July 2026").

    Returns a result dict if it parses AND the text does not already
    look like a bare quantity (guards against numbers like "9999.99"
    being misread as a date, which dateutil's fuzzy parsing can do).
    """
    stripped = text.strip()
    if _looks_like_quantity(stripped):
        return None
    try:
        parsed = dateutil_parser.parse(stripped, fuzzy=False)
        return {
            "label": "date",
            "value": parsed.date().isoformat(),
            "resolved_by": "rules",
        }
    except (ParserError, ValueError, OverflowError):
        return None


def _rule_based_classify(text: str) -> dict | None:
    """Tier 1: try fast, deterministic rules first."""
    stripped = text.strip()
    if not stripped:
        return None

    # Negative numbers are data-entry errors, not valid quantities -- and
    # must never reach the date check below (dateutil will misparse them).
    # Returning None here sends them straight to the LLM/review tier.
    if _looks_like_negative_number(stripped):
        return None

    if _looks_like_quantity(stripped):
        return {"label": "quantity", "value": stripped, "resolved_by": "rules"}

    if _looks_like_unit(stripped):
        unit_info = lookup_unit(stripped)
        return {"label": "unit", "value": stripped, "unit_info": unit_info, "resolved_by": "rules"}

    date_result = _looks_like_date(stripped)
    if date_result:
        return date_result

    return None


def _spacy_classify(text: str) -> dict | None:
    """
    Tier 2: real NLP model (spaCy NER). Used specifically for
    unpredictable proper nouns -- site/organization names -- that
    regex cannot reliably catch.

    Bills are frequently in ALL CAPS, and spaCy's small model performs
    noticeably worse on all-caps text than on normal title case, so we
    normalize casing before running NER.
    """
    stripped = text.strip()
    if not stripped:
        return None

    # Never let spaCy call a known non-site word a site name.
    if stripped.lower() in NON_SITE_DENYLIST:
        return None

    normalized_for_ner = stripped.title() if stripped.isupper() else stripped
    doc = _NLP(normalized_for_ner)

    for ent in doc.ents:
        if ent.label_ in ("ORG", "GPE", "FAC", "LOC"):
            site_info = normalize_site_name(stripped)
            return {
                "label": "site-name",
                "value": site_info["site"],
                "site_info": site_info,
                "resolved_by": "nlp",
            }

    return None


def _llm_fallback_stub(text: str) -> dict:
    """
    Tier 3: last resort for fragments neither rules nor spaCy could
    confidently classify.

    TODO (Person 4): replace this stub with a real LLM API call.
    The LLM should be given the raw fragment and asked to classify it
    as quantity/unit/date/site_name, or return "unknown" if it
    genuinely cannot tell -- it must not guess with false confidence.
    """
    return {
        "label": "unknown",
        "value": text.strip(),
        "resolved_by": "llm_stub",
        "needs_review": True,
    }


def classify_fragment(text: str) -> dict:
    """
    Classifies a single text fragment through the 3-tier cascade.
    Returns a dict describing the label, value, and which tier
    resolved it (useful for auditability / debugging).
    """
    if text is None or not str(text).strip():
        return {"label": "unknown", "value": "", "resolved_by": "empty_input"}

    result = _rule_based_classify(str(text))
    if result:
        return result

    result = _spacy_classify(str(text))
    if result:
        return result

    return _llm_fallback_stub(str(text))


def classify_fragments(fragments: list[str]) -> list[dict]:
    """Convenience wrapper to classify a list of fragments."""
    return [classify_fragment(f) for f in fragments]