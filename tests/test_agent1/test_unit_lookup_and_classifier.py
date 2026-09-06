# tests/test_agent1/test_unit_lookup_and_classifier.py
"""
Tests for Person 3's Step 1 (unit lookup) and Step 2 (fragment classifier).
Run with: pytest tests/test_agent1/
"""

import sys
import os

# Allow importing from Agents/agent1_ingestion without packaging it yet
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..", "Agents", "agent1_ingestion"),
)

from unit_lookup import lookup_unit
from classifier import classify_fragment, classify_fragments


# --- lookup_unit tests ---

def test_exact_match():
    result = lookup_unit("kWh")
    assert result["resolved"] is True
    assert result["canonical_unit"] == "kWh"
    assert result["match_type"] == "exact"


def test_case_and_whitespace_insensitive():
    result = lookup_unit("  Units  ")
    assert result["resolved"] is True
    assert result["canonical_unit"] == "kWh"


def test_fuzzy_match_catches_typo():
    result = lookup_unit("Kilowat-hours")  # missing a 't'
    assert result["resolved"] is True
    assert result["canonical_unit"] == "kWh"
    assert "fuzzy" in result["match_type"]


def test_unknown_unit_fails_safely():
    result = lookup_unit("completely made up nonsense")
    assert result["resolved"] is False
    assert result["canonical_unit"] is None


def test_empty_and_none_input():
    assert lookup_unit("")["resolved"] is False
    assert lookup_unit(None)["resolved"] is False


def test_gallons_converts_to_litres_not_matched_as_litres():
    # Real bug found against the team's fuel_consumption CSV: "gallons"
    # was fuzzy-matching to the "l" (litres) key with a 1.0 multiplier,
    # silently treating US gallons as litres.
    result = lookup_unit("gallons")
    assert result["resolved"] is True
    assert result["canonical_unit"] == "L"
    assert result["match_type"] == "exact"
    assert round(result["multiplier"], 5) == 3.78541


def test_diesel_is_not_matched_as_a_unit():
    # "DIESEL" is a fuel type, not a unit - it was fuzzy-matching to
    # "l" for the same reason gallons was. Short keys should only ever
    # match exactly.
    result = lookup_unit("DIESEL")
    assert result["resolved"] is False


# --- classifier tests ---

def test_classify_quantity():
    result = classify_fragment("245.6")
    assert result["label"] == "quantity"
    assert result["resolved_by"] == "rules"


def test_classify_large_quantity_not_misread_as_date():
    # dateutil's fuzzy fallback will happily misparse a bare number as
    # a date if you let it - this must stay a quantity.
    result = classify_fragment("9999.99")
    assert result["label"] == "quantity"


def test_classify_unit():
    assert classify_fragment("kWh")["label"] == "unit"


def test_classify_date():
    assert classify_fragment("12/08/2026")["label"] == "date"


def test_classify_word_month_date():
    # Regex alone can't catch this - needs the dateutil fallback tier.
    result = classify_fragment("03-Jul-2026")
    assert result["label"] == "date"


def test_classify_dot_separated_date():
    result = classify_fragment("23.07.2026")
    assert result["label"] == "date"


def test_classify_site_name_via_nlp():
    # A real spaCy NER hit, not just a rules fallback.
    result = classify_fragment("LANKA ELECTRICITY COMPANY")
    assert result["label"] == "site-name"
    assert result["resolved_by"] == "nlp"


def test_classify_short_site_name_falls_to_llm_stub():
    # spaCy's small model isn't confident on very short two-word
    # branch names without more context - this is an honest, expected
    # limit, and it should fall through to the LLM tier rather than
    # get a guessed label.
    result = classify_fragment("Colombo Branch")
    assert result["resolved_by"] == "llm_stub"
    assert result["label"] == "unknown"


def test_diesel_not_misclassified_as_site_name():
    # Guards against spaCy NER false-positiving a single capitalized
    # fuel-type word as an ORG entity.
    result = classify_fragment("DIESEL")
    assert result["resolved_by"] == "llm_stub"
    assert result["label"] == "unknown"


def test_negative_quantity_flagged_not_accepted():
    # Negative fuel/consumption values are data-entry errors and
    # should be flagged (fall to the LLM tier), never silently
    # accepted as a valid quantity.
    result = classify_fragment("-38.93")
    assert result["label"] != "quantity"
    assert result["resolved_by"] == "llm_stub"


def test_missing_data_marker_falls_to_llm_stub():
    result = classify_fragment("N/A")
    assert result["resolved_by"] == "llm_stub"
    assert result["label"] == "unknown"


def test_classify_fragments_batch():
    fragments = ["245.6", "kWh", "12/08/2026", "LANKA ELECTRICITY COMPANY"]
    results = classify_fragments(fragments)
    labels = [r["label"] for r in results]
    assert labels == ["quantity", "unit", "date", "site-name"]