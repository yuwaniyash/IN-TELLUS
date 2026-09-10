from typing import Optional, List
from pydantic import BaseModel, Field


class ExtractionRecord(BaseModel):
    record_id: Optional[str] = None

    resource_type: str = Field(
        ...,
        description="electricity, water, or fuel"
    )

    fuel_type: Optional[str] = None

    consumption: Optional[float] = None

    unit: Optional[str] = None

    billing_period: Optional[str] = None

    # Exact transaction date (YYYY-MM-DD), populated for individual fuel
    # transactions where billing_period (month-level) alone would lose
    # day-level detail. None for bill-based records, where billing_period
    # is the meaningful unit.
    transaction_date: Optional[str] = None

    site: Optional[str] = None

    country: str = "Sri Lanka"

    account_number: Optional[str] = None

    previous_reading: Optional[float] = None

    current_reading: Optional[float] = None

    amount_lkr: Optional[float] = None

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0
    )

    extraction_method: str = "unknown"

    warnings: List[str] = Field(
        default_factory=list
    )


class ExtractionResponse(BaseModel):
    success: bool

    records: List[ExtractionRecord]

    source_file: Optional[str] = None

    warnings: List[str] = Field(
        default_factory=list
    )