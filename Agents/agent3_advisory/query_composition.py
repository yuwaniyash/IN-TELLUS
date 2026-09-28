"""
query_composition.py -- Agent 3, Step 2 (NLP): Composed query building.

Built against Agent 2's REAL output shape (assemble.py / trends.py /
renewable.py): signals come from per-site trend.anomalies (flagged only),
trend.budget_check, renewable/benchmark availability, etc.

Rule: if ANY real signal is present -- even one -- it is used. The generic
fallback query only fires when there are truly zero signals across every
site. This keeps used_fallback_query unambiguous: True means nothing at
all was available, not "only a little."
"""

from dataclasses import dataclass, field
from schemas import Agent3Input, SiteReport


@dataclass
class ComposedQuery:
    query_text: str
    signals_used: list[str] = field(default_factory=list)
    used_fallback_query: bool = False


_LIKELY_CAUSES = {
    "electricity": "likely caused by HVAC or lighting load, inefficient equipment, or operational changes",
    "fuel": "likely caused by generator or vehicle inefficiency, delayed maintenance, or longer operating hours",
    "water": "likely caused by leaks, inefficient fixtures, or operational changes",
}
_DEFAULT_CAUSE = "likely caused by equipment inefficiency or operational changes"


def _anomaly_signals(site_reports: list[SiteReport]) -> list[str]:
    """
    Domain vocabulary matches the resource type, so an electricity anomaly
    no longer pulls in generator-maintenance documents.
    """
    signals = []
    for report in site_reports:
        flagged = [a for a in report.trend.anomalies if a.flagged]
        cause = _LIKELY_CAUSES.get((report.resource_type or "").lower(), _DEFAULT_CAUSE)
        for a in flagged:
            pct = f"{a.pct_deviation * 100:.0f}%" if a.pct_deviation is not None else "an unspecified amount"
            signals.append(
                f"{report.site} {report.resource_type} consumption {a.direction} baseline by {pct} in {a.period}, {cause}"
            )
    return signals

def _budget_signals(agent_input: Agent3Input) -> list[str]:
    signals = []

    if agent_input.proposal and agent_input.proposal.budget:
        signals.append(f"budget-constrained under Rs. {agent_input.proposal.budget:,.0f}")

    for report in agent_input.diagnostics.site_reports:
        bc = report.trend.budget_check
        if bc and bc.status == "over_budget":
            signals.append(f"{report.site} over budget: {bc.message or ''}".strip())

    return signals


def _renewable_signal(site_reports: list[SiteReport]) -> str | None:
    parts = []
    for r in site_reports:
        if r.renewable and r.renewable.sizing:
            sizing = r.renewable.sizing
            offset_pct = f"{sizing.actual_offset_pct * 100:.0f}%"
            part = f"{r.site}: {sizing.system_size_kwp} kWp solar system would offset {offset_pct} of consumption"

            payback = r.renewable.savings_and_payback
            if payback and payback.status == "ok" and payback.payback_years:
                part += f", estimated payback {payback.payback_years:.1f} years"

            parts.append(part)

    if not parts:
        return None
    return "; ".join(parts)


def _benchmark_signal(site_reports: list[SiteReport]) -> str | None:
    for report in site_reports:
        bc = report.benchmark_comparison
        if bc and bc.comparison and bc.comparison.status != "not_evaluable":
            return bc.comparison.message
    return None


def _multi_site_signal(agent_input: Agent3Input) -> str | None:
    if agent_input.multi_site or len(agent_input.diagnostics.site_reports) > 1:
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
    total = agent_input.diagnostics.footprint.company_total.total_kg
    resource = agent_input.diagnostics.resource_type
    return (
        f"general efficiency and sustainability guidance for a facility "
        f"emitting approximately {total} kg CO2e, primarily from {resource}"
    )


def compose_query(agent_input: Agent3Input) -> ComposedQuery:
    site_reports = agent_input.diagnostics.site_reports

    signals = []
    signals.extend(_anomaly_signals(site_reports))
    signals.extend(_budget_signals(agent_input))

    for s in [
        _renewable_signal(site_reports),
        _benchmark_signal(site_reports),
        _multi_site_signal(agent_input),
        _framework_signal(agent_input),
        _user_context_signal(agent_input),
    ]:
        if s:
            signals.append(s)

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