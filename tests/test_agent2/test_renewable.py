"""
tests/test_agent2/test_renewable.py
=====================================
Unit tests for Renewable Sizing Calculation (Person 3, Agent 2).
"""

import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Agents.agent2_calc.renewable import (
    size_renewable_system,
    evaluate_existing_system,
    load_solar_reference,
)

REF = load_solar_reference()
MID_PSH = REF["solar_irradiance_by_region"]["mid_country"]["peak_sun_hours"]
EFFICIENCY = REF["system_efficiency"]["value"]
ANNUAL_GEN_PER_KWP_MID = MID_PSH * 365 * EFFICIENCY  # kWh generated per kWp per year, mid-country tier


def test_full_offset_sizing_hits_target():
    result = size_renewable_system(annual_consumption_kwh=10000.0, region="mid_country", target_offset_pct=1.0)
    assert result["errors"] == []
    assert math.isclose(result["sizing"]["actual_offset_pct"], 1.0, rel_tol=1e-3)
    assert math.isclose(result["sizing"]["annual_generation_kwh"], 10000.0, rel_tol=1e-3)
    expected_size = 10000.0 / ANNUAL_GEN_PER_KWP_MID
    assert math.isclose(result["sizing"]["system_size_kwp"], expected_size, rel_tol=1e-3)


def test_no_export_when_generation_matches_consumption_exactly():
    result = size_renewable_system(annual_consumption_kwh=10000.0, region="mid_country", target_offset_pct=1.0)
    assert result["sizing"]["exported_kwh"] == 0.0
    assert math.isclose(result["sizing"]["self_consumed_kwh"], 10000.0, rel_tol=1e-3)


def test_fixed_size_mode_partial_offset():
    result = size_renewable_system(
        annual_consumption_kwh=10000.0, region="mid_country", system_size_kwp=5.0
    )
    assert result["errors"] == []
    assert result["assumptions"]["mode"] == "fixed_size"
    expected_gen = 5.0 * ANNUAL_GEN_PER_KWP_MID
    assert math.isclose(result["sizing"]["annual_generation_kwh"], expected_gen, rel_tol=1e-3)
    assert result["sizing"]["exported_kwh"] == 0.0  # generation < consumption here
    assert result["sizing"]["actual_offset_pct"] < 1.0


def test_oversized_system_produces_export():
    result = size_renewable_system(
        annual_consumption_kwh=5000.0, region="mid_country", system_size_kwp=10.0
    )
    assert result["sizing"]["exported_kwh"] > 0
    assert math.isclose(result["sizing"]["self_consumed_kwh"], 5000.0, rel_tol=1e-3)
    assert result["sizing"]["actual_offset_pct"] > 1.0


def test_cost_scales_with_system_size():
    small = size_renewable_system(annual_consumption_kwh=10000.0, system_size_kwp=5.0)
    large = size_renewable_system(annual_consumption_kwh=10000.0, system_size_kwp=10.0)
    assert large["cost"]["system_cost_lkr"] == small["cost"]["system_cost_lkr"] * 2


def test_missing_tariff_gives_not_evaluable_but_still_sizes():
    result = size_renewable_system(annual_consumption_kwh=10000.0, system_size_kwp=5.0)
    assert result["errors"] == []
    assert result["sizing"]["system_size_kwp"] == 5.0
    assert result["savings_and_payback"]["status"] == "not_evaluable"


def test_savings_and_payback_computed_with_tariff():
    result = size_renewable_system(
        annual_consumption_kwh=10000.0, system_size_kwp=5.0,
        effective_tariff_lkr_per_kwh=45.0,
    )
    sp = result["savings_and_payback"]
    assert sp["status"] == "ok"
    expected_gen = 5.0 * ANNUAL_GEN_PER_KWP_MID
    expected_savings = expected_gen * 45.0  # no export in this case
    assert math.isclose(sp["annual_savings_lkr"], expected_savings, rel_tol=1e-3)
    expected_payback = result["cost"]["system_cost_lkr"] / expected_savings
    assert math.isclose(sp["payback_years"], expected_payback, abs_tol=0.01)


def test_payback_accounts_for_export_at_feed_in_rate():
    result = size_renewable_system(
        annual_consumption_kwh=5000.0, system_size_kwp=10.0,
        effective_tariff_lkr_per_kwh=45.0, feed_in_tariff_lkr_per_kwh=20.0,
    )
    sp = result["savings_and_payback"]
    self_consumed = result["sizing"]["self_consumed_kwh"]
    exported = result["sizing"]["exported_kwh"]
    expected_savings = self_consumed * 45.0 + exported * 20.0
    assert math.isclose(sp["annual_savings_lkr"], expected_savings, rel_tol=1e-3)


def test_negative_consumption_is_an_error_not_a_crash():
    result = size_renewable_system(annual_consumption_kwh=-100.0)
    assert len(result["errors"]) > 0
    assert "sizing" not in result


def test_negative_system_size_is_an_error():
    result = size_renewable_system(annual_consumption_kwh=10000.0, system_size_kwp=-5.0)
    assert len(result["errors"]) > 0


def test_unknown_region_falls_back_with_warning_not_crash():
    result = size_renewable_system(annual_consumption_kwh=10000.0, region="atlantis")
    assert result["errors"] == []
    assert any("mid_country" in w for w in result["warnings"])


def test_custom_peak_sun_hours_overrides_region_tier():
    result_region = size_renewable_system(annual_consumption_kwh=10000.0, region="hill_country")
    result_custom = size_renewable_system(
        annual_consumption_kwh=10000.0, region="hill_country", custom_peak_sun_hours=6.0
    )
    assert result_custom["assumptions"]["peak_sun_hours_per_day"] == 6.0
    assert result_custom["sizing"]["system_size_kwp"] < result_region["sizing"]["system_size_kwp"]


def test_evaluate_existing_system_matches_fixed_size_mode():
    r1 = evaluate_existing_system(system_size_kwp=8.0, annual_consumption_kwh=12000.0, effective_tariff_lkr_per_kwh=40.0)
    r2 = size_renewable_system(annual_consumption_kwh=12000.0, system_size_kwp=8.0, effective_tariff_lkr_per_kwh=40.0)
    assert r1 == r2


def test_determinism():
    r1 = size_renewable_system(annual_consumption_kwh=8000.0, region="lowland_coastal", effective_tariff_lkr_per_kwh=42.0)
    r2 = size_renewable_system(annual_consumption_kwh=8000.0, region="lowland_coastal", effective_tariff_lkr_per_kwh=42.0)
    assert r1 == r2


def test_zero_savings_flags_no_payback_instead_of_dividing_by_zero():
    # A pathological but possible input: tariff of a vanishingly small positive value
    # combined with essentially no self-consumption should not crash on division.
    result = size_renewable_system(
        annual_consumption_kwh=1.0, system_size_kwp=0.0001,
        effective_tariff_lkr_per_kwh=0.0000001,
    )
    assert result["errors"] == []
    assert result["savings_and_payback"]["status"] in ("ok", "no_savings")


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
