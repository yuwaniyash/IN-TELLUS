import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Agents.agent2_calc.security_validation import validate_analyze_request


def test_valid_minimal_request():
    result = validate_analyze_request(file_id=1)
    assert result["valid"] is True


def test_rejects_non_integer_file_id():
    result = validate_analyze_request(file_id="1")
    assert result["valid"] is False


def test_rejects_zero_or_negative_file_id():
    assert validate_analyze_request(file_id=0)["valid"] is False
    assert validate_analyze_request(file_id=-5)["valid"] is False


def test_rejects_bool_as_file_id():
    # bool is a subclass of int in Python -- must be explicitly excluded
    assert validate_analyze_request(file_id=True)["valid"] is False


def test_rejects_negative_budget():
    result = validate_analyze_request(file_id=1, monthly_budget_lkr=-100)
    assert result["valid"] is False


def test_accepts_zero_budget():
    result = validate_analyze_request(file_id=1, monthly_budget_lkr=0)
    assert result["valid"] is True


def test_rejects_invalid_region():
    result = validate_analyze_request(file_id=1, region="mars")
    assert result["valid"] is False


def test_accepts_valid_region():
    result = validate_analyze_request(file_id=1, region="hill_country")
    assert result["valid"] is True


def test_rejects_dangerous_sector_string():
    result = validate_analyze_request(file_id=1, sector="<script>alert(1)</script>")
    assert result["valid"] is False


def test_rejects_oversized_sector_string():
    result = validate_analyze_request(file_id=1, sector="a" * 300)
    assert result["valid"] is False


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
