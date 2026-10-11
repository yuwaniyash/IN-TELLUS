import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Agents.agent2_calc.nlp_context import extract_keyword_flags, extract_entities, process_free_text


def test_keyword_flag_detected():
    flags = extract_keyword_flags("We installed new equipment in the warehouse last month.")
    assert any("new equipment" in f for f in flags)


def test_no_keyword_flags_for_unrelated_text():
    flags = extract_keyword_flags("Everything ran as normal this month.")
    assert flags == []


def test_keyword_flags_handles_none_and_empty_string():
    assert extract_keyword_flags(None) == []
    assert extract_keyword_flags("") == []


def test_multiple_keywords_all_flagged():
    flags = extract_keyword_flags("There was a generator running due to an outage, and a small leak.")
    assert len(flags) >= 3


def test_entities_returns_list_without_crashing_regardless_of_spacy_availability():
    result = extract_entities("Colombo HQ increased output in March.")
    assert isinstance(result, list)


def test_process_free_text_handles_none():
    result = process_free_text(None)
    assert result["keyword_flags"] == []
    assert result["entities"] == []
    assert result["source_text"] is None


def test_process_free_text_shape():
    result = process_free_text("The site had a meter fault this billing period.")
    assert "keyword_flags" in result
    assert "entities" in result
    assert "spacy_available" in result
    assert any("meter" in f.lower() for f in result["keyword_flags"])


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
