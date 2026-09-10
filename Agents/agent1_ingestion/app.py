from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException

from schemas import (
    ExtractionRecord,
    ExtractionResponse
)

from llm_fallback import llm_fallback
from pipeline import run_extraction_pipeline

# Matches text_extraction.py's UPLOAD_ROOT (repo root) and file_path
# convention (relative to repo root).
REPO_ROOT = Path(__file__).parent.parent.parent
UPLOAD_DIR = REPO_ROOT / "uploads"


app = FastAPI(
    title="Agent 1 - Data Extraction",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "agent": "Agent 1",
        "status": "running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.post("/extract", response_model=ExtractionResponse)
async def extract(
    file: UploadFile = File(...)
):

    # =======================================================
    # PERSON 1
    # File validation + saving
    # =======================================================

    # TODO: replace this whole block with Person 1's validate_and_save_file(file)
    # once it's ready — it should own file-type/size/CSV-injection checks,
    # the raw_files DB insert, and processing_status tracking. This is
    # only enough to unblock testing the real Person 2/3 pipeline today.

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided"
        )

    suffix = Path(file.filename).suffix.lower()
    if suffix == ".pdf":
        file_type = "pdf"
    elif suffix == ".csv":
        file_type = "csv"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Only .pdf and .csv are supported."
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_path = UPLOAD_DIR / file.filename
    contents = await file.read()
    saved_path.write_bytes(contents)

    # file_path passed to Person 2's extract_text() must be relative to
    # REPO_ROOT, matching text_extraction.py's UPLOAD_ROOT convention.
    relative_file_path = str(saved_path.relative_to(REPO_ROOT))

    # =======================================================
    # PERSON 2 + PERSON 3
    # Text extraction, rule-based parsing, unit lookup
    # =======================================================

    try:
        raw_text, partial_data_list = run_extraction_pipeline(relative_file_path, file_type)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Extraction pipeline failed",
                "error": str(e)
            }
        )

    # =======================================================
    # PER-RECORD: REQUIRED FIELDS CHECK -> LLM FALLBACK -> VALIDATION
    #
    # A PDF or single-bill CSV produces exactly one partial_data dict here.
    # A fuel transaction log produces one per transaction row (could be
    # 1000+) — each is checked and validated independently so one bad row
    # never blocks the rest of the file, matching Person 2's "never fail
    # all-or-nothing" design in rule_parser.py / fuel_csv_parser.py.
    # =======================================================

    # billing_period is a hard requirement for bills (it's the only period
    # indicator they have), but NOT for fuel transactions — those already
    # carry their own transaction_date, and billing_period is just a
    # convenience field derived from it. Forcing a fuel record with a good
    # quantity/unit/site/fuel_type through the full LLM fallback just
    # because its date didn't parse throws away a real confidence score
    # and mislabels the record, for no benefit — the missing date is
    # already captured as a warning on the record itself.
    required_fields = [
        "resource_type",
        "consumption",
        "unit",
        "billing_period",
        "site"
    ]
    required_fields_fuel = [
        "resource_type",
        "consumption",
        "unit",
        "site"
    ]

    records = []
    response_warnings = []

    for partial_data in partial_data_list:

        fields_to_check = (
            required_fields_fuel
            if partial_data.get("resource_type") == "fuel"
            else required_fields
        )

        missing_fields = [
            field
            for field in fields_to_check
            if not partial_data.get(field)
        ]

        if missing_fields:
            partial_data = llm_fallback(
                raw_text,
                partial_data
            )

        try:
            record = ExtractionRecord(**partial_data)
        except Exception as e:
            response_warnings.append(f"record dropped, failed validation: {e}")
            continue

        records.append(record)
        response_warnings.extend(record.warnings)

    if not records:
        raise HTTPException(
            status_code=422,
            detail={"message": "No records could be extracted or validated from this file."}
        )

    # =======================================================
    # RETURN CLEAN STRUCTURED DATA
    # =======================================================

    return ExtractionResponse(
        success=True,
        records=records,
        source_file=file.filename,
        warnings=response_warnings
    )