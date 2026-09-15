"""
Database/get_records.py
=========================
Read-side queries for Agent 2. Complements Database/save_records.py
(the write-side, owned by Agent 1's pipeline).

Every query here is scoped by company_id, taken from the caller's JWT
via Security_Layer.auth.get_current_company_id — NEVER a client-supplied
value. This is what makes multi-tenant isolation actually enforced
rather than just a documented convention (same principle Security_Layer/
auth.py's docstring calls out for Agent 1).
"""

from Security_Layer.file_intake import get_connection


def get_file_metadata(file_id: int, company_id: int):
    """
    Looks up a raw_files row, scoped to the caller's company. Returns
    None if the file doesn't exist OR belongs to a different company —
    the route should treat both cases identically (404), so one company
    can't use response differences to probe whether a file_id exists
    under a different account.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT file_id, file_name, resource_type, file_type, file_path,
                   processing_status, company_id
            FROM raw_files
            WHERE file_id = %s AND company_id = %s;
            """,
            (file_id, company_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "file_id": row[0], "file_name": row[1], "resource_type": row[2],
            "file_type": row[3], "file_path": row[4],
            "processing_status": row[5], "company_id": row[6],
        }
    finally:
        cur.close()
        conn.close()


def get_records_for_file(file_id: int, company_id: int, resource_type: str) -> list:
    """
    Fetches the specific consumption rows tied to ONE uploaded file,
    normalized into the shape Person 1's compute_batch() expects
    (resource_type, consumption, unit, fuel_type, site, billing_period).
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        if resource_type == "electricity":
            cur.execute(
                """
                SELECT site, consumption_kwh, unit, billing_period_start, electricity_cost_lkr
                FROM electricity_consumption
                WHERE source_file_id = %s AND company_id = %s;
                """,
                (file_id, company_id),
            )
            return [
                {
                    "resource_type": "electricity", "site": r[0], "consumption": r[1],
                    "unit": r[2], "billing_period": r[3].strftime("%Y-%m") if r[3] else None,
                    "amount_lkr": r[4],
                }
                for r in cur.fetchall()
            ]

        if resource_type == "water":
            cur.execute(
                """
                SELECT site, consumption_m3, unit, billing_period_start, water_cost_lkr
                FROM water_consumption
                WHERE source_file_id = %s AND company_id = %s;
                """,
                (file_id, company_id),
            )
            return [
                {
                    "resource_type": "water", "site": r[0], "consumption": r[1],
                    "unit": r[2], "billing_period": r[3].strftime("%Y-%m") if r[3] else None,
                    "amount_lkr": r[4],
                }
                for r in cur.fetchall()
            ]

        if resource_type == "fuel":
            cur.execute(
                """
                SELECT site, fuel_type, quantity, unit, transaction_date
                FROM fuel_consumption
                WHERE source_file_id = %s AND company_id = %s;
                """,
                (file_id, company_id),
            )
            return [
                {
                    "resource_type": "fuel", "site": r[0], "fuel_type": r[1],
                    "consumption": r[2], "unit": r[3],
                    "billing_period": r[4].strftime("%Y-%m") if r[4] else None,
                }
                for r in cur.fetchall()
            ]

        raise ValueError(f"Unknown resource_type: {resource_type}")
    finally:
        cur.close()
        conn.close()


def get_historical_monthly_series(company_id: int, site: str, resource_type: str, value_field: str = "consumption") -> list:
    """
    Fetches ALL historical periods (across every uploaded file, not just
    the current one) for one company + site + resource_type, aggregated
    to one value per calendar month. This is what feeds Person 2's trend
    analysis and Person 3's annual-consumption input — a single file's
    records can't provide a real time series on their own.

    value_field: "consumption" (kWh/L/m3) or "cost" (LKR, not available
    for fuel — the fuel_consumption table has no cost column yet).
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        if resource_type == "electricity":
            column = "consumption_kwh" if value_field == "consumption" else "electricity_cost_lkr"
            cur.execute(
                f"""
                SELECT to_char(billing_period_start, 'YYYY-MM') AS period, SUM({column}) AS total
                FROM electricity_consumption
                WHERE company_id = %s AND site = %s AND billing_period_start IS NOT NULL
                GROUP BY period ORDER BY period;
                """,
                (company_id, site),
            )
        elif resource_type == "water":
            column = "consumption_m3" if value_field == "consumption" else "water_cost_lkr"
            cur.execute(
                f"""
                SELECT to_char(billing_period_start, 'YYYY-MM') AS period, SUM({column}) AS total
                FROM water_consumption
                WHERE company_id = %s AND site = %s AND billing_period_start IS NOT NULL
                GROUP BY period ORDER BY period;
                """,
                (company_id, site),
            )
        elif resource_type == "fuel":
            if value_field != "consumption":
                raise ValueError("fuel_consumption has no cost column — only 'consumption' is supported for fuel.")
            cur.execute(
                """
                SELECT to_char(transaction_date, 'YYYY-MM') AS period, SUM(quantity) AS total
                FROM fuel_consumption
                WHERE company_id = %s AND site = %s AND transaction_date IS NOT NULL
                GROUP BY period ORDER BY period;
                """,
                (company_id, site),
            )
        else:
            raise ValueError(f"Unknown resource_type: {resource_type}")

        return [{"period": row[0], "value": float(row[1]), "site": site} for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def get_distinct_sites_for_company(company_id: int) -> list:
    """
    All sites this company has ANY consumption data for, across all
    three resource tables. Used to decide which sites to run trend
    analysis / renewable sizing for when a request doesn't name one.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT site FROM electricity_consumption WHERE company_id = %s AND site IS NOT NULL
            UNION
            SELECT site FROM water_consumption WHERE company_id = %s AND site IS NOT NULL
            UNION
            SELECT site FROM fuel_consumption WHERE company_id = %s AND site IS NOT NULL;
            """,
            (company_id, company_id, company_id),
        )
        return [row[0] for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()
