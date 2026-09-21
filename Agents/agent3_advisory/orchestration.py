"""
orchestration.py -- Agent 3's tier-gated entry point.

agent3_recommend() is the single function everything else (the FastAPI
endpoint) calls. It decides whether Agent 3 runs at all based on tier,
builds the Standard action plan, and -- for Premium -- adds the
sequential solarpunk/vendor/audit steps on top. Every completed run is
logged via audit.py for the audit trail.
"""

from schemas import (
    Agent3Input,
    Agent3Output,
    Tier,
)
from query_composition import compose_query
from generation import generate_standard_plan, generate_category_plan
from audit import (
    log_agent3_run,
    log_solarpunk_plan,
    log_vendor_matches,
    get_audit_trail_for_company,
)


def agent3_recommend(agent_input: Agent3Input) -> Agent3Output | None:
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

    retrieved_source_ids = [item.source.doc_id for item in action_plan]
    site_id = agent_input.diagnostics.site_reports[0].site if agent_input.diagnostics.site_reports else None

    run_id = log_agent3_run(
        company_id=agent_input.company_id,
        tier=agent_input.tier.value,
        diagnostics_snapshot=agent_input.diagnostics.model_dump(),
        composed_query=composed.query_text,
        retrieved_source_ids=retrieved_source_ids,
        generated_output=output.model_dump(),
        site_id=site_id,
    )

    if agent_input.tier != Tier.PREMIUM:
        return output

    if agent_input.proposal:
        output.solarpunk_plan = generate_solarpunk_plan(agent_input, run_id)

    output.vendor_matching = match_vendors(output.action_plan, run_id)
    output.audit_trail = export_audit_trail(agent_input, run_id)

    return output


def generate_solarpunk_plan(agent_input: Agent3Input, run_id: int):
    """
    Builds a Premium-only solarpunk plan from the submitted proposal,
    retrieving only category='solarpunk' KB content. Returns None if the
    retrieval/generation produces nothing usable.
    """
    from schemas import SolarpunkPlan

    proposal = agent_input.proposal
    signals = [f"budget Rs. {proposal.budget:,.0f}"]

    if proposal.goals_text:
        signals.append(proposal.goals_text.strip())
    if proposal.timeline_months:
        signals.append(f"timeline of {proposal.timeline_months} months")

    action_items = generate_category_plan(signals, category="solarpunk")

    if not action_items:
        return None

    plan = SolarpunkPlan(
        projects=[item.action for item in action_items],
        estimated_investment=proposal.budget,
        timeline=f"{proposal.timeline_months} months" if proposal.timeline_months else None,
        sources=[item.source for item in action_items],
    )

    log_solarpunk_plan(
        agent3_run_id=run_id,
        proposal_snapshot=proposal.model_dump(),
        retrieved_source_ids=[item.source.doc_id for item in action_items],
        generated_plan=plan.model_dump(),
    )

    return plan


def match_vendors(action_plan, run_id: int):
    """
    Retrieves category='vendor' KB content relevant to what was actually
    recommended in the action plan, grouping matches by the intervention
    topic they relate to.
    """
    from schemas import VendorMatch

    if not action_plan:
        return None

    signals = [item.action for item in action_plan]
    vendor_items = generate_category_plan(signals, category="vendor")

    if not vendor_items:
        return None

    matches_by_category: dict[str, list[str]] = {}
    for item in vendor_items:
        category_label = item.source.title
        matches_by_category.setdefault(category_label, []).append(item.action)

    matches = [
        VendorMatch(category=category, matches=vals)
        for category, vals in matches_by_category.items()
    ]

    log_vendor_matches(
        agent3_run_id=run_id,
        matched_categories={m.category: m.matches for m in matches},
    )

    return matches


def export_audit_trail(agent_input: Agent3Input, run_id: int):
    """
    Reads back everything logged for this company so far, via audit.py.
    Returns an AuditTrailExport summarizing the run history -- actual
    PDF/JSON file generation is a later addition; for now this returns
    the raw trail as JSON-in-memory (file_path stays None).
    """
    from schemas import AuditTrailExport

    trail = get_audit_trail_for_company(agent_input.company_id)

    return AuditTrailExport(
        company_id=agent_input.company_id,
        run_ids=trail["run_ids"],
        export_format="json",
        file_path=None,
    )


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
    TEST_COMPANY_ID = 1  # replace with a real company_id from your `companies` table

    print("=== Testing tier: free_trial ===")
    free_input = Agent3Input(company_id=TEST_COMPANY_ID, diagnostics=fake_diagnostics, tier=Tier.FREE_TRIAL)
    result = agent3_recommend(free_input)
    print(f"Result: {result}\n")

    print("=== Testing tier: standard ===")
    standard_input = Agent3Input(company_id=TEST_COMPANY_ID, diagnostics=fake_diagnostics, tier=Tier.STANDARD)
    result = agent3_recommend(standard_input)
    print(result.model_dump_json(indent=2))

    print("\n=== Testing tier: premium (no proposal) ===")
    premium_input = Agent3Input(company_id=TEST_COMPANY_ID, diagnostics=fake_diagnostics, tier=Tier.PREMIUM)
    result = agent3_recommend(premium_input)
    print(result.model_dump_json(indent=2))

    print("\n=== Testing tier: premium (with proposal) ===")
    from schemas import ProjectProposal
    premium_with_proposal = Agent3Input(
        company_id=TEST_COMPANY_ID,
        diagnostics=fake_diagnostics,
        tier=Tier.PREMIUM,
        proposal=ProjectProposal(
            budget=500000,
            site_id="Colombo South",
            timeline_months=18,
            goals_text="explore green roof and microgrid options for our main office building",
        ),
    )
    result = agent3_recommend(premium_with_proposal)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    _run_tests()