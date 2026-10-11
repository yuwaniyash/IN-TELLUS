import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Agents.agent2_calc.benchmarks import retrieve_benchmark, compare_to_benchmark, load_benchmarks

REF = load_benchmarks()


def test_retrieve_known_sector():
    result = retrieve_benchmark("office", REF)
    assert result["found"] is True
    assert result["electricity_kwh_per_m2_per_year_median"] == 166


def test_retrieve_unknown_sector_does_not_guess():
    result = retrieve_benchmark("moon_base", REF)
    assert result["found"] is False
    assert "available_sectors" in result


def test_sector_lookup_is_case_and_space_insensitive():
    result = retrieve_benchmark("Retail Hospitality", REF)
    assert result["found"] is True


def test_compare_without_floor_area_is_not_evaluable():
    result = compare_to_benchmark(annual_kwh=100000, floor_area_m2=None, sector="office", benchmarks=REF)
    assert result["comparison"]["status"] == "not_evaluable"
    assert result["benchmark"]["found"] is True  # benchmark itself still returned


def test_compare_above_benchmark():
    # 166 kWh/m2 median; use a company at 300 kWh/m2 -> clearly above
    result = compare_to_benchmark(annual_kwh=300 * 1000, floor_area_m2=1000, sector="office", benchmarks=REF)
    assert result["comparison"]["status"] == "above_benchmark"


def test_compare_below_benchmark():
    result = compare_to_benchmark(annual_kwh=50 * 1000, floor_area_m2=1000, sector="office", benchmarks=REF)
    assert result["comparison"]["status"] == "below_benchmark"


def test_compare_in_line_with_benchmark():
    result = compare_to_benchmark(annual_kwh=166 * 1000, floor_area_m2=1000, sector="office", benchmarks=REF)
    assert result["comparison"]["status"] == "in_line_with_benchmark"


def test_compare_unknown_sector_not_evaluable():
    result = compare_to_benchmark(annual_kwh=100000, floor_area_m2=1000, sector="spaceport", benchmarks=REF)
    assert result["comparison"]["status"] == "not_evaluable"
    assert result["benchmark"]["found"] is False


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
