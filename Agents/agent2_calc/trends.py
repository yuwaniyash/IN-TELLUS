"""
Agents/agent2_calc/trends.py
=============================
Person 2 — Trend Analysis: Anomaly Detection + Budget Forecasting
(Agent 2 / Analysis)

Operates on a time-ordered series of period values — Scope 1/2/3
footprint kg CO2e, raw consumption, or cost in LKR. The caller decides
what "value" means and labels it via `metric_name` for traceability;
this module doesn't care what unit it's looking at, only whether it's
moving in a way worth flagging.

Design goals:
  - Never invents a trend/anomaly from too little data. Insufficient
    history returns an explicit "insufficient_data"-style result, not
    a guess dressed up as a finding.
  - Deterministic statistical methods only (rolling mean/stdev,
    z-score, ordinary least-squares regression) — no LLM/NLP here,
    that's Person 4's context-enrichment layer downstream.
  - Every flagged anomaly and forecast carries the numbers that
    produced it, so the report is auditable end-to-end.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, asdict
from typing import Optional

MIN_PERIODS_FOR_BASELINE = 2    # minimum prior periods needed to form a baseline
MIN_PERIODS_TOTAL = 3           # minimum total periods before any anomaly/forecast check runs

Z_SCORE_THRESHOLD = 2.0         # ~95% CI under a normal approximation
PCT_DEVIATION_THRESHOLD = 0.30  # 30% above/below baseline mean
UNDER_BUDGET_MARGIN = 0.10      # more than 10% under budget is called out separately from "on budget"


@dataclass
class AnomalyFlag:
    period: str
    value: float
    baseline_mean: Optional[float]
    baseline_stdev: Optional[float]
    z_score: Optional[float]
    pct_deviation: float
    flagged: bool
    trigger: Optional[str]    # "z_score" | "pct_deviation" | "both" | None
    direction: Optional[str]  # "above" | "below" | None

    def to_dict(self) -> dict:
        return asdict(self)


def check_sufficient_history(series: list) -> dict:
    n = len(series)
    sufficient = n >= MIN_PERIODS_TOTAL
    return {
        "sufficient": sufficient,
        "periods_available": n,
        "min_required": MIN_PERIODS_TOTAL,
        "message": (
            f"Only {n} period(s) of data available; need at least {MIN_PERIODS_TOTAL} "
            f"({MIN_PERIODS_FOR_BASELINE} for baseline + 1 current) before anomaly "
            f"detection or forecasting can run reliably."
            if not sufficient else
            f"{n} periods available — sufficient for trend analysis."
        ),
    }


def _sorted_by_period(series: list) -> list:
    return sorted(series, key=lambda p: p["period"])


def compute_baseline(prior_values: list) -> dict:
    """Mean + population stdev of the periods PRIOR to the one being checked."""
    if not prior_values:
        return {"mean": None, "stdev": None, "n": 0}
    mean = statistics.mean(prior_values)
    stdev = statistics.pstdev(prior_values) if len(prior_values) >= 2 else None
    return {"mean": mean, "stdev": stdev, "n": len(prior_values)}


def detect_anomalies(series: list) -> list:
    """
    series: list of {"period": "YYYY-MM", "value": float, "site": optional}

    For each period from index MIN_PERIODS_FOR_BASELINE onward, computes
    a rolling baseline from ALL strictly-prior periods, then flags if the
    current value deviates beyond either the z-score or percentage
    threshold. Periods before a baseline is available are skipped
    entirely (not fabricated with a fake baseline).
    """
    ordered = _sorted_by_period(series)
    flags = []

    for i in range(MIN_PERIODS_FOR_BASELINE, len(ordered)):
        prior_values = [p["value"] for p in ordered[:i]]
        current = ordered[i]
        baseline = compute_baseline(prior_values)
        mean = baseline["mean"]
        stdev = baseline["stdev"]

        pct_dev = (current["value"] - mean) / mean if mean else 0.0

        z = None
        z_flag = False
        if stdev and stdev > 0:
            z = (current["value"] - mean) / stdev
            z_flag = abs(z) >= Z_SCORE_THRESHOLD

        pct_flag = abs(pct_dev) >= PCT_DEVIATION_THRESHOLD
        flagged = z_flag or pct_flag

        trigger = None
        if z_flag and pct_flag:
            trigger = "both"
        elif z_flag:
            trigger = "z_score"
        elif pct_flag:
            trigger = "pct_deviation"

        direction = None
        if flagged:
            direction = "above" if current["value"] > mean else "below"

        flags.append(AnomalyFlag(
            period=current["period"], value=current["value"],
            baseline_mean=round(mean, 4) if mean is not None else None,
            baseline_stdev=round(stdev, 4) if stdev is not None else None,
            z_score=round(z, 4) if z is not None else None,
            pct_deviation=round(pct_dev, 4),
            flagged=flagged, trigger=trigger, direction=direction,
        ))

    return flags


def detect_recurring_pattern(flags: list) -> dict:
    """
    Distinguishes a one-time spike from a recurring/worsening trend by
    looking for 2+ CONSECUTIVE flagged periods in the same direction
    (both "above" or both "below" baseline).
    """
    flagged_only = [f for f in flags if f.flagged]
    if not flagged_only:
        return {"pattern": "none", "consecutive_runs": [], "message": "No anomalies flagged."}

    runs = []
    current_run = []
    for f in flags:
        if f.flagged:
            if current_run and current_run[-1].direction == f.direction:
                current_run.append(f)
            else:
                if len(current_run) >= 2:
                    runs.append(current_run)
                current_run = [f]
        else:
            if len(current_run) >= 2:
                runs.append(current_run)
            current_run = []
    if len(current_run) >= 2:
        runs.append(current_run)

    if runs:
        longest = max(runs, key=len)
        return {
            "pattern": "recurring",
            "consecutive_runs": [[f.period for f in r] for r in runs],
            "message": (
                f"{len(longest)} consecutive periods flagged {longest[0].direction} baseline "
                f"({longest[0].period} to {longest[-1].period}) — treat as a recurring/worsening "
                f"trend, not a one-off event."
            ),
        }
    return {
        "pattern": "one_time",
        "consecutive_runs": [],
        "message": (
            f"{len(flagged_only)} isolated anomaly period(s) flagged, no consecutive run — "
            f"likely one-time spike(s), not a sustained trend."
        ),
    }


def forecast_next_period(series: list) -> dict:
    """
    Projects the next period's value from available history.

    Method:
      - >=3 points: ordinary least-squares linear regression over the
        period index, projected one step forward. R^2 is reported
        alongside so the caller can judge forecast confidence.
      - 2 points: naive straight-line extrapolation through both
        points — reported as low confidence.
      - <2 points: cannot forecast at all; method="insufficient_data".
    """
    ordered = _sorted_by_period(series)
    n = len(ordered)

    if n < 2:
        return {
            "method": "insufficient_data", "forecast_value": None,
            "confidence": "none", "based_on_periods": n,
            "message": f"Only {n} period(s) available; need at least 2 to extrapolate a trend.",
        }

    xs = list(range(n))
    ys = [p["value"] for p in ordered]

    x_mean = statistics.mean(xs)
    y_mean = statistics.mean(ys)
    ss_xx = sum((x - x_mean) ** 2 for x in xs)
    ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))

    slope = (ss_xy / ss_xx) if ss_xx else 0.0
    intercept = y_mean - slope * x_mean

    next_x = n
    forecast_value = slope * next_x + intercept

    r_squared = None
    if n >= 3 and ss_xx > 0:
        ss_tot = sum((y - y_mean) ** 2 for y in ys)
        if ss_tot > 0:
            predicted = [slope * x + intercept for x in xs]
            ss_res = sum((y - p) ** 2 for y, p in zip(ys, predicted))
            r_squared = 1 - (ss_res / ss_tot)

    confidence = "low" if n < 3 else ("high" if (r_squared or 0) >= 0.6 else "medium")

    return {
        "method": "linear_regression" if n >= 3 else "two_point_extrapolation",
        "forecast_value": round(forecast_value, 4),
        "slope_per_period": round(slope, 4),
        "r_squared": round(r_squared, 4) if r_squared is not None else None,
        "confidence": confidence,
        "based_on_periods": n,
        "message": f"Forecast for the period after {ordered[-1]['period']}, based on {n} historical period(s).",
    }


def check_budget(forecast_value: Optional[float], budget: Optional[float]) -> dict:
    """
    Compares a forecast value (e.g. projected next-period cost in LKR)
    against a stated budget. Never guesses a budget — if either input
    is missing, returns an explicit "not_evaluable" status instead of
    a fabricated comparison.
    """
    if forecast_value is None or budget is None:
        return {
            "status": "not_evaluable",
            "message": "Forecast value or budget not provided — cannot evaluate overrun.",
            "forecast_value": forecast_value, "budget": budget,
            "overrun_pct": None, "overrun_amount": None,
        }

    if budget == 0:
        return {
            "status": "not_evaluable",
            "message": "Budget is zero — overrun percentage is undefined.",
            "forecast_value": forecast_value, "budget": budget,
            "overrun_pct": None, "overrun_amount": round(forecast_value, 4),
        }

    overrun_amount = forecast_value - budget
    overrun_pct = overrun_amount / budget

    if overrun_pct > 0:
        status = "over_budget"
    elif overrun_pct < -UNDER_BUDGET_MARGIN:
        status = "under_budget"
    else:
        status = "on_budget"

    return {
        "status": status,
        "forecast_value": round(forecast_value, 4),
        "budget": round(budget, 4),
        "overrun_amount": round(overrun_amount, 4),
        "overrun_pct": round(overrun_pct, 4),
        "message": (
            f"Forecast ({forecast_value:.2f}) is {abs(overrun_pct) * 100:.1f}% "
            f"{'over' if overrun_pct >= 0 else 'under'} budget ({budget:.2f})."
        ),
    }


def analyze_trend(series: list, metric_name: str = "value", budget: Optional[float] = None) -> dict:
    """
    Orchestrates the full Person 2 pipeline for ONE (site, metric) time
    series: sufficiency gate -> anomaly detection -> pattern detection
    -> forecast -> budget check. This is the function Person 4 calls
    once per site/metric when assembling the final Agent 2 output.
    """
    history_check = check_sufficient_history(series)
    result = {
        "metric_name": metric_name,
        "site": series[0].get("site") if series else None,
        "history_check": history_check,
        "anomalies": [],
        "pattern": None,
        "forecast": None,
        "budget_check": None,
    }

    if not history_check["sufficient"]:
        # Still attempt a forecast if 2 points exist, but mark budget check
        # as skipped rather than evaluating it against a shaky number.
        result["forecast"] = forecast_next_period(series)
        result["budget_check"] = {
            "status": "not_evaluable",
            "message": "Skipped: insufficient history for a reliable anomaly/budget check.",
            "forecast_value": None, "budget": budget,
            "overrun_pct": None, "overrun_amount": None,
        }
        return result

    flags = detect_anomalies(series)
    result["anomalies"] = [f.to_dict() for f in flags]
    result["pattern"] = detect_recurring_pattern(flags)

    forecast = forecast_next_period(series)
    result["forecast"] = forecast
    result["budget_check"] = check_budget(forecast.get("forecast_value"), budget)

    return result
