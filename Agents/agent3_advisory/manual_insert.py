import os
import random
from dotenv import load_dotenv
import psycopg2

load_dotenv()

conn = psycopg2.connect(os.environ["DATABASE_URL_POOLED"])
cur = conn.cursor()

fake_embedding = [round(random.random(), 4) for _ in range(768)]

cur.execute(
    "INSERT INTO knowledge_base (content, metadata, embedding) VALUES (%s, %s, %s)",
    ("This is a manually inserted test row.", '{"source": "manual_test"}', fake_embedding),
)
conn.commit()

cur.execute("SELECT id, content FROM knowledge_base ORDER BY id DESC LIMIT 1;")
print("Inserted row:", cur.fetchone())

cur.close()
conn.close()
print("Step 2 done. Check Neon's table view for the new row.")