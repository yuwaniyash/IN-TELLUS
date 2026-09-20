# query_composition.py
"""
Agent 3 â€” Step 2 (NLP): Composed query building.

Rule (confirmed): if ANY real signal is present â€” even one â€” it is used.
The generic benchmark fallback only fires when there are truly zero signals
(anomalies, budget, multi-site, SL framework applicability, user context all
absent). This keeps `used_fallback_query` unambiguous: True means nothing at
all was available, not "only a little."
"""

from dataclasses import dataclass, field
from schema import Agent3Input, Anomaly


@dataclass
class ComposedQuery:
    query_text: str
    signals_used: list[str] = field(default_factory=list)
    used_fallback_query: bool = False


def _anomaly_signal(anomalies: list[Anomaly] | None) -> str | None:
    if not anomalies:
        return None
    parts = [f"{a.type} anomaly {a.magnitude} in {a.period}" for a in anomalies]
    return "; ".join(parts)


def _budget_signal(agent_input: Agent3Input) -> str | None:
    # Prefer an explicit project proposal budget if present, else the
    # budget_outlook's stated_budget from Agent 2's diagnostics.
    if agent_input.proposal and agent_input.proposal.budget:
        return f"budget-constrained under Rs. {agent_input.proposal.budget:,.0f}"

    outlook = agent_input.diagnostics.budget_outlook
    if outlook and outlook.stated_budget:
        return f"budget-constrained under Rs. {outlook.stated_budget:,.0f}"

    return None


def _multi_site_signal(agent_input: Agent3Input) -> str | None:
    if agent_input.multi_site:
        return "cross-site comparison"
    return None


def _framework_signal(agent_input: Agent3Input) -> str | None:
    if agent_input.sl_framework_applicable:
        return "Sri Lanka NGRS framework alignment"
    return None


def _user_context_signal(agent_input: Agent3Input) -> str | None:
    if agent_input.user_context and agent_input.user_context.strip():
        return agent_input.user_context.strip()
    return None


def _generic_fallback_query(agent_input: Agent3Input) -> str:
    total = agent_input.diagnostics.footprint.get("total_co2e_kg", "unknown")
    breakdown = agent_input.diagnostics.footprint.get("breakdown_by_resource", {})
    resource_mix = ", ".join(breakdown.keys()) if breakdown else "mixed resources"
    return (
        f"general efficiency and sustainability guidance for a facility "
        f"emitting approximately {total} kg CO2e, primarily from {resource_mix}"
    )


def compose_query(agent_input: Agent3Input) -> ComposedQuery:
    """
    Builds the retrieval query for Agent 3, Step 3 (IR).

    Gathers every available signal and combines them into one query string.
    Falls back to a generic benchmark query only when zero signals exist.
    """
    signal_extractors = [
        _anomaly_signal(agent_input.diagnostics.anomalies),
        _budget_signal(agent_input),
        _multi_site_signal(agent_input),
        _framework_signal(agent_input),
        _user_context_signal(agent_input),
    ]

    signals = [s for s in signal_extractors if s]

    if not signals:
        return ComposedQuery(
            query_text=_generic_fallback_query(agent_input),
            signals_used=[],
            used_fallback_query=True,
        )

    return ComposedQuery(
        query_text="; ".join(signals),
        signals_used=signals,
        used_fallback_query=False,
    )
