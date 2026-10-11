import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import Agents.agent3_advisory.schemas as schemas_module

# query_composition.py does `from schemas import ...` (a top-level import that
# only works when the agent3_advisory folder itself is on sys.path). Point that
# name at the real package module just for the import, then restore it, so this
# test also works when the whole suite is run from the project root.
_saved = sys.modules.get("schemas")
sys.modules["schemas"] = schemas_module
try:
    from Agents.agent3_advisory.query_composition import compose_query
finally:
    if _saved is None:
        sys.modules.pop("schemas", None)
    else:
        sys.modules["schemas"] = _saved

from Agents.agent3_advisory.schemas import Agent3Input, Tier


def _site(site="Kandy Plant", resource="fuel", anomalies=None, budget_check=None):
    return {
        "site": site,
        "resource_type": resource,
        "trend": {
            "history_check": {"sufficient": True},
            "anomalies": anomalies or [],
            "budget_check": budget_check,
        },
    }


def _anomaly(flagged=True, pct=0.32, direction="above", period="2025-03"):
    return {"period": period, "trigger": "both", "direction": direction,
            "value": 100.0, "pct_deviation": pct, "flagged": flagged}


def _input(site_reports=None, resource="fuel", total=2340, **kwargs):
    return Agent3Input(
        company_id=1,
        diagnostics={
            "file_id": 1,
            "resource_type": resource,
            "footprint": {"company_total": {"total_kg": total}},
            "site_reports": site_reports or [],
        },
        tier=Tier.STANDARD,
        **kwargs,
    )


def test_zero_signals_triggers_fallback():
    result = compose_query(_input(site_reports=[]))
    assert result.used_fallback_query is True
    assert result.signals_used == []
    assert "2340" in result.query_text


def test_single_anomaly_signal_skips_fallback():
    result = compose_query(_input(site_reports=[_site(anomalies=[_anomaly()])]))
    assert result.used_fallback_query is False
    assert len(result.signals_used) == 1
    assert "Kandy Plant fuel consumption above baseline by 32% in 2025-03" in result.query_text


def test_unflagged_anomaly_is_ignored():
    result = compose_query(_input(site_reports=[_site(anomalies=[_anomaly(flagged=False)])]))
    assert result.used_fallback_query is True


def test_multiple_signals_are_all_composed():
    result = compose_query(_input(
        site_reports=[_site(
            anomalies=[_anomaly()],
            budget_check={"status": "over_budget", "message": "10% over budget"},
        )],
        sl_framework_applicable=True,
        user_context="reduce diesel costs",
    ))
    assert result.used_fallback_query is False
    assert len(result.signals_used) == 4
    assert "above baseline by 32%" in result.query_text
    assert "Kandy Plant over budget: 10% over budget" in result.query_text
    assert "Sri Lanka NGRS framework alignment" in result.query_text
    assert "reduce diesel costs" in result.query_text


def test_electricity_anomaly_uses_electricity_vocabulary():
    result = compose_query(_input(
        site_reports=[_site(site="Colombo HQ", resource="electricity", anomalies=[_anomaly()])],
        resource="electricity",
    ))
    assert "HVAC" in result.query_text
    assert "generator" not in result.query_text


def test_multiple_sites_add_cross_site_signal():
    result = compose_query(_input(site_reports=[_site(site="A"), _site(site="B")]))
    assert result.used_fallback_query is False
    assert "cross-site comparison" in result.signals_used


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))