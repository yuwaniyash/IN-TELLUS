"""
Agents/agent2_calc/emissions.py
================================
Person 1 — Core Emissions Engine (Agent 2 / Analysis)

Turns validated ExtractionRecord-shaped dicts (Agent 1's output) into
GHG Protocol Scope 1/2/3-tagged CO2e figures, using the published
emission factor table in data/emission_factors/emission_factors.json.

Design goals (per the project's "no black box" Responsible AI stance):
  - Pure, deterministic calculation. No LLM/NLP here — that's Person 4's
    context-enrichment layer downstream. Same input -> same output, always.
  - Never silently drop or guess. Unresolvable records come back with an
    explicit error, not a skipped/zeroed value.
  - Every computed figure carries which factor + source was used, so the
    report is auditable end-to-end.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

_FACTORS_PATH = Path(__file__).resolve().parents[2] / "data" / "emission_factors" / "emission_factors.json"

_VALID_RESOURCE_TYPES = {"electricity", "water", "fuel"}


@dataclass
class EmissionResult:
    """One computed emissions line, one-to-one with an input record."""
    resource_type: Optional[str]
    scope: Optional[int]              # 1, 2, 3, or None (excluded, e.g. water)
    co2e_kg: Optional[float]          # None if calculation failed
    factor_used: Optional[float]
    factor_unit: Optional[str]
    factor_source: Optional[str]
    site: Optional[str]
    billing_period: Optional[str]
    included_in_total: bool
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def load_emission_factors(path: Path = _FACTORS_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_fuel_factor(fuel_type, unit, factors: dict):
    """
    Returns (factor_value, factor_unit_label, source) for a fuel record,
    matching on fuel_type (case-insensitive, alias-aware) and the record's
    declared unit (L, kg, or m3). Returns (None, None, None) if it can't
    resolve unambiguously.
    """
    if not fuel_type:
        return None, None, None

    key = fuel_type.strip().lower().replace(" ", "_")
    fuel_table = factors.get("fuel", {})

    match = fuel_table.get(key)
    if match is None:
        for fkey, fentry in fuel_table.items():
            if key in [a.lower() for a in fentry.get("aliases", [])]:
                match = fentry
                break

    if match is None:
        return None, None, None

    unit_norm = (unit or "").strip().lower()
    if unit_norm in ("l", "litre", "litres", "liter", "liters") and "factor_kg_co2e_per_litre" in match:
        return match["factor_kg_co2e_per_litre"], "kg_co2e_per_litre", match.get("source")
    if unit_norm == "kg" and "factor_kg_co2e_per_kg" in match:
        return match["factor_kg_co2e_per_kg"], "kg_co2e_per_kg", match.get("source")
    if unit_norm in ("m3", "m^3", "cubic_metres") and "factor_kg_co2e_per_m3" in match:
        return match["factor_kg_co2e_per_m3"], "kg_co2e_per_m3", match.get("source")

    # Unit missing/unrecognised: fall back only if the fuel has exactly one
    # factor variant defined (unambiguous), otherwise refuse to guess.
    available = [
        (v, u) for v, u in [
            (match.get("factor_kg_co2e_per_litre"), "kg_co2e_per_litre"),
            (match.get("factor_kg_co2e_per_kg"), "kg_co2e_per_kg"),
            (match.get("factor_kg_co2e_per_m3"), "kg_co2e_per_m3"),
        ] if v is not None
    ]
    if len(available) == 1:
        return available[0][0], available[0][1], match.get("source")

    return None, None, None


def compute_emissions(record: dict, factors: dict = None) -> EmissionResult:
    """
    Computes one EmissionResult from one ExtractionRecord-shaped dict.
    Never raises on bad data — returns an EmissionResult with `errors`
    populated instead, so one bad record can't take down a batch.
    """
    factors = factors if factors is not None else load_emission_factors()

    resource_type = (record.get("resource_type") or "").strip().lower()
    site = record.get("site")
    billing_period = record.get("billing_period")
    consumption = record.get("consumption")
    unit = record.get("unit")

    errors = []
    warnings = []

    if resource_type not in _VALID_RESOURCE_TYPES:
        errors.append(f"Unknown or missing resource_type: {record.get('resource_type')!r}")
        return EmissionResult(
            resource_type=record.get("resource_type"), scope=None, co2e_kg=None,
            factor_used=None, factor_unit=None, factor_source=None,
            site=site, billing_period=billing_period, included_in_total=False,
            errors=errors, warnings=warnings,
        )

    if consumption is None:
        errors.append("consumption is missing")
    elif not isinstance(consumption, (int, float)):
        errors.append(f"consumption is not numeric: {consumption!r}")
    elif consumption < 0:
        errors.append(f"consumption is negative: {consumption}")

    if errors:
        return EmissionResult(
            resource_type=resource_type, scope=None, co2e_kg=None,
            factor_used=None, factor_unit=None, factor_source=None,
            site=site, billing_period=billing_period, included_in_total=False,
            errors=errors, warnings=warnings,
        )

    # ---- Electricity: Scope 2 ----
    if resource_type == "electricity":
        grid = factors["electricity"]["grid_default"]
        factor = grid["factor_kg_co2_per_kwh"]
        unit_norm = (unit or "").strip().lower()
        if unit_norm != "kwh":
            warnings.append(
                f"Expected unit 'kWh' for electricity, got {unit!r}. "
                f"Proceeding assuming kWh; verify upstream unit normalization."
            )
        co2e = round(consumption * factor, 4)
        return EmissionResult(
            resource_type=resource_type, scope=2, co2e_kg=co2e,
            factor_used=factor, factor_unit="kg_co2_per_kwh", factor_source=grid["source"],
            site=site, billing_period=billing_period, included_in_total=True,
            errors=errors, warnings=warnings,
        )

    # ---- Fuel: Scope 1 ----
    if resource_type == "fuel":
        fuel_type = record.get("fuel_type")
        if not fuel_type:
            errors.append("fuel record missing fuel_type")
            return EmissionResult(
                resource_type=resource_type, scope=1, co2e_kg=None,
                factor_used=None, factor_unit=None, factor_source=None,
                site=site, billing_period=billing_period, included_in_total=False,
                errors=errors, warnings=warnings,
            )
        factor, factor_unit, source = _resolve_fuel_factor(fuel_type, unit, factors)
        if factor is None:
            errors.append(
                f"Could not resolve emission factor for fuel_type={fuel_type!r}, unit={unit!r}. "
                f"Either fuel_type is not in the emission_factors table, or its unit is "
                f"ambiguous/unrecognised for that fuel."
            )
            return EmissionResult(
                resource_type=resource_type, scope=1, co2e_kg=None,
                factor_used=None, factor_unit=None, factor_source=None,
                site=site, billing_period=billing_period, included_in_total=False,
                errors=errors, warnings=warnings,
            )
        co2e = round(consumption * factor, 4)
        return EmissionResult(
            resource_type=resource_type, scope=1, co2e_kg=co2e,
            factor_used=factor, factor_unit=factor_unit, factor_source=source,
            site=site, billing_period=billing_period, included_in_total=True,
            errors=errors, warnings=warnings,
        )

    # ---- Water: excluded from GHG scope by default, reported for context ----
    if resource_type == "water":
        w = factors["water"]["supply_and_treatment"]
        factor = w["factor_kg_co2e_per_m3"]
        unit_norm = (unit or "").strip().lower()
        if unit_norm not in ("m3", "m^3"):
            warnings.append(
                f"Expected unit 'm3' for water, got {unit!r}. "
                f"Proceeding assuming m3; verify upstream unit normalization."
            )
        co2e_context_only = round(consumption * factor, 4)
        warnings.append(
            "Water is excluded from the Scope 1/2/3 GHG total by policy "
            "(not a standard GHG Protocol boundary item for this company type); "
            "co2e_kg here is contextual only, not summed into totals."
        )
        return EmissionResult(
            resource_type=resource_type, scope=None, co2e_kg=co2e_context_only,
            factor_used=factor, factor_unit="kg_co2e_per_m3", factor_source=w["source"],
            site=site, billing_period=billing_period, included_in_total=False,
            errors=errors, warnings=warnings,
        )

    errors.append("Unhandled resource_type branch")  # unreachable given the guard above
    return EmissionResult(
        resource_type=resource_type, scope=None, co2e_kg=None,
        factor_used=None, factor_unit=None, factor_source=None,
        site=site, billing_period=billing_period, included_in_total=False,
        errors=errors, warnings=warnings,
    )


def compute_batch(records: list, factors: dict = None) -> list:
    factors = factors if factors is not None else load_emission_factors()
    return [compute_emissions(r, factors) for r in records]


def aggregate_footprint(results: list) -> dict:
    """
    Rolls a list of EmissionResults up into the footprint report shape
    consumed downstream by Person 2 (trend analysis / anomaly detection
    and budget forecasting) and Person 4 (final assembly).

    Grouping: by site, then scope, plus a company-wide total. Records
    that failed calculation are collected separately (never silently
    dropped) under "failed_records".
    """
    by_site = {}
    company_scope1 = 0.0
    company_scope2 = 0.0
    company_scope3 = 0.0
    excluded_total = 0.0
    failed_records = []

    for r in results:
        if r.errors:
            failed_records.append({
                "resource_type": r.resource_type,
                "site": r.site,
                "billing_period": r.billing_period,
                "errors": r.errors,
            })
            continue

        site_key = r.site or "unknown_site"
        bucket = by_site.setdefault(site_key, {
            "scope1_kg": 0.0, "scope2_kg": 0.0, "scope3_kg": 0.0,
            "excluded_kg": 0.0, "records": 0,
        })
        bucket["records"] += 1

        if not r.included_in_total:
            bucket["excluded_kg"] += r.co2e_kg or 0.0
            excluded_total += r.co2e_kg or 0.0
            continue

        if r.scope == 1:
            bucket["scope1_kg"] += r.co2e_kg
            company_scope1 += r.co2e_kg
        elif r.scope == 2:
            bucket["scope2_kg"] += r.co2e_kg
            company_scope2 += r.co2e_kg
        elif r.scope == 3:
            bucket["scope3_kg"] += r.co2e_kg
            company_scope3 += r.co2e_kg

    for bucket in by_site.values():
        bucket["total_kg"] = round(
            bucket["scope1_kg"] + bucket["scope2_kg"] + bucket["scope3_kg"], 4
        )
        for k in ("scope1_kg", "scope2_kg", "scope3_kg", "excluded_kg"):
            bucket[k] = round(bucket[k], 4)

    return {
        "company_total": {
            "scope1_kg": round(company_scope1, 4),
            "scope2_kg": round(company_scope2, 4),
            "scope3_kg": round(company_scope3, 4),
            "total_kg": round(company_scope1 + company_scope2 + company_scope3, 4),
            "excluded_from_total_kg": round(excluded_total, 4),
        },
        "by_site": by_site,
        "failed_records": failed_records,
    }
