import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Agents.agent2_calc.llm_context import build_explanation_prompt, explain_findings


def test_prompt_includes_key_context_fields():
    context = {
        "site": "Colombo HQ",
        "pattern": {"pattern": "recurring", "message": "3 consecutive periods above baseline"},
        "forecast": {"message": "Forecast for next period: 1200"},
        "budget_check": {"message": "Forecast is 10% over budget"},
    }
    prompt = build_explanation_prompt(context)
    assert "Colombo HQ" in prompt
    assert "3 consecutive periods above baseline" in prompt
    assert "10% over budget" in prompt


def test_explain_findings_falls_back_to_rule_based_without_api_key(monkeypatch):
    monkeypatch.delenv("AGENT2_LLM_API_KEY", raising=False)
    context = {
        "site": "Kandy Plant",
        "pattern": {"pattern": "none", "message": "no anomalies"},
        "forecast": {"forecast_value": 500.0, "confidence": "high"},
        "budget_check": {"status": "on_budget", "message": "on budget"},
    }
    result = explain_findings(context)
    assert result["source"] == "rule_based_fallback"
    assert "Kandy Plant" in result["explanation"]
    assert len(result["explanation"]) > 0


def test_explain_findings_mentions_recurring_pattern():
    context = {
        "site": "Site A",
        "pattern": {"pattern": "recurring", "message": "worsening trend detected"},
        "forecast": {},
        "budget_check": {},
    }
    result = explain_findings(context)
    assert "recurring" in result["explanation"].lower() or "worsening trend detected" in result["explanation"]


def test_explain_findings_mentions_renewable_when_present():
    context = {
        "site": "Site A",
        "pattern": {"pattern": "none", "message": "stable"},
        "forecast": {},
        "budget_check": {},
        "renewable": {
            "sizing": {"system_size_kwp": 7.5, "actual_offset_pct": 0.9},
            "savings_and_payback": {"status": "ok", "payback_years": 4.2, "message": "payback 4.2 years"},
        },
    }
    result = explain_findings(context)
    assert "7.5" in result["explanation"]
    assert "4.2" in result["explanation"]


def test_explain_findings_handles_empty_context_without_crashing():
    result = explain_findings({})
    assert result["source"] == "rule_based_fallback"
    assert len(result["explanation"]) > 0


def test_never_raises_even_if_llm_call_would_fail(monkeypatch):
    import Agents.agent2_calc.llm_context as llm_context

    def broken_call(prompt):
        raise RuntimeError("simulated API outage")

    monkeypatch.setattr(llm_context, "_call_llm_api", broken_call)
    result = llm_context.explain_findings({"site": "Site A"})
    assert result["source"] == "rule_based_fallback"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
