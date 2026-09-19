"""
Agent 3 - Step 4 (Security): Vet retrieved sources.

Even though ingest.py sets approved=True on every chunk at ingestion time,
this re-checks each retrieved document before it reaches the LLM prompt -
defense in depth. Anything failing the check is dropped and logged rather
than silently passed through.
"""


def vet_sources(docs: list) -> list:
    vetted = []
    for d in docs:
        if d.metadata.get("approved") is True and d.metadata.get("source_id"):
            vetted.append(d)
        else:
            print(f"[SECURITY] Rejected unvetted source: {d.metadata}")
    return vetted
