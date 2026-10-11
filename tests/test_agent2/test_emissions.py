"""
tests/test_agent2/test_emissions.py
====================================
Unit tests for the Core Emissions Engine (Person 1, Agent 2).

Covers:
  - Determinism: identical input -> identical output, every call.
  - Correct Scope 1/2/3 tagging.
  - Correct factor selection for electricity, each fuel type/unit, water.
  - Graceful handling of missing/invalid data (no exceptions raised).
  - Aggregation totals sum correctly across sites and scopes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Agents.agent2_calc.emissions import (
    compute_emissions,
    compute_batch,
    aggregate_footprint,
    load_emission_factors,
)

FACTORS = load_emission_factors()


def test_determinism_same_input_same_output():
    record = {
        "resource_type": "electricity",
        "consumption": 1500.0,
        "unit": "kWh",
        "site": "Colombo HQ",
        "billing_period": "2026-07",
    }
    results = [compute_emissions(record, FACTORS) for _ in range(5)]
    co2e_values = [r.co2e_kg for r in results]
    assert len(set(co2e_values)) == 1, "Same input must produce identical output every time"
    assert co2e_values[0] == round(1500.0 * FACTORS["electricity"]["grid_default"]["factor_kg_co2_per_kwh"], 4)


def test_electricity_is_scope_2():
    record = {"resource_type": "electricity", "consumption": 1000.0, "unit": "kWh", "site": "A"}
    r = compute_emissions(record, FACTORS)
    assert r.scope == 2
    assert r.included_in_total is True
    assert r.errors == []
    assert r.co2e_kg > 0


def test_fuel_diesel_litres_is_scope_1():
    record = {
        "resource_type": "fuel", "fuel_type": "diesel",
        "consumption": 200.0, "unit": "L", "site": "Kandy Plant",
    }
    r = compute_emissions(record, FACTORS)
    assert r.scope == 1
    assert r.included_in_total is True
    expected = round(200.0 * FACTORS["fuel"]["diesel"]["factor_kg_co2e_per_litre"], 4)
    assert r.co2e_kg == expected


def test_fuel_lpg_kg_vs_litre_gives_different_factor():
    record_kg = {"resource_type": "fuel", "fuel_type": "lpg", "consumption": 10.0, "unit": "kg", "site": "A"}
    record_l = {"resource_type": "fuel", "fuel_type": "lpg", "consumption": 10.0, "unit": "L", "site": "A"}
    r_kg = compute_emissions(record_kg, FACTORS)
    r_l = compute_emissions(record_l, FACTORS)
    assert r_kg.co2e_kg != r_l.co2e_kg, "kg and litre factors for LPG must differ and both must be honoured"


def test_fuel_alias_resolution():
    record = {"resource_type": "fuel", "fuel_type": "gasoline", "consumption": 50.0, "unit": "L", "site": "A"}
    r = compute_emissions(record, FACTORS)
    assert r.errors == []
    assert r.factor_used == FACTORS["fuel"]["petrol"]["factor_kg_co2e_per_litre"]


def test_water_is_excluded_from_total_but_still_reported():
    record = {"resource_type": "water", "consumption": 500.0, "unit": "m3", "site": "A"}
    r = compute_emissions(record, FACTORS)
    assert r.scope is None
    assert r.included_in_total is False
    assert r.co2e_kg is not None  # still computed for context
    assert any("excluded" in w.lower() for w in r.warnings)


def test_missing_consumption_produces_error_not_exception():
    record = {"resource_type": "electricity", "unit": "kWh", "site": "A"}
    r = compute_emissions(record, FACTORS)
    assert r.co2e_kg is None
    assert len(r.errors) > 0


def test_unknown_fuel_type_produces_error_not_guess():
    record = {"resource_type": "fuel", "fuel_type": "unobtainium", "consumption": 10.0, "unit": "L", "site": "A"}
    r = compute_emissions(record, FACTORS)
    assert r.co2e_kg is None
    assert r.included_in_total is False
    assert len(r.errors) > 0


def test_unknown_resource_type_does_not_crash():
    record = {"resource_type": "compressed_air", "consumption": 10.0, "unit": "m3", "site": "A"}
    r = compute_emissions(record, FACTORS)
    assert r.co2e_kg is None
    assert len(r.errors) > 0


def test_negative_consumption_flagged():
    record = {"resource_type": "electricity", "consumption": -50.0, "unit": "kWh", "site": "A"}
    r = compute_emissions(record, FACTORS)
    assert r.co2e_kg is None
    assert any("negative" in e.lower() for e in r.errors)


def test_aggregate_footprint_sums_correctly_across_sites_and_scopes():
    records = [
        {"resource_type": "electricity", "consumption": 1000.0, "unit": "kWh", "site": "Site A"},
        {"resource_type": "fuel", "fuel_type": "diesel", "consumption": 100.0, "unit": "L", "site": "Site A"},
        {"resource_type": "electricity", "consumption": 500.0, "unit": "kWh", "site": "Site B"},
        {"resource_type": "water", "consumption": 200.0, "unit": "m3", "site": "Site B"},
        {"resource_type": "fuel", "fuel_type": "nonexistent_fuel", "consumption": 5.0, "unit": "L", "site": "Site B"},
    ]
    results = compute_batch(records, FACTORS)
    footprint = aggregate_footprint(results)

    grid_factor = FACTORS["electricity"]["grid_default"]["factor_kg_co2_per_kwh"]
    diesel_factor = FACTORS["fuel"]["diesel"]["factor_kg_co2e_per_litre"]

    expected_scope2 = round(1000.0 * grid_factor + 500.0 * grid_factor, 4)
    expected_scope1 = round(100.0 * diesel_factor, 4)

    assert footprint["company_total"]["scope2_kg"] == expected_scope2
    assert footprint["company_total"]["scope1_kg"] == expected_scope1
    assert footprint["company_total"]["scope3_kg"] == 0.0
    assert len(footprint["failed_records"]) == 1  # the nonexistent_fuel record
    assert "Site A" in footprint["by_site"]
    assert "Site B" in footprint["by_site"]
    assert footprint["by_site"]["Site A"]["records"] == 2
    # water excluded from Site B's total but recorded
    assert footprint["by_site"]["Site B"]["excluded_kg"] > 0


def test_aggregate_footprint_empty_list():
    footprint = aggregate_footprint([])
    assert footprint["company_total"]["total_kg"] == 0.0
    assert footprint["by_site"] == {}
    assert footprint["failed_records"] == []


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
