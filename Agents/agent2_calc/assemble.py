"""
Agents/agent2_calc/assemble.py
=================================
Orchestrates the full Agent 2 pipeline for ONE uploaded file, scoped to
ONE company (via the caller-verified company_id from the JWT).

Pipeline:
  1. Look up the file (company-scoped) -> know its resource_type.
  2. Pull this file's records (Person 1 input) + suspicious-value flags.
  3. Compute emissions (Person 1) -> footprint.
  4. For each site in the file: pull full historical series from the DB
     (not just this file), run trend analysis (Person 2), and for
     electricity sites, size a renewable system (Person 3) + compare to
     an industry benchmark (Person 4/IR).
  5. Generate a plain-English explanation per site (Person 4/LLM).
  6. Return one assembled document — this IS the Agent 2 -> Agent 3
     contract payload.

Never raises on a single site/record failing — partial results with
explicit errors/warnings are always preferable to a hard 500, since one
bad site shouldn't block the whole company's report.
"""

from __future__ import annotations

from typing import Optional

from Database.get_records import (
    get_file_metadata,
    get_records_for_file,
    get_historical_monthly_series,
)
from Security_Layer.audit_log import flag_suspicious_values, log_calculation_run

from .emissions import compute_batch, aggregate_footprint
from .trends import analyze_trend
from .renewable import size_renewable_system
from .benchmarks import compare_to_benchmark
from .nlp_context import process_free_text
from .llm_context import explain_findings


def _estimate_annual_consumption(series: list) -> dict:
    """
    Turns a monthly historical series into an annual figure for
    renewable sizing. Uses the trailing 12 months if available;
    otherwise extrapolates from however many months exist, flagged as
    lower confidence the fewer months there are.
    """
    if not series:
        return {"annual_kwh": None, "confidence": "none", "months_used": 0}

    ordered = sorted(series, key=lambda p: p["period"])
    trailing = ordered[-12:]
    months_used = len(trailing)
    total = sum(p["value"] for p in trailing)

    if months_used >= 12:
        annual = total
        confidence = "high"
    else:
        annual = (total / months_used) * 12
        confidence = "high" if months_used >= 6 else ("medium" if months_used >= 3 else "low")

    return {"annual_kwh": annual, "confidence": confidence, "months_used": months_used}


def _estimate_effective_tariff(company_id: int, site: str) -> Optional[float]:
    """
    Derives the company's own effective LKR/kWh rate from its actual
    billing history (total cost / total consumption over the same
    periods), rather than assuming a national tariff category. Returns
    None if there isn't enough cost data to compute this — the
    renewable module handles that gracefully (sizing still works,
    savings/payback reported as not_evaluable).
    """
    consumption_series = get_historical_monthly_series(company_id, site, "electricity", value_field="consumption")
    cost_series = get_historical_monthly_series(company_id, site, "electricity", value_field="cost")

    cost_by_period = {p["period"]: p["value"] for p in cost_series if p["value"] is not None}
    total_cost = 0.0
    total_kwh = 0.0
    for p in consumption_series:
        if p["period"] in cost_by_period and p["value"]:
            total_cost += cost_by_period[p["period"]]
            total_kwh += p["value"]

    if total_kwh <= 0:
        return None
    return total_cost / total_kwh


def run_full_analysis(
    file_id: int,
    company_id: int,
    monthly_budget_lkr: Optional[float] = None,
    effective_tariff_lkr_per_kwh: Optional[float] = None,
    region: str = "mid_country",
    sector: Optional[str] = None,
    floor_area_m2: Optional[float] = None,
) -> dict:
    file_meta = get_file_metadata(file_id, company_id)
    if file_meta is None:
        return {"errors": [f"file_id {file_id} not found for this company"], "result": None}

    resource_type = file_meta["resource_type"]
    records = get_records_for_file(file_id, company_id, resource_type)
    if not records:
        return {"errors": [f"No consumption records found for file_id {file_id}"], "result": None}

    suspicious_flags = flag_suspicious_values(records)

    emission_results = compute_batch(records)
    footprint = aggregate_footprint(emission_results)

    sites = sorted({r["site"] for r in records if r.get("site")})
    site_reports = []

    for site in sites:
        site_result = {"site": site, "resource_type": resource_type}

        history = get_historical_monthly_series(company_id, site, resource_type, value_field="consumption")
        trend = analyze_trend(history, metric_name=f"{resource_type}_consumption_kwh", budget=monthly_budget_lkr)
        site_result["trend"] = trend

        renewable_result = None
        benchmark_result = None

        if resource_type == "electricity":
            annual_estimate = _estimate_annual_consumption(history)
            if annual_estimate["annual_kwh"] is not None:
                tariff = effective_tariff_lkr_per_kwh
                if tariff is None:
                    tariff = _estimate_effective_tariff(company_id, site)

                renewable_result = size_renewable_system(
                    annual_consumption_kwh=annual_estimate["annual_kwh"],
                    effective_tariff_lkr_per_kwh=tariff,
                    region=region,
                )
                renewable_result["annual_consumption_estimate"] = annual_estimate

            if sector:
                benchmark_result = compare_to_benchmark(
                    annual_kwh=annual_estimate["annual_kwh"] or 0,
                    floor_area_m2=floor_area_m2,
                    sector=sector,
                )

        site_result["renewable"] = renewable_result
        site_result["benchmark_comparison"] = benchmark_result

        # NLP: no live free-text source yet (see nlp_context.py docstring) —
        # wired in as a no-op today, ready the moment one exists.
        site_result["nlp_context"] = process_free_text(None)

        explanation_context = {
            "site": site,
            "pattern": trend.get("pattern"),
            "forecast": trend.get("forecast"),
            "budget_check": trend.get("budget_check"),
            "renewable": renewable_result,
            "benchmark_comparison": benchmark_result,
        }
        site_result["explanation"] = explain_findings(explanation_context)

        site_reports.append(site_result)

    result = {
        "file_id": file_id,
        "resource_type": resource_type,
        "footprint": footprint,
        "suspicious_value_flags": suspicious_flags,
        "site_reports": site_reports,
    }

    output_summary = {
        "resource_type": resource_type,
        "sites_analyzed": len(site_reports),
        "company_total_co2e_kg": footprint["company_total"]["total_kg"],
        "failed_records": len(footprint["failed_records"]),
    }
    fingerprint = log_calculation_run(
        endpoint="/agent2/analyze",
        company_id=company_id,
        input_ref={"file_id": file_id},
        output_summary=output_summary,
        warnings=suspicious_flags,
        errors=footprint["failed_records"],
    )
    result["audit_fingerprint"] = fingerprint

    return {"errors": [], "result": result}
