"""
audit.py — persistence layer for Agent 3's audit trail.

Every completed run writes one row to agent3_runs. Premium-only steps
(solarpunk, vendor matching) write their own linked rows. Nothing here
does retrieval or generation -- purely inserts, called AFTER each step
in orchestration.py succeeds.
"""

import os
import json
from dotenv import load_dotenv
import psycopg
from psycopg.types.json import Jsonb

load_dotenv()

CONNECTION_STRING = os.environ["DATABASE_URL_POOLED"]


def log_agent3_run(
    company_id: str,
    tier: str,
    diagnostics_snapshot: dict,
    composed_query: str,
    retrieved_source_ids: list[str],
    generated_output: dict,
    site_id: str | None = None,
) -> int:
    """
    Logs the core Standard-tier run. Returns the new row's id, which
    solarpunk_plans/vendor_matches rows link back to via agent3_run_id.
    """
    with psycopg.connect(CONNECTION_STRING) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent3_runs
                    (company_id, site_id, diagnostics_snapshot, composed_query,
                     retrieved_source_ids, generated_output, tier)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    company_id,
                    site_id,
                    Jsonb(diagnostics_snapshot),
                    composed_query,
                    retrieved_source_ids,
                    Jsonb(generated_output),
                    tier,
                ),
            )
            run_id = cur.fetchone()[0]
            conn.commit()
    return run_id


def log_solarpunk_plan(
    agent3_run_id: int,
    proposal_snapshot: dict,
    retrieved_source_ids: list[str],
    generated_plan: dict,
) -> int:
    with psycopg.connect(CONNECTION_STRING) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO solarpunk_plans
                    (agent3_run_id, proposal_snapshot, retrieved_source_ids, generated_plan)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    agent3_run_id,
                    Jsonb(proposal_snapshot),
                    retrieved_source_ids,
                    Jsonb(generated_plan),
                ),
            )
            row_id = cur.fetchone()[0]
            conn.commit()
    return row_id


def log_vendor_matches(agent3_run_id: int, matched_categories: dict) -> int:
    with psycopg.connect(CONNECTION_STRING) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO vendor_matches (agent3_run_id, matched_categories)
                VALUES (%s, %s)
                RETURNING id;
                """,
                (agent3_run_id, Jsonb(matched_categories)),
            )
            row_id = cur.fetchone()[0]
            conn.commit()
    return row_id


def log_security_event(company_id: str | None, event_type: str, detail: dict) -> int:
    """
    For rejected/unvetted content, validation failures, etc. -- called
    from wherever such an event is detected, not just from orchestration.py.
    """
    with psycopg.connect(CONNECTION_STRING) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO security_events (company_id, event_type, detail)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (company_id, event_type, Jsonb(detail)),
            )
            row_id = cur.fetchone()[0]
            conn.commit()
    return row_id


def get_audit_trail_for_company(company_id: str) -> dict:
    """
    Reads back everything logged for a company -- this is what
    export_audit_trail() in orchestration.py will call.
    """
    with psycopg.connect(CONNECTION_STRING) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, tier, composed_query, retrieved_source_ids, created_at
                FROM agent3_runs
                WHERE company_id = %s
                ORDER BY created_at DESC;
                """,
                (company_id,),
            )
            runs = cur.fetchall()

            cur.execute(
                """
                SELECT id, event_type, detail, created_at
                FROM security_events
                WHERE company_id = %s
                ORDER BY created_at DESC;
                """,
                (company_id,),
            )
            events = cur.fetchall()

    return {
        "company_id": company_id,
        "run_ids": [r[0] for r in runs],
        "runs": [
            {"id": r[0], "tier": r[1], "composed_query": r[2], "retrieved_source_ids": r[3], "created_at": str(r[4])}
            for r in runs
        ],
        "security_events": [
            {"id": e[0], "event_type": e[1], "detail": e[2], "created_at": str(e[3])}
            for e in events
        ],
    }