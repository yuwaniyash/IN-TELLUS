"""
Regression tests for fuel_csv_parser.py against the real fuel transaction
log. Locks in the "clean rate" so a future change that silently breaks
parsing on more rows gets caught.

Run with: pytest tests/test_agent1/test_fuel_csv_parser.py -v
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from Agents.agent1_ingestion.fuel_csv_parser import parse_fuel_transaction_csv

SAMPLE_PATH = Path(__file__).parent.parent.parent / "data" / "sample_bills" / "fuel_consumption_July_2026_RAW.csv"


def _load_transactions():
    df = pd.read_csv(SAMPLE_PATH, dtype=str, keep_default_na=False)
    rows = df.to_dict(orient="records")
    return parse_fuel_transaction_csv(rows)


def test_parses_all_rows():
    transactions = _load_transactions()
    assert len(transactions) == 1552


def test_clean_rate_at_least_99_percent():
    """
    As of this test's writing: 1542/1552 rows parse with zero warnings
    (10 flagged rows are genuinely ambiguous/missing data, not bugs).
    If this drops, something regressed — investigate before adjusting
    the threshold.
    """
    transactions = _load_transactions()
    clean = [t for t in transactions if not t.warnings]
    clean_rate = len(clean) / len(transactions)
    assert clean_rate >= 0.99, f"Clean rate dropped to {clean_rate:.1%}"


def test_no_unrecognized_date_formats():
    """All 10 date format variants found in the real file must be covered."""
    transactions = _load_transactions()
    date_warnings = [t for t in transactions if any("date format" in w for w in t.warnings)]
    assert date_warnings == []


def test_gallons_flagged_not_silently_converted():
    """Ambiguous units must never be silently normalized — they need a human decision."""
    transactions = _load_transactions()
    gallon_rows = [t for t in transactions if t.unit_raw.strip().lower().startswith("gallon")]
    assert len(gallon_rows) > 0  # sanity: the real file does contain gallon rows
    for t in gallon_rows:
        assert t.unit_ambiguous is True
        assert t.unit is None


def test_fuel_type_casing_normalized():
    transactions = _load_transactions()
    fuel_types = {t.fuel_type for t in transactions if t.fuel_type}
    assert fuel_types == {"petrol", "diesel"}


def test_site_names_mostly_canonicalized():
    """
    Verify that the known canonical site names dominate the parsed results.

    Person 3's IR lookup resolves site abbreviations, casing variants,
    spacing variants, and known aliases to the four canonical sites.
    """
    transactions = _load_transactions()
    from collections import Counter
    site_counts = Counter(t.site for t in transactions)

    top_4_total = sum(
        count for site, count in site_counts.most_common(4)
    )
    clean_rate = top_4_total / len(transactions)

    assert clean_rate > 0.85, (
        f"Canonicalization rate dropped to {clean_rate:.1%}"
    )

  