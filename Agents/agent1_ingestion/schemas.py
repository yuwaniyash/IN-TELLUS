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

    # The raw_files.file_id this extraction was saved under -- Agent 2's
    # POST /analyze takes exactly this value. Without it, the frontend has
    # no way to tell Agent 2 which file's records to analyze.
    file_id: int

    records: List[ExtractionRecord]

    source_file: Optional[str] = None

    warnings: List[str] = Field(
        default_factory=list
    )