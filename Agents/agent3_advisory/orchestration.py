"""
orchestration.py -- Agent 3's tier-gated entry points.

agent3_recommend() is the bill-based flow: it builds the Standard action
plan and, for Premium, adds the solarpunk/vendor/audit steps on top.

agent3_solarpunk_only() is the proposal-only Premium flow: it needs NO
utility bill. It builds the solarpunk plan from the proposal alone, then
matches vendors to the plan's projects and returns the audit trail.

Every completed run is logged via audit.py for the audit trail.
"""

from schemas import (
    Agent3Input,
    Agent3Output,
    Tier,
    ProjectProposal,
    SolarpunkPlan,
    SolarpunkOutput,
    VendorMatch,
    AuditTrailExport,
)
from query_composition import compose_query
from generation import generate_standard_plan, generate_category_plan
from audit import (
    log_agent3_run,
    log_solarpunk_plan,
    log_vendor_matches,
    get_audit_trail_for_company,
)


# ---------------------------------------------------------------------------
# Bill-based flow (Standard and Premium)
# ---------------------------------------------------------------------------

def agent3_recommend(agent_input: Agent3Input) -> Agent3Output | None:
    if agent_input.tier == Tier.FREE_TRIAL:
        return None

    composed = compose_query(agent_input)

    k_per_signal = 4 if len(composed.signals_used) <= 2 else 2

    action_plan = generate_standard_plan(
        signals=composed.signals_used,
        fallback_query=composed.query_text,
        k_per_signal=k_per_signal,
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


# ---------------------------------------------------------------------------
# Proposal-only flow (Premium, no bill needed)
# ---------------------------------------------------------------------------

def agent3_solarpunk_only(company_id: int, proposal: ProjectProposal) -> SolarpunkOutput | None:
    """
    Builds a solarpunk plan from the proposal alone. Returns None if the
    knowledge base produced nothing usable for this proposal.

    Logged as a normal agent3_runs row with an empty diagnostics snapshot,
    so solarpunk_plans / vendor_matches can link to it as usual.
    """
    plan = _build_solarpunk_plan(proposal)
    if plan is None:
        return None

    run_id = log_agent3_run(
        company_id=company_id,
        tier=Tier.PREMIUM.value,
        diagnostics_snapshot={},
        composed_query="; ".join(_proposal_signals(proposal)),
        retrieved_source_ids=[s.doc_id for s in plan.sources],
        generated_output=plan.model_dump(),
        site_id=None,
    )

    log_solarpunk_plan(
        agent3_run_id=run_id,
        proposal_snapshot=proposal.model_dump(),
        retrieved_source_ids=[s.doc_id for s in plan.sources],
        generated_plan=plan.model_dump(),
    )

    # No action plan exists here, so vendors are matched to the solarpunk
    # projects instead (green roof -> green roof contractors, etc.).
    vendors = _match_vendors_from_signals(plan.projects, run_id)
    audit_trail = _audit_trail_for(company_id)

    return SolarpunkOutput(
        solarpunk_plan=plan,
        vendor_matching=vendors,
        audit_trail=audit_trail,
    )


# ---------------------------------------------------------------------------
# Shared steps
# ---------------------------------------------------------------------------

def _proposal_signals(proposal: ProjectProposal) -> list[str]:
    signals = [f"budget Rs. {proposal.budget:,.0f}"]

    if proposal.goals_text:
        signals.append(proposal.goals_text.strip())
    if proposal.timeline_months:
        signals.append(f"timeline of {proposal.timeline_months} months")

    return signals


def _build_solarpunk_plan(proposal: ProjectProposal) -> SolarpunkPlan | None:
    """
    Retrieves only category='solarpunk' KB content and generates the plan.
    Pure generation: no logging. Returns None if nothing usable came back.
    """
    action_items = generate_category_plan(_proposal_signals(proposal), category="solarpunk")

    if not action_items:
        return None

    return SolarpunkPlan(
        projects=[item.action for item in action_items],
        estimated_investment=proposal.budget,
        timeline=f"{proposal.timeline_months} months" if proposal.timeline_months else None,
        sources=[item.source for item in action_items],
    )


def generate_solarpunk_plan(agent_input: Agent3Input, run_id: int):
    """
    Bill-based flow: builds the plan from the submitted proposal and logs it
    against the run that was just recorded.
    """
    plan = _build_solarpunk_plan(agent_input.proposal)
    if plan is None:
        return None

    log_solarpunk_plan(
        agent3_run_id=run_id,
        proposal_snapshot=agent_input.proposal.model_dump(),
        retrieved_source_ids=[s.doc_id for s in plan.sources],
        generated_plan=plan.model_dump(),
    )

    return plan


def _match_vendors_from_signals(signals: list[str], run_id: int):
    """
    Retrieves category='vendor' KB content relevant to the given signals,
    grouping matches by the provider category they belong to.
    """
    if not signals:
        return None

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


def match_vendors(action_plan, run_id: int):
    """Bill-based flow: match vendors to what the action plan recommended."""
    if not action_plan:
        return None

    return _match_vendors_from_signals([item.action for item in action_plan], run_id)


def _audit_trail_for(company_id: int) -> AuditTrailExport:
    """
    Reads back everything logged for this company so far, via audit.py.
    Actual PDF/JSON file generation is a later addition; for now this
    returns the run history in memory (file_path stays None).
    """
    trail = get_audit_trail_for_company(company_id)

    return AuditTrailExport(
        company_id=company_id,
        run_ids=trail["run_ids"],
        export_format="json",
        file_path=None,
    )


def export_audit_trail(agent_input: Agent3Input, run_id: int):
    return _audit_trail_for(agent_input.company_id)


# ---------------------------------------------------------------------------
# Manual tests
# ---------------------------------------------------------------------------

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
            )
        ],
        audit_fingerprint="fp_test_001",
    )


def _run_solarpunk_only_test():
    TEST_COMPANY_ID = 1  # replace with a real company_id from your `companies` table

    print("=== Testing: premium, proposal only (no bill) ===")
    result = agent3_solarpunk_only(
        TEST_COMPANY_ID,
        ProjectProposal(
            budget=4500000,
            site_id=None,
            timeline_months=18,
            goals_text="cut electricity use, add on-site renewable generation, and explore a green roof and a solar microgrid",
        ),
    )
    if result is None:
        print("Result: None (no solarpunk content matched)")
    else:
        print(result.model_dump_json(indent=2))


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

    print()
    _run_solarpunk_only_test()


if __name__ == "__main__":
    import sys

    # python orchestration.py solarpunk   -> runs only the proposal-only test (fast)
    # python orchestration.py             -> runs every test
    if "solarpunk" in sys.argv[1:]:
        _run_solarpunk_only_test()
    else:
        _run_tests()
