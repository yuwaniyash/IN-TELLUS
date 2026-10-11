import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import Agents.agent2_calc.assemble as assemble_module

TOKEN = "test-token"


def _six_month_series(site, values):
    periods = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
    return [{"period": p, "value": v, "site": site} for p, v in zip(periods, values)]


def test_file_not_found_returns_error_not_exception():
    # Agent 1 answers 404 -> fetch_file_records_from_agent1 returns None
    with patch.object(assemble_module, "fetch_file_records_from_agent1", return_value=None):
        outcome = assemble_module.run_full_analysis(file_id=999, company_id=1, auth_token=TOKEN)
    assert outcome["errors"] != []
    assert outcome["result"] is None


def test_agent1_unreachable_returns_error_not_exception():
    # Agent-to-agent link is down -> clear error, no crash
    with patch.object(assemble_module, "fetch_file_records_from_agent1",
                      side_effect=RuntimeError("Could not reach Agent 1")):
        outcome = assemble_module.run_full_analysis(file_id=1, company_id=1, auth_token=TOKEN)
    assert outcome["errors"] != []
    assert outcome["result"] is None


def test_empty_records_returns_error_not_exception():
    payload = {"resource_type": "electricity", "records": []}
    with patch.object(assemble_module, "fetch_file_records_from_agent1", return_value=payload):
        outcome = assemble_module.run_full_analysis(file_id=1, company_id=1, auth_token=TOKEN)
    assert outcome["errors"] != []
    assert outcome["result"] is None


def test_full_pipeline_wires_together_for_electricity():
    records = [
        {"resource_type": "electricity", "site": "Colombo HQ", "consumption": 1200.0, "unit": "kWh", "billing_period": "2026-06"},
    ]
    payload = {"resource_type": "electricity", "records": records}
    consumption_series = _six_month_series("Colombo HQ", [1000, 1050, 1100, 1150, 1180, 1200])
    cost_series = _six_month_series("Colombo HQ", [45000, 47000, 49000, 51000, 52500, 54000])

    def fake_historical(company_id, site, resource_type, value_field="consumption"):
        return cost_series if value_field == "cost" else consumption_series

    with patch.object(assemble_module, "fetch_file_records_from_agent1", return_value=payload) as fetch, \
         patch.object(assemble_module, "get_historical_monthly_series", side_effect=fake_historical), \
         patch.object(assemble_module, "flag_suspicious_values", return_value=[]), \
         patch.object(assemble_module, "log_calculation_run", return_value="fingerprint123"):

        outcome = assemble_module.run_full_analysis(
            file_id=1, company_id=1, auth_token=TOKEN,
            monthly_budget_lkr=60000.0, region="lowland_coastal",
        )

    # the caller's token is forwarded to Agent 1 (agent-to-agent communication)
    fetch.assert_called_once_with(1, TOKEN)

    assert outcome["errors"] == []
    result = outcome["result"]
    assert result["resource_type"] == "electricity"
    assert result["footprint"]["company_total"]["scope2_kg"] > 0
    assert len(result["site_reports"]) == 1

    site_report = result["site_reports"][0]
    assert site_report["site"] == "Colombo HQ"
    assert site_report["trend"]["history_check"]["sufficient"] is True
    assert site_report["renewable"] is not None
    assert site_report["renewable"]["sizing"]["system_size_kwp"] > 0
    assert site_report["renewable"]["savings_and_payback"]["status"] in ("ok", "no_savings")
    assert "explanation" in site_report
    assert site_report["explanation"]["source"] in ("llm", "rule_based_fallback")
    assert result["audit_fingerprint"] == "fingerprint123"


def test_fuel_records_skip_renewable_and_benchmark():
    records = [
        {"resource_type": "fuel", "fuel_type": "diesel", "site": "Kandy Plant", "consumption": 100.0, "unit": "L", "billing_period": "2026-06"},
    ]
    payload = {"resource_type": "fuel", "records": records}
    fuel_series = _six_month_series("Kandy Plant", [80, 85, 90, 95, 98, 100])

    with patch.object(assemble_module, "fetch_file_records_from_agent1", return_value=payload), \
         patch.object(assemble_module, "get_historical_monthly_series", return_value=fuel_series), \
         patch.object(assemble_module, "flag_suspicious_values", return_value=[]), \
         patch.object(assemble_module, "log_calculation_run", return_value="fp"):

        outcome = assemble_module.run_full_analysis(file_id=2, company_id=1, auth_token=TOKEN, sector="office")

    assert outcome["errors"] == []
    site_report = outcome["result"]["site_reports"][0]
    assert site_report["renewable"] is None
    assert site_report["benchmark_comparison"] is None
    assert site_report["trend"]["history_check"]["sufficient"] is True


def test_suspicious_flags_propagate_into_result():
    records = [{"resource_type": "electricity", "site": "A", "consumption": 10_000_000.0, "unit": "kWh", "billing_period": "2026-06"}]
    payload = {"resource_type": "electricity", "records": records}

    with patch.object(assemble_module, "fetch_file_records_from_agent1", return_value=payload), \
         patch.object(assemble_module, "get_historical_monthly_series", return_value=[]), \
         patch.object(assemble_module, "flag_suspicious_values", return_value=["Unusually high electricity consumption"]), \
         patch.object(assemble_module, "log_calculation_run", return_value="fp"):

        outcome = assemble_module.run_full_analysis(file_id=3, company_id=1, auth_token=TOKEN)

    assert outcome["result"]["suspicious_value_flags"] == ["Unusually high electricity consumption"]


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))