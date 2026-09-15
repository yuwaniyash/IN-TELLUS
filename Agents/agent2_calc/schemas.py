from typing import Optional, Any, Dict, List

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    file_id: int = Field(..., gt=0, description="raw_files.file_id to analyze, from Agent 1's extraction step")

    monthly_budget_lkr: Optional[float] = Field(
        default=None, ge=0,
        description="Company-stated monthly budget for the resource in this file, if known. "
                     "Enables the budget-overrun check; skipped (not_evaluable) if omitted."
    )
    effective_tariff_lkr_per_kwh: Optional[float] = Field(
        default=None, ge=0,
        description="Override for the company's own electricity rate. If omitted, Agent 2 derives "
                     "it from the company's own historical cost/consumption data where possible."
    )
    region: str = Field(
        default="mid_country",
        description="Solar irradiance tier for renewable sizing: lowland_coastal | mid_country | hill_country"
    )
    sector: Optional[str] = Field(
        default=None,
        description="Company sector, for the industry benchmark comparison (e.g. 'office', 'retail_hospitality', "
                     "'factory_industrial', 'warehouse'). Skipped if omitted."
    )
    floor_area_m2: Optional[float] = Field(
        default=None, ge=0,
        description="Floor area in m2, needed to compute the company's own electricity intensity for "
                     "the benchmark comparison. Skipped (benchmark returned without comparison) if omitted."
    )


class AnalyzeResponse(BaseModel):
    success: bool
    result: Optional[Dict[str, Any]] = None
    warnings: List[str] = Field(default_factory=list)
