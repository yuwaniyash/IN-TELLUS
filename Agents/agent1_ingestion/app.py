from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException

from .schemas import (
    ExtractionRecord,
    ExtractionResponse
)

from .llm_fallback import llm_fallback
from .pipeline import run_extraction_pipeline

from Security_Layer.sanitization import validate_file
from Security_Layer.file_intake import get_connection, update_processing_status
import uuid

# Matches text_extraction.py's UPLOAD_ROOT (repo root) and file_path
# convention (relative to repo root).
REPO_ROOT = Path(__file__).parent.parent.parent
UPLOAD_DIR = REPO_ROOT / "uploads"


app = FastAPI(
    title="Agent 1 - Data Extraction",
    version="1.0.0"
)

def create_raw_file_record(
    file_name: str,
    resource_type: str,
    file_type: str,
    file_path: str
) -> int:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO raw_files
            (file_name, resource_type, file_type, file_path, processing_status)
        VALUES
            (%s, %s, %s, %s, %s)
        RETURNING file_id;
        """,
        (
            file_name,
            resource_type,
            file_type,
            file_path,
            "PENDING"
        )
    )

    file_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return file_id

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

    # =======================================================
# PERSON 1
# File validation + temporary saving
# =======================================================

    if not file.filename:
        raise HTTPException(
        status_code=400,
        detail="No filename provided"
    )

    suffix = Path(file.filename).suffix.lower()

    if suffix not in {".pdf", ".csv"}:
        raise HTTPException(
        status_code=400,
        detail=f"Unsupported file type '{suffix}'. Only .pdf and .csv are supported."
    )

    file_type = suffix.replace(".", "")

    contents = await file.read()

# Use Person 1's security validation
    is_valid, reason = validate_file(contents, file.filename)

    if not is_valid:
     raise HTTPException(
        status_code=400,
        detail=reason
    )

# Save using a unique filename
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


    unique_filename = f"{uuid.uuid4()}{suffix}"
    saved_path = UPLOAD_DIR / unique_filename
    saved_path.write_bytes(contents)

    relative_file_path = str(saved_path.relative_to(REPO_ROOT))

    # =======================================================
    # PERSON 2 + PERSON 3
    # Text extraction, rule-based parsing, unit lookup
    # =======================================================

    try:
        raw_text, partial_data_list = run_extraction_pipeline(
            relative_file_path,
            file_type
        )

        # Resource type is determined by the extraction pipeline.
        resource_types = {
            data.get("resource_type")
            for data in partial_data_list
            if data.get("resource_type")
        }

        if not resource_types:
            raise ValueError(
                "Could not determine resource type from the uploaded file."
            )

        # A single uploaded bill should have one resource type.
        resource_type = next(iter(resource_types))

        # Create the raw_files record.
        file_id = create_raw_file_record(
            file_name=file.filename,
            resource_type=resource_type,
            file_type=file_type,
            file_path=relative_file_path
        )

        # Extraction is now actively being processed.
        update_processing_status(file_id, "PROCESSING")

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

        record.record_id = file_id
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
    update_processing_status(file_id, "COMPLETED")
    return ExtractionResponse(
        success=True,
        records=records,
        source_file=file.filename,
        warnings=response_warnings
    )