"""
Regression tests for rule_parser.py, using REAL sample bills (not synthetic
ones) — these caught actual bugs (ISO date format missing, account number
regex breaking on slashes, unit mismatched to the wrong value) that the
earlier synthetic-only tests didn't. Keep these bills as permanent fixtures;
don't replace them with fake ones.

Run with: pytest tests/test_agent1/test_rule_parser.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from Agents.agent1_ingestion.text_extraction import extract_text
from Agents.agent1_ingestion.rule_parser import parse_bill_text

SAMPLE_DIR = Path(__file__).parent.parent.parent / "data" / "sample_bills"


def test_real_water_bill():
    text = extract_text(str(SAMPLE_DIR / "water_bill_real.pdf"), "pdf")
    result = parse_bill_text(text)

    assert result.consumption.value == "850"
    assert result.unit_raw.value == "m³"
    assert result.billing_date.value == "2026-07-28"
    assert result.account_number.value == "08/42/105/928/14"
    assert result.missing_fields == []


def test_real_electricity_bill():
    text = extract_text(str(SAMPLE_DIR / "electricity_bill_real.pdf"), "pdf")
    result = parse_bill_text(text)

    assert result.consumption.value == "3450"
    assert result.unit_raw.value == "kWh"
    assert result.billing_date.value == "2026-07-28"
    assert result.account_number.value == "4471829"
    assert result.missing_fields == []


def test_synthetic_electricity_bill_still_works():
    """Regression guard — real-bill fixes shouldn't break the original synthetic case."""
    text = extract_text(str(SAMPLE_DIR / "electricity_bill_sample.pdf"), "pdf")
    result = parse_bill_text(text)

    assert result.consumption.value == "12450"
    assert result.missing_fields == []
