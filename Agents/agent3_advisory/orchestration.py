"""
orchestration.py — Agent 3's tier-gated entry point.

agent3_recommend() is the single function everything else (the FastAPI
endpoint, later) calls. It decides whether Agent 3 runs at all based on
tier, builds the Standard action plan, and — for Premium — adds the
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
    action_plan = generate_standard_plan(composed.query_text)

    output = Agent3Output(
        tier=agent_input.tier,
        action_plan=action_plan,
        sl_framework_notes=[],  # TODO: populate once SL framework retrieval is built
        used_fallback_query=composed.used_fallback_query,
    )

    if agent_input.tier != Tier.PREMIUM:
        return output

    # --- Premium-only, sequential ---
    if agent_input.proposal:
        output.solarpunk_plan = generate_solarpunk_plan(agent_input)

    output.vendor_matching = match_vendors(output.action_plan)
    output.audit_trail = export_audit_trail(agent_input)

    return output


def generate_solarpunk_plan(agent_input: Agent3Input):
    """
    Stub for now: same RAG pattern as generate_standard_plan, but built
    against the proposal + category='solarpunk' content. Not built yet --
    wire this up once we're ready to move past Standard tier testing.
    """
    print("STUB: generate_solarpunk_plan not yet implemented")
    return None


def match_vendors(action_plan):
    """
    Stub for now: retrieves category='vendor' content matched against the
    action plan's intervention types. Not built yet.
    """
    print("STUB: match_vendors not yet implemented")
    return None


def export_audit_trail(agent_input: Agent3Input):
    """
    Stub for now: reads from audit tables (agent3_runs, etc.) once
    audit.py exists and orchestration.py is actually logging runs.
    """
    print("STUB: export_audit_trail not yet implemented")
    return None


if __name__ == "__main__":
    # Hand-built fake input, matching schema.py's shape. Replace with a
    # real Agent 2 output once that's finalized -- the shape is what
    # matters here, not the specific numbers.
    from schemas import Agent2Diagnostics, Anomaly

    fake_diagnostics = Agent2Diagnostics(
        footprint={
            "total_co2e_kg": 18500,
            "breakdown_by_resource": {"electricity": 14000, "diesel": 4500},
        },
        anomalies=[
            Anomaly(
                type="electricity_spike",
                magnitude="35%",
                period="last 2 months",
                explanation="Unusual increase in HVAC runtime detected",
            )
        ],
        renewable_sizing=None,
        budget_outlook=None,
        sufficient_history=True,
    )

    print("=== Testing tier: free_trial ===")
    free_input = Agent3Input(diagnostics=fake_diagnostics, tier=Tier.FREE_TRIAL)
    result = agent3_recommend(free_input)
    print(f"Result: {result}\n")  # should print None

    print("=== Testing tier: standard ===")
    standard_input = Agent3Input(diagnostics=fake_diagnostics, tier=Tier.STANDARD)
    result = agent3_recommend(standard_input)
    print(result.model_dump_json(indent=2))

    print("\n=== Testing tier: premium ===")
    premium_input = Agent3Input(diagnostics=fake_diagnostics, tier=Tier.PREMIUM)
    result = agent3_recommend(premium_input)
    print(result.model_dump_json(indent=2))