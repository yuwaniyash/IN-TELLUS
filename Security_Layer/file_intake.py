"""
Security_Layer / file_intake.py
=================================
Handles what happens AFTER a file passes sanitization:
  1. Save the file to disk
  2. Create a row in the raw_files table
  3. Track processing_status as the pipeline progresses

This file does NOT decide if a file is safe -- that's sanitization.py's job.
It only runs once sanitization has already approved the file.
"""

import os
import uuid
import psycopg2
from dotenv import load_dotenv

from sanitization import validate_file  # reuse the safety check

# ============================================================
# DATABASE CONNECTION
# ============================================================
# Loads DATABASE_URL from your .env file -- never hardcode credentials in code
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL not found. Make sure your .env file exists and contains:\n"
        "DATABASE_URL=postgresql://username:password@host/dbname?sslmode=require"
    )

def get_connection():
    return psycopg2.connect(DATABASE_URL)


# ============================================================
# SAVE FILE TO DISK + CREATE raw_files ROW
# ============================================================

UPLOAD_DIR = "uploads"

def save_raw_file(file_bytes: bytes, original_filename: str, resource_type: str) -> dict:
    """
    Saves a file to disk and inserts a row into raw_files.
    resource_type should be one of: 'electricity', 'fuel', 'water'
    Returns {"file_id": ..., "file_path": ...}
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    ext = os.path.splitext(original_filename)[1].lower()
    unique_name = f"{uuid.uuid4()}{ext}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(save_path, "wb") as f:
        f.write(file_bytes)

    file_type = ext.replace(".", "")  # "pdf" or "csv"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO raw_files (file_name, resource_type, file_type, file_path, processing_status)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING file_id;
        """,
        (original_filename, resource_type, file_type, save_path, "PENDING"),
    )
    file_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return {"file_id": file_id, "file_path": save_path}


# ============================================================
# UPDATE PROCESSING STATUS
# ============================================================

def update_processing_status(file_id: int, status: str):
    """
    Valid statuses: 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE raw_files SET processing_status = %s WHERE file_id = %s;",
        (status, file_id),
    )
    conn.commit()
    cur.close()
    conn.close()


# ============================================================
# MAIN ENTRY POINT -- this is what Person 4 (U) will call
# ============================================================

def intake_file(file_bytes: bytes, filename: str, resource_type: str) -> dict:
    """
    Full intake pipeline: validate -> save -> record in DB.

    Returns:
        {"success": True, "file_id": ..., "file_path": ...}
        or
        {"success": False, "reason": "..."}
    """
    is_valid, reason = validate_file(file_bytes, filename)
    if not is_valid:
        return {"success": False, "reason": reason}

    result = save_raw_file(file_bytes, filename, resource_type)
    return {"success": True, "file_id": result["file_id"], "file_path": result["file_path"]}


# ============================================================
# TEST IT YOURSELF
# ============================================================
if __name__ == "__main__":
    fake_csv = b"date,site,consumption\n2025-07-01,Site A,4500\n"

    # Step 1: check validation works
    is_valid, reason = validate_file(fake_csv, "test_bill.csv")
    print(f"Validation: {is_valid}, {reason}")

    # Step 2: full intake (this WILL try to connect to your database)
    # Make sure DATABASE_URL above is set to your real Neon string first
    if is_valid:
        result = intake_file(fake_csv, "test_bill.csv", "electricity")
        print(f"Intake result: {result}")