"""
tests/test_agent2/test_trends.py
==================================
Unit tests for Trend Analysis: Anomaly Detection + Budget Forecasting
(Person 2, Agent 2).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Agents.agent2_calc.trends import (
    check_sufficient_history,
    detect_anomalies,
    detect_recurring_pattern,
    forecast_next_period,
    check_budget,
    analyze_trend,
)


def series(values, start="2026-01", site="Site A"):
    """Helper: builds a chronological monthly series from a list of values."""
    year, month = map(int, start.split("-"))
    out = []
    for v in values:
        out.append({"period": f"{year:04d}-{month:02d}", "value": v, "site": site})
        month += 1
        if month > 12:
            month = 1
            year += 1
    return out


# ---------- sufficiency gate ----------

def test_insufficient_history_flagged():
    s = series([100, 110])
    check = check_sufficient_history(s)
    assert check["sufficient"] is False
    assert check["periods_available"] == 2


def test_sufficient_history_passes_at_three():
    s = series([100, 110, 105])
    check = check_sufficient_history(s)
    assert check["sufficient"] is True


# ---------- anomaly detection ----------

def test_stable_series_no_anomalies():
    s = series([100, 100, 100, 100, 100])
    flags = detect_anomalies(s)
    assert all(f.flagged is False for f in flags)


def test_spike_is_flagged():
    s = series([100, 100, 100, 100, 200])
    flags = detect_anomalies(s)
    last = flags[-1]
    assert last.flagged is True
    assert last.direction == "above"
    assert last.trigger in ("pct_deviation", "z_score", "both")


def test_drop_is_flagged_as_below():
    s = series([100, 100, 100, 100, 40])
    flags = detect_anomalies(s)
    last = flags[-1]
    assert last.flagged is True
    assert last.direction == "below"


def test_small_fluctuation_not_flagged():
    s = series([100, 100, 100, 108])  # 8% deviation, under the 30% threshold
    flags = detect_anomalies(s)
    assert flags[-1].flagged is False


# ---------- recurring vs one-time pattern ----------

def test_isolated_spike_is_one_time():
    s = series([100, 100, 100, 200, 100])
    flags = detect_anomalies(s)
    pattern = detect_recurring_pattern(flags)
    assert pattern["pattern"] == "one_time"


def test_consecutive_spikes_are_recurring():
    s = series([100, 100, 100, 200, 200])
    flags = detect_anomalies(s)
    pattern = detect_recurring_pattern(flags)
    assert pattern["pattern"] == "recurring"
    assert len(pattern["consecutive_runs"]) >= 1
    assert len(pattern["consecutive_runs"][0]) >= 2


def test_no_anomalies_gives_none_pattern():
    s = series([100, 100, 100, 100])
    flags = detect_anomalies(s)
    pattern = detect_recurring_pattern(flags)
    assert pattern["pattern"] == "none"


# ---------- forecasting ----------

def test_forecast_insufficient_data_with_one_point():
    s = series([100])
    forecast = forecast_next_period(s)
    assert forecast["method"] == "insufficient_data"
    assert forecast["forecast_value"] is None


def test_forecast_two_points_is_low_confidence():
    s = series([100, 120])
    forecast = forecast_next_period(s)
    assert forecast["method"] == "two_point_extrapolation"
    assert forecast["confidence"] == "low"
    assert forecast["forecast_value"] == 140.0  # straight line continuation


def test_forecast_linear_trend_is_accurate_and_high_confidence():
    s = series([100, 110, 120, 130, 140])  # perfectly linear, slope +10
    forecast = forecast_next_period(s)
    assert forecast["method"] == "linear_regression"
    assert forecast["slope_per_period"] == 10.0
    assert forecast["forecast_value"] == 150.0
    assert forecast["r_squared"] == 1.0
    assert forecast["confidence"] == "high"


def test_forecast_determinism():
    s = series([100, 95, 130, 110, 140])
    f1 = forecast_next_period(s)
    f2 = forecast_next_period(s)
    assert f1 == f2


# ---------- budget check ----------

def test_budget_over():
    result = check_budget(forecast_value=150.0, budget=140.0)
    assert result["status"] == "over_budget"
    assert result["overrun_amount"] == 10.0


def test_budget_under():
    result = check_budget(forecast_value=80.0, budget=150.0)
    assert result["status"] == "under_budget"


def test_budget_on_target():
    result = check_budget(forecast_value=145.0, budget=150.0)
    assert result["status"] == "on_budget"


def test_budget_missing_inputs_not_evaluable():
    result = check_budget(forecast_value=None, budget=150.0)
    assert result["status"] == "not_evaluable"
    result2 = check_budget(forecast_value=150.0, budget=None)
    assert result2["status"] == "not_evaluable"


def test_budget_zero_not_evaluable():
    result = check_budget(forecast_value=100.0, budget=0)
    assert result["status"] == "not_evaluable"


# ---------- full pipeline ----------

def test_analyze_trend_full_pipeline_determinism():
    s = series([100, 100, 100, 100, 200, 200])
    r1 = analyze_trend(s, metric_name="scope2_kg", budget=250.0)
    r2 = analyze_trend(s, metric_name="scope2_kg", budget=250.0)
    assert r1 == r2
    assert r1["history_check"]["sufficient"] is True
    assert r1["pattern"]["pattern"] == "recurring"
    assert r1["budget_check"]["status"] in ("over_budget", "on_budget", "under_budget")


def test_analyze_trend_insufficient_history_skips_budget_check():
    s = series([100, 110])
    r = analyze_trend(s, metric_name="scope2_kg", budget=250.0)
    assert r["history_check"]["sufficient"] is False
    assert r["budget_check"]["status"] == "not_evaluable"
    assert r["anomalies"] == []


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
