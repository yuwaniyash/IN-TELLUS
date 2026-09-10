"""
Database / save_records.py
=================================
Routes a validated ExtractionRecord into the correct resource-specific
table (electricity_consumption / water_consumption / fuel_consumption)
based on record.resource_type.
"""

from datetime import date, datetime
import calendar

from Security_Layer.file_intake import get_connection


def billing_period_to_dates(period: str | None) -> tuple[date | None, date | None]:
    """'YYYY-MM' -> (first day, last day) of that month."""
    if not period:
        return None, None
    try:
        year, month = map(int, period.split("-"))
        start = date(year, month, 1)
        end = date(year, month, calendar.monthrange(year, month)[1])
        return start, end
    except (ValueError, TypeError):
        return None, None


def save_electricity_record(record: dict, file_id: int) -> int:
    start, end = billing_period_to_dates(record.get("billing_period"))
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO electricity_consumption
                (site, billing_period_start, billing_period_end,
                 previous_reading_kwh, current_reading_kwh, consumption_kwh,
                 unit, electricity_cost_lkr, account_no, source_file_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING electricity_record_id;
            """,
            (
                record.get("site"), start, end,
                record.get("previous_reading"), record.get("current_reading"),
                record.get("consumption"), record.get("unit"),
                record.get("amount_lkr"), record.get("account_number"),
                file_id,
            ),
        )
        rec_id = cur.fetchone()[0]
        conn.commit()
        return rec_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def save_water_record(record: dict, file_id: int) -> int:
    start, end = billing_period_to_dates(record.get("billing_period"))
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO water_consumption
                (site, billing_period_start, billing_period_end,
                 previous_reading_m3, current_reading_m3, consumption_m3,
                 unit, water_cost_lkr, account_no, source_file_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING water_record_id;
            """,
            (
                record.get("site"), start, end,
                record.get("previous_reading"), record.get("current_reading"),
                record.get("consumption"), record.get("unit"),
                record.get("amount_lkr"), record.get("account_number"),
                file_id,
            ),
        )
        rec_id = cur.fetchone()[0]
        conn.commit()
        return rec_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def save_fuel_record(record: dict, file_id: int) -> int:
    txn_date = None
    if record.get("transaction_date"):
        try:
            txn_date = datetime.fromisoformat(record["transaction_date"]).date()
        except (ValueError, TypeError):
            txn_date = None

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO fuel_consumption
                (transaction_date, site, fuel_type, quantity, unit, source_file_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING fuel_record_id;
            """,
            (
                txn_date, record.get("site"), record.get("fuel_type"),
                record.get("consumption"), record.get("unit"), file_id,
            ),
        )
        rec_id = cur.fetchone()[0]
        conn.commit()
        return rec_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def save_extraction_record(record: dict, file_id: int) -> int:
    """Dispatches to the right save_*_record() based on resource_type."""
    resource_type = record.get("resource_type")
    if resource_type == "electricity":
        return save_electricity_record(record, file_id)
    elif resource_type == "water":
        return save_water_record(record, file_id)
    elif resource_type == "fuel":
        return save_fuel_record(record, file_id)
    else:
        raise ValueError(f"Unknown resource_type: {resource_type}")