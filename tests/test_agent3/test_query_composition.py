import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Agents.agent3_advisory.schemas import Agent3Input, Agent2Diagnostics, Anomaly, BudgetOutlook, Tier
from Agents.agent3_advisory.query_composition import compose_query


def test_zero_signals_triggers_fallback():
    agent_input = Agent3Input(
        diagnostics=Agent2Diagnostics(
            footprint={"total_co2e_kg": 2340, "breakdown_by_resource": {"electricity": 1800, "fuel": 540}},
            anomalies=None,
            sufficient_history=False,
        ),
        tier=Tier.STANDARD,
    )
    result = compose_query(agent_input)
    assert result.used_fallback_query is True
    assert "2340" in result.query_text


def test_single_anomaly_signal_skips_fallback():
    agent_input = Agent3Input(
        diagnostics=Agent2Diagnostics(
            footprint={"total_co2e_kg": 2340, "breakdown_by_resource": {"fuel": 540}},
            anomalies=[Anomaly(type="fuel", magnitude="+32%", period="2025-03")],
            sufficient_history=True,
        ),
        tier=Tier.STANDARD,
    )
    result = compose_query(agent_input)
    assert result.used_fallback_query is False
    assert result.query_text == "fuel anomaly +32% in 2025-03"


def test_multiple_signals_are_all_composed():
    agent_input = Agent3Input(
        diagnostics=Agent2Diagnostics(
            footprint={"total_co2e_kg": 2340, "breakdown_by_resource": {"fuel": 540}},
            anomalies=[Anomaly(type="fuel", magnitude="+32%", period="2025-03")],
            budget_outlook=BudgetOutlook(projected_spend_next_month=145000, stated_budget=130000),
            sufficient_history=True,
        ),
        tier=Tier.STANDARD,
        multi_site=True,
        sl_framework_applicable=True,
    )
    result = compose_query(agent_input)
    assert result.used_fallback_query is False
    assert len(result.signals_used) == 4
    assert "cross-site comparison" in result.query_text
    assert "Sri Lanka NGRS framework alignment" in result.query_text


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
