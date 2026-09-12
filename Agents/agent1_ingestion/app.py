from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends

from .schemas import (
    ExtractionRecord,
    ExtractionResponse
)

from .llm_fallback import llm_fallback
from Security_Layer.auth_routes import router as auth_router
from Security_Layer.auth import get_current_company_id

from .pipeline import run_extraction_pipeline
from Database.save_records import save_extraction_record
from Security_Layer.sanitization import validate_file
from Security_Layer.file_intake import get_connection, update_processing_status
import uuid

REPO_ROOT = Path(__file__).parent.parent.parent
UPLOAD_DIR = REPO_ROOT / "uploads"

app = FastAPI(
    title="Agent 1 - Data Extraction",
    version="1.0.0"
)
app.include_router(auth_router)


def create_raw_file_record(file_name, resource_type, file_type, file_path, company_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO raw_files (file_name, resource_type, file_type, file_path, processing_status, company_id)
               VALUES (%s, %s, %s, %s, 'PENDING', %s) RETURNING file_id;""",
            (file_name, resource_type, file_type, file_path, company_id)
        )
        file_id = cur.fetchone()[0]
        conn.commit()
        return file_id
    finally:
        cur.close()
        conn.close()


@app.get("/")
def root():
    return {"agent": "Agent 1", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/extract", response_model=ExtractionResponse)
async def extract(
    file: UploadFile = File(...),
    company_id: int = Depends(get_current_company_id),
):

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    suffix = Path(file.filename).suffix.lower()

    if suffix not in {".pdf", ".csv"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Only .pdf and .csv are supported."
        )

    file_type = suffix.replace(".", "")
    contents = await file.read()

    is_valid, reason = validate_file(contents, file.filename)
    if not is_valid:
        raise HTTPException(status_code=400, detail=reason)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    unique_filename = f"{uuid.uuid4()}{suffix}"
    saved_path = UPLOAD_DIR / unique_filename
    saved_path.write_bytes(contents)
    relative_file_path = str(saved_path.relative_to(REPO_ROOT))

    try:
        raw_text, partial_data_list = run_extraction_pipeline(str(saved_path), file_type, company_id)

        resource_types = {
            data.get("resource_type")
            for data in partial_data_list
            if data.get("resource_type")
        }

        if not resource_types:
            raise ValueError("Could not determine resource type from the uploaded file.")

        resource_type = next(iter(resource_types))

        file_id = create_raw_file_record(
            file_name=file.filename,
            resource_type=resource_type,
            file_type=file_type,
            file_path=relative_file_path,
            company_id=company_id
        )

        update_processing_status(file_id, "PROCESSING")

    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail={"message": "Extraction pipeline failed", "error": str(e)}
        )

    required_fields = [
        "resource_type",
        "consumption",
        "unit",
        "billing_period",
        "site",
        "previous_reading",
        "current_reading",
        "amount_lkr"
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

        missing_fields = [f for f in fields_to_check if not partial_data.get(f)]

        if missing_fields:
            partial_data = llm_fallback(raw_text, partial_data)

        try:
            record = ExtractionRecord(**partial_data)
        except Exception as e:
            response_warnings.append(f"record dropped, failed validation: {e}")
            continue

        record.record_id = file_id
        records.append(record)
        try:
            saved_id = save_extraction_record(record.model_dump(), file_id, company_id)
            record.record_id = str(saved_id)
        except Exception as e:
            response_warnings.append(f"record extracted but failed to save to database: {e}")
        response_warnings.extend(record.warnings)

    if not records:
        raise HTTPException(
            status_code=422,
            detail={"message": "No records could be extracted or validated from this file."}
        )

    update_processing_status(file_id, "COMPLETED")
    return ExtractionResponse(
        success=True,
        records=records,
        source_file=file.filename,
        warnings=response_warnings
    )