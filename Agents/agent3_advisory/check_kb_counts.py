import os
from dotenv import load_dotenv
import psycopg

load_dotenv()

with psycopg.connect(os.environ["DATABASE_URL_POOLED"]) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT cmetadata->>'source_id', count(*)
            FROM langchain_pg_embedding
            GROUP BY cmetadata->>'source_id'
            ORDER BY 2 DESC;
        """)
        rows = cur.fetchall()
        for row in rows:
            print(row)
        print(f"\nTotal distinct source_ids: {len(rows)}")
        print(f"Total rows: {sum(r[1] for r in rows)}")