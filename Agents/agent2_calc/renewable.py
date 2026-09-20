"""
Agents/agent2_calc/renewable.py
=================================
Person 3 — Renewable Sizing Calculation (Agent 2 / Analysis)

Sizes a rooftop solar PV system against a company's actual electricity
consumption, using published Sri Lanka solar irradiance tiers, a typical
system performance ratio, and current market installation cost / export
tariff figures (see data/renewable_reference/solar_reference.json for
all sources).

Design goals (same "no black box" stance as Persons 1 & 2):
  - Deterministic arithmetic only. No LLM/NLP here — Person 4's layer
    turns these numbers into plain-English narrative and vendor matching.
  - Every assumption used (region tier, efficiency, cost, tariff) is
    reported back in the output with its source, so nothing is a
    hidden constant.
  - The one number this module refuses to default is the company's own
    electricity tariff (LKR/kWh) — that varies hugely by CEB tariff
    category and must come from the company's actual billing data
    (Person 1's aggregated cost figures), not a guess. Without it,
    sizing/offset/generation are still computed; savings/payback are
    reported as "not_evaluable" rather than fabricated.
"""

from __future__ import annotations
from decimal import Decimal

import json
from pathlib import Path
from typing import Optional

_REFERENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "renewable_reference" / "solar_reference.json"
)

_VALID_REGIONS = {"lowland_coastal", "mid_country", "hill_country"}


