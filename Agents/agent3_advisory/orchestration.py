"""
orchestration.py -- Agent 3's tier-gated entry point.

agent3_recommend() is the single function everything else (the FastAPI
endpoint, later) calls. It decides whether Agent 3 runs at all based on
tier, builds the Standard action plan, and -- for Premium -- adds the
sequential solarpunk/vendor/audit steps on top.
"""

from schemas import (
    Agent3Input,
    Agent3Output,
    Tier,
)
from query_composition import compose_query
from generation import generate_standard_plan


def agent3_recommend(agent_input: Agent3Input) -> Agent3Output | None:
    """
    Main entry point. Returns None for free_trial (Agent 3 doesn't run at
    all), a Standard Agent3Output for standard tier, and a Premium
    Agent3Output (with solarpunk_plan/vendor_matching/audit_trail filled
    in) for premium tier.
    """
    if agent_input.tier == Tier.FREE_TRIAL:
        return None

    composed = compose_query(agent_input)
    action_plan = generate_standard_plan(
        signals=composed.signals_used,
        fallback_query=composed.query_text,
    )

    output = Agent3Output(
        tier=agent_input.tier,
        action_plan=action_plan,
        sl_framework_notes=[],
        used_fallback_query=composed.used_fallback_query,
    )

    if agent_input.tier != Tier.PREMIUM:
        return output

    if agent_input.proposal:
        output.solarpunk_plan = generate_solarpunk_plan(agent_input)

    output.vendor_matching = match_vendors(output.action_plan)
    output.audit_trail = export_audit_trail(agent_input)

    return output


def generate_solarpunk_plan(agent_input: Agent3Input):
    print("STUB: generate_solarpunk_plan not yet implemented")
    return None


def match_vendors(action_plan):
    print("STUB: match_vendors not yet implemented")
    return None


def export_audit_trail(agent_input: Agent3Input):
    print("STUB: export_audit_trail not yet implemented")
    return None


def _build_fake_diagnostics():
    from schemas import (
        Agent2Diagnostics,
        Footprint,
        CompanyTotal,
        SiteReport,
        Trend,
        HistoryCheck,
        TrendAnomaly,
        TrendPattern,
        TrendForecast,
        BudgetCheck,
        Renewable,
        RenewableSizingDetail,
        SavingsAndPayback,
    )

    return Agent2Diagnostics(
        file_id=101,
        resource_type="electricity",
        footprint=Footprint(
            company_total=CompanyTotal(
                total_kg=18500,
                scope1_kg=4500,
                scope2_kg=14000,
                excluded_from_total_kg=0,
            ),
            failed_records=[],
        ),
        suspicious_value_flags=[],
        site_reports=[
            SiteReport(
                site="Colombo South",
                resource_type="electricity",
                trend=Trend(
                    history_check=HistoryCheck(sufficient=True),
                    anomalies=[
                        TrendAnomaly(
                            period="2026-08",
                            trigger="pct_deviation",
                            direction="above",
                            value=14200,
                            baseline_mean=10500,
                            pct_deviation=0.35,
                            flagged=True,
                        )
                    ],
                    pattern=TrendPattern(
                        pattern="rising",
                        message="Consumption trending upward over the last 3 months",
                    ),
                    forecast=TrendForecast(
                        method="linear",
                        forecast_value=14800,
                        confidence="medium",
                    ),
                    budget_check=BudgetCheck(
                        status="over_budget",
                        message="Projected spend exceeds stated monthly budget",
                    ),
                ),
                renewable=Renewable(
                    sizing=RenewableSizingDetail(
                        system_size_kwp=25.0,
                        actual_offset_pct=0.62,
                    ),
                    savings_and_payback=SavingsAndPayback(
                        status="ok",
                        payback_years=4.2,
                    ),
                ),
                benchmark_comparison=None,
                explanation="Electricity use at Colombo South has risen steadily, driven mainly by extended HVAC runtime.",
            )
        ],
        audit_fingerprint="fp_test_001",
    )


def _run_tests():
    fake_diagnostics = _build_fake_diagnostics()

    print("=== Testing tier: free_trial ===")
    free_input = Agent3Input(diagnostics=fake_diagnostics, tier=Tier.FREE_TRIAL)
    result = agent3_recommend(free_input)
    print(f"Result: {result}\n")

    print("=== Testing tier: standard ===")
    standard_input = Agent3Input(diagnostics=fake_diagnostics, tier=Tier.STANDARD)
    result = agent3_recommend(standard_input)
    print(result.model_dump_json(indent=2))

    print("\n=== Testing tier: premium ===")
    premium_input = Agent3Input(diagnostics=fake_diagnostics, tier=Tier.PREMIUM)
    result = agent3_recommend(premium_input)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    _run_tests()