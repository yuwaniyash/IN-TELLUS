"""
Agents/agent2_calc/benchmarks.py
===================================
Person 4 IR ("Information Retrieval") component for Agent 2.

This is deliberately a simple, deterministic table lookup — not a
search engine or vector index. Agent 3 owns the project's more
substantial IR/RAG work (pgvector over case studies and vendors); this
module's only job is to answer "how does this company's electricity use
compare to a published benchmark for its sector?" so Person 4's LLM
narrative has an external reference point, not just the company's own
numbers in isolation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

_BENCHMARKS_PATH = Path(__file__).resolve().parents[2] / "data" / "benchmarks" / "industry_benchmarks.json"


def load_benchmarks(path: Path = _BENCHMARKS_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def retrieve_benchmark(sector: str, benchmarks: Optional[dict] = None) -> dict:
    """
    Returns the benchmark record for a sector, or an explicit
    "not_found" result — never guesses a number for an unlisted sector.
    """
    benchmarks = benchmarks if benchmarks is not None else load_benchmarks()
    sector_key = (sector or "").strip().lower().replace(" ", "_")
    entry = benchmarks["sectors"].get(sector_key)
    if entry is None:
        return {
            "found": False,
            "sector_requested": sector,
            "available_sectors": list(benchmarks["sectors"].keys()),
            "message": f"No benchmark on file for sector {sector!r}.",
        }
    return {"found": True, "sector_requested": sector, "sector_key": sector_key, **entry}


def compare_to_benchmark(annual_kwh: float, floor_area_m2: Optional[float], sector: str,
                          benchmarks: Optional[dict] = None) -> dict:
    """
    Compares the company's own annual electricity intensity (kWh/m2) to
    the sector benchmark, if floor area is available. Without floor
    area, still returns the benchmark reference (useful context on its
    own) but marks the comparison "not_evaluable" rather than fabricating
    an intensity figure from a missing denominator.
    """
    benchmark = retrieve_benchmark(sector, benchmarks)
    if not benchmark["found"]:
        return {"benchmark": benchmark, "comparison": {"status": "not_evaluable", "message": benchmark["message"]}}

    if floor_area_m2 is None or floor_area_m2 <= 0:
        return {
            "benchmark": benchmark,
            "comparison": {
                "status": "not_evaluable",
                "message": "floor_area_m2 not provided — cannot compute the company's own intensity to compare.",
            },
        }

    company_intensity = annual_kwh / floor_area_m2
    median = benchmark["electricity_kwh_per_m2_per_year_median"]
    ratio = company_intensity / median if median else None

    if ratio is None:
        status = "not_evaluable"
        message = "Benchmark median is zero or missing — cannot compute a ratio."
    elif ratio > 1.15:
        status = "above_benchmark"
        message = f"This company's electricity intensity is {ratio:.2f}x the {benchmark['sector_key']} sector median — worth investigating efficiency opportunities."
    elif ratio < 0.85:
        status = "below_benchmark"
        message = f"This company's electricity intensity is {ratio:.2f}x the {benchmark['sector_key']} sector median — better than typical for this sector."
    else:
        status = "in_line_with_benchmark"
        message = f"This company's electricity intensity ({ratio:.2f}x the sector median) is broadly in line with typical {benchmark['sector_key']} usage."

    return {
        "benchmark": benchmark,
        "comparison": {
            "status": status,
            "company_intensity_kwh_per_m2": round(company_intensity, 2),
            "benchmark_median_kwh_per_m2": median,
            "ratio_to_median": round(ratio, 3) if ratio is not None else None,
            "message": message,
        },
    }