def load_solar_reference(path: Path = _REFERENCE_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_peak_sun_hours(region: Optional[str], custom_peak_sun_hours: Optional[float], reference: dict):
    """Returns (psh_value, source_description, warnings_list)."""
    warnings = []

    if custom_peak_sun_hours is not None:
        if custom_peak_sun_hours <= 0:
            return None, None, ["custom_peak_sun_hours must be positive; ignoring override."]
        return (
            custom_peak_sun_hours,
            "Custom site-specific irradiance value supplied by caller (e.g. from Global Solar Atlas coordinates lookup).",
            warnings,
        )

    region_key = (region or "mid_country").strip().lower()
    if region_key not in _VALID_REGIONS:
        warnings.append(
            f"Unrecognised region {region!r}; falling back to 'mid_country' (national average tier)."
        )
        region_key = "mid_country"

    region_data = reference["solar_irradiance_by_region"][region_key]
    warnings.append(
        f"Using regional irradiance TIER '{region_key}' ({region_data['peak_sun_hours']} peak sun hours/day), "
        f"not a site-specific measurement. {reference['solar_irradiance_by_region']['_meta']['notes']}"
    )
    return (
        region_data["peak_sun_hours"],
        reference["solar_irradiance_by_region"]["_meta"]["source"],
        warnings,
    )


def size_renewable_system(
    annual_consumption_kwh: float,
    effective_tariff_lkr_per_kwh: Optional[float] = None,
    region: str = "mid_country",
    target_offset_pct: float = 1.0,
    system_size_kwp: Optional[float] = None,
    custom_peak_sun_hours: Optional[float] = None,
    cost_per_kw_lkr: Optional[float] = None,
    feed_in_tariff_lkr_per_kwh: Optional[float] = None,
    reference: Optional[dict] = None,
    
) -> dict:
    """
    Two modes, chosen by which argument is supplied:
      - target_offset_pct (default 1.0 = size to fully offset consumption):
        solves for the system size (kWp) needed to hit that offset.
      - system_size_kwp: evaluates a FIXED system size the company already
        has or is considering, instead of solving for one.

    Returns a single dict: assumptions used (with sources), sizing result,
    generation/offset, and — if effective_tariff_lkr_per_kwh is provided —
    savings and payback period. Never raises; validation failures come
    back as `errors`, non-fatal caveats as `warnings`.
    """
    reference = reference if reference is not None else load_solar_reference()
    errors = []
    warnings = []
    if isinstance(annual_consumption_kwh, Decimal):
        annual_consumption_kwh = float(annual_consumption_kwh)

    if annual_consumption_kwh is None or not isinstance(annual_consumption_kwh, (int, float)) or annual_consumption_kwh <= 0:
        errors.append(f"annual_consumption_kwh must be a positive number, got {annual_consumption_kwh!r}")

    if system_size_kwp is not None and (not isinstance(system_size_kwp, (int, float)) or system_size_kwp <= 0):
        errors.append(f"system_size_kwp must be a positive number if provided, got {system_size_kwp!r}")

    if system_size_kwp is None and (target_offset_pct is None or target_offset_pct <= 0):
        errors.append(f"target_offset_pct must be a positive number, got {target_offset_pct!r}")

    if errors:
        return {"errors": errors, "warnings": warnings}

    if target_offset_pct is not None and target_offset_pct > 1.5:
        warnings.append(
            f"target_offset_pct={target_offset_pct} implies sizing for well over 100% of consumption "
            f"(net exporter). Confirm this is intended before quoting to the client."
        )

    psh, psh_source, psh_warnings = _resolve_peak_sun_hours(region, custom_peak_sun_hours, reference)
    warnings.extend(psh_warnings)
    if psh is None:
        errors.append("Could not resolve a peak sun hours value.")
        return {"errors": errors, "warnings": warnings}

    efficiency = reference["system_efficiency"]["value"]
    annual_generation_per_kwp = psh * 365 * efficiency

    mode = "fixed_size" if system_size_kwp is not None else "target_offset"
    if mode == "fixed_size":
        resolved_size_kwp = system_size_kwp
    else:
        target_annual_generation_kwh = annual_consumption_kwh * target_offset_pct
        resolved_size_kwp = target_annual_generation_kwh / annual_generation_per_kwp

    actual_annual_generation_kwh = resolved_size_kwp * annual_generation_per_kwp
    actual_offset_pct = actual_annual_generation_kwh / annual_consumption_kwh

    self_consumed_kwh = min(actual_annual_generation_kwh, annual_consumption_kwh)
    exported_kwh = max(0.0, actual_annual_generation_kwh - annual_consumption_kwh)

    cost_ref = reference["installation_cost"]["on_grid_no_battery"]
    resolved_cost_per_kw = cost_per_kw_lkr if cost_per_kw_lkr is not None else cost_ref["cost_lkr_per_kw_default"]
    if cost_per_kw_lkr is None:
        warnings.append(
            f"Using default installation cost of LKR {resolved_cost_per_kw:,.0f}/kW "
            f"(market range LKR {cost_ref['cost_lkr_per_kw_low']:,.0f}-{cost_ref['cost_lkr_per_kw_high']:,.0f}/kW, "
            f"{cost_ref['source']}). {cost_ref['source_note']}"
        )
    system_cost_lkr = resolved_size_kwp * resolved_cost_per_kw

    result = {
        "errors": [],
        "warnings": warnings,
        "assumptions": {
            "mode": mode,
            "region": region,
            "peak_sun_hours_per_day": psh,
            "peak_sun_hours_source": psh_source,
            "system_efficiency": efficiency,
            "system_efficiency_source": reference["system_efficiency"]["source"],
            "cost_per_kw_lkr": resolved_cost_per_kw,
            "target_offset_pct_requested": target_offset_pct if mode == "target_offset" else None,
        },
        "sizing": {
            "system_size_kwp": round(resolved_size_kwp, 3),
            "annual_generation_kwh": round(actual_annual_generation_kwh, 2),
            "actual_offset_pct": round(actual_offset_pct, 4),
            "self_consumed_kwh": round(self_consumed_kwh, 2),
            "exported_kwh": round(exported_kwh, 2),
        },
        "cost": {
            "system_cost_lkr": round(system_cost_lkr, 2),
        },
        "savings_and_payback": None,
    }

    if effective_tariff_lkr_per_kwh is None:
        result["savings_and_payback"] = {
            "status": "not_evaluable",
            "message": (
                "effective_tariff_lkr_per_kwh (the company's own current CEB rate) was not "
                "provided — cannot compute savings or payback without it. Derive it from the "
                "company's actual billing data (cost_lkr / consumption_kwh), do not guess a "
                "national average tariff category."
            ),
        }
        return result

    if effective_tariff_lkr_per_kwh <= 0:
        result["savings_and_payback"] = {
            "status": "not_evaluable",
            "message": f"effective_tariff_lkr_per_kwh must be positive, got {effective_tariff_lkr_per_kwh!r}.",
        }
        return result

    feed_in_ref = reference["feed_in_tariff"]["net_accounting_export"]
    resolved_feed_in = feed_in_tariff_lkr_per_kwh if feed_in_tariff_lkr_per_kwh is not None else feed_in_ref["rate_lkr_per_kwh_default"]
    if feed_in_tariff_lkr_per_kwh is None and exported_kwh > 0:
        warnings.append(
            f"Using default feed-in/export tariff of LKR {resolved_feed_in}/kWh "
            f"(PUCSL band LKR {feed_in_ref['rate_lkr_per_kwh_low']}-{feed_in_ref['rate_lkr_per_kwh_high']}/kWh "
            f"depending on system capacity — {feed_in_ref['source']}). {feed_in_ref['notes']}"
        )

    annual_savings_lkr = self_consumed_kwh * effective_tariff_lkr_per_kwh + exported_kwh * resolved_feed_in

    if annual_savings_lkr <= 0:
        payback_status = "no_savings"
        payback_years = None
        message = "Computed annual savings is zero or negative — payback period is undefined."
    else:
        payback_years = system_cost_lkr / annual_savings_lkr
        payback_status = "ok"
        message = f"Estimated payback in {payback_years:.1f} years."

    result["assumptions"]["effective_tariff_lkr_per_kwh"] = effective_tariff_lkr_per_kwh
    result["assumptions"]["feed_in_tariff_lkr_per_kwh"] = resolved_feed_in
    result["savings_and_payback"] = {
        "status": payback_status,
        "annual_savings_lkr": round(annual_savings_lkr, 2),
        "payback_years": round(payback_years, 2) if payback_years is not None else None,
        "message": message,
    }

    return result


def evaluate_existing_system(
    system_size_kwp: float,
    annual_consumption_kwh: float,
    effective_tariff_lkr_per_kwh: Optional[float] = None,
    region: str = "mid_country",
    **kwargs,
) -> dict:
    """
    Convenience wrapper: evaluates a system size the company already has
    (or is specifically considering) rather than solving for a target
    offset. Same output shape as size_renewable_system().
    """
    return size_renewable_system(
        annual_consumption_kwh=annual_consumption_kwh,
        effective_tariff_lkr_per_kwh=effective_tariff_lkr_per_kwh,
        region=region,
        system_size_kwp=system_size_kwp,
        **kwargs,
    )
