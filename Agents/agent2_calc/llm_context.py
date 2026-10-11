"""
Agents/agent2_calc/llm_context.py
====================================
Person 4 LLM component for Agent 2: turns the structured, deterministic
output of Persons 1-3 into a plain-English explanation a non-technical
reader can act on.

Follows the same swappable-stub pattern as Agent 1's llm_fallback.py
(documented in docs/api_contract.md): `_call_llm_api()` is the ONE
function to replace with a real API call (Anthropic/OpenAI/whatever the
project settles on) — everything around it (prompt construction, the
fallback path, the output shape) stays the same either way.

Unlike Agent 1's fallback tier (which must return "unknown" honestly
when it can't classify), this module has a deterministic RULE-BASED
fallback that composes real sentences from the structured data whenever
no LLM is configured — so the /analyze endpoint always returns a
coherent narrative, not a placeholder, even with zero API keys set.
The output always labels which path produced it (`"source":
"llm" | "rule_based_fallback"`), so no one mistakes a templated
sentence for a model-generated one.
"""

from __future__ import annotations

import os
from typing import Optional


def build_explanation_prompt(analysis_context: dict) -> str:
    """
    Builds the prompt text for the real LLM call. Kept as its own
    function (not inlined) so it can be unit-tested and iterated on
    independently of which LLM provider ends up wired in.
    """
    site = analysis_context.get("site", "this site")
    pattern = analysis_context.get("pattern") or {}
    forecast = analysis_context.get("forecast") or {}
    budget_check = analysis_context.get("budget_check") or {}
    renewable = analysis_context.get("renewable")
    benchmark_comparison = analysis_context.get("benchmark_comparison")

    lines = [
        "You are writing a short, plain-English paragraph for a sustainability report aimed "
        "at a non-technical business owner. Do not invent numbers not given below. "
        "Be concrete and specific, but keep it to 3-5 sentences.",
        "",
        f"Site: {site}",
        f"Anomaly pattern: {pattern.get('message', 'no anomaly data available')}",
        f"Forecast: {forecast.get('message', 'no forecast available')}",
        f"Budget status: {budget_check.get('message', 'not evaluated')}",
    ]
    if renewable:
        sp = renewable.get("savings_and_payback", {})
        lines.append(f"Solar sizing: {renewable.get('sizing', {})}, payback: {sp.get('message', 'not evaluated')}")
    if benchmark_comparison:
        lines.append(f"Industry benchmark comparison: {benchmark_comparison.get('comparison', {}).get('message', 'not evaluated')}")

    return "\n".join(lines)


def _call_llm_api(prompt: str) -> Optional[str]:
    """
    REPLACE THIS FUNCTION with a real LLM call once the project settles
    on a provider. Contract to satisfy:
      - Input: the prompt string from build_explanation_prompt().
      - Output: a plain-English paragraph (str), or None if the call
        fails/isn't configured — never raise, the caller falls back
        to the rule-based path on None.

    Currently a stub: returns None unless an API key env var is set,
    in which case it still returns None with a clear TODO — wiring the
    actual HTTP call is a one-function change when you're ready.
    """
    api_key = os.getenv("AGENT2_LLM_API_KEY")
    if not api_key:
        return None
    # TODO: real call goes here, e.g.:
    #   response = anthropic_client.messages.create(model=..., messages=[{"role": "user", "content": prompt}])
    #   return response.content[0].text
    return None


def _rule_based_explanation(analysis_context: dict) -> str:
    """
    Deterministic fallback — composes a real, readable paragraph from
    the structured data without any model call. This is what actually
    runs in grading/dev environments with no LLM API key configured.
    """
    site = analysis_context.get("site", "This site")
    pattern = analysis_context.get("pattern") or {}
    forecast = analysis_context.get("forecast") or {}
    budget_check = analysis_context.get("budget_check") or {}
    renewable = analysis_context.get("renewable")
    benchmark_comparison = analysis_context.get("benchmark_comparison")

    sentences = []

    pattern_type = pattern.get("pattern")
    if pattern_type == "recurring":
        sentences.append(f"{site} shows a recurring anomaly pattern: {pattern.get('message', '')}")
    elif pattern_type == "one_time":
        sentences.append(f"{site} had at least one unusual period, but it appears to be a one-off rather than a trend: {pattern.get('message', '')}")
    elif pattern_type == "none":
        sentences.append(f"{site}'s consumption has stayed within normal bounds over the periods analysed.")

    if forecast.get("forecast_value") is not None:
        sentences.append(
            f"Based on recent trends, the next period is projected at approximately "
            f"{forecast['forecast_value']:.1f} (confidence: {forecast.get('confidence', 'unknown')})."
        )

    budget_status = budget_check.get("status")
    if budget_status == "over_budget":
        sentences.append(f"This projection is over the stated budget: {budget_check.get('message', '')}")
    elif budget_status == "under_budget":
        sentences.append(f"This projection is comfortably under the stated budget: {budget_check.get('message', '')}")

    if renewable and renewable.get("savings_and_payback", {}).get("status") == "ok":
        sp = renewable["savings_and_payback"]
        sizing = renewable.get("sizing", {})
        sentences.append(
            f"A {sizing.get('system_size_kwp', '?')} kWp solar system could offset "
            f"{sizing.get('actual_offset_pct', 0) * 100:.0f}% of consumption here, "
            f"paying back in an estimated {sp.get('payback_years', '?')} years."
        )

    if benchmark_comparison and benchmark_comparison.get("comparison", {}).get("status") not in (None, "not_evaluable"):
        sentences.append(benchmark_comparison["comparison"]["message"])

    if not sentences:
        sentences.append(f"Not enough data was available to generate a detailed explanation for {site} yet.")

    return " ".join(sentences)


def explain_findings(analysis_context: dict) -> dict:
    """
    Single entry point Person 4's assembly step calls per site. Tries
    the real LLM first (if configured), falls back to the deterministic
    rule-based path on any failure/absence — the endpoint never breaks
    or blocks on this step either way.
    """
    prompt = build_explanation_prompt(analysis_context)

    llm_output = None
    try:
        llm_output = _call_llm_api(prompt)
    except Exception:
        llm_output = None

    if llm_output:
        return {"source": "llm", "explanation": llm_output, "prompt_used": prompt}

    return {
        "source": "rule_based_fallback",
        "explanation": _rule_based_explanation(analysis_context),
        "prompt_used": prompt,
    }
