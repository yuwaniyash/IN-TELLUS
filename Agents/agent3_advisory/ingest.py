import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector

load_dotenv()

CONNECTION_STRING = os.environ["DATABASE_URL_POOLED"]
COLLECTION_NAME = "knowledge_base"

embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001",
    google_api_key=os.environ["GEMINI_API_KEY"],
    output_dimensionality=768,
)

test_vector = embeddings.embed_query("solar panel installation cost")
print(f"Embedded 1 string -> vector of length {len(test_vector)}")
assert len(test_vector) == 768, "Dimension mismatch - check output_dimensionality vs your table"

vectorstore = PGVector(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    connection=CONNECTION_STRING,
    use_jsonb=True,
)

# Placeholder docs -- each one now has a real source_id + title, matching
# what SourceCitation in schema.py requires. Person A: real KB ingestion
# needs to follow this same metadata shape (source_id, title, category, approved).
sample_docs = [
    {
        "source_id": "renewable_001",
        "title": "Rooftop solar and Scope 2 emissions",
        "content": "Installing rooftop solar panels can reduce a facility's Scope 2 emissions by offsetting grid electricity use.",
    },
    {
        "source_id": "intervention_001",
        "title": "LED lighting retrofit savings",
        "content": "LED lighting retrofits typically cut lighting-related energy consumption by 40-60% compared to fluorescent fixtures.",
    },
    {
        "source_id": "intervention_002",
        "title": "Fleet electrification",
        "content": "Switching commercial fleet vehicles to electric can significantly reduce Scope 1 emissions from fuel combustion.",
    },
    {
        "source_id": "intervention_003",
        "title": "Energy audits",
        "content": "Energy audits help identify the highest-impact, lowest-cost efficiency improvements in a facility.",
    },
    {
        "source_id": "renewable_002",
        "title": "Battery storage with solar",
        "content": "Battery storage systems paired with solar allow facilities to shift energy use away from peak-demand periods.",
    },
]

sample_texts = [d["content"] for d in sample_docs]
sample_metadatas = [
    {
        "source_id": d["source_id"],
        "title": d["title"],
        "category": "renewables",
        "approved": True,
    }
    for d in sample_docs
]

ids = vectorstore.add_texts(texts=sample_texts, metadatas=sample_metadatas)
print(f"Inserted {len(ids)} chunks with real embeddings.")
for doc, doc_id in zip(sample_docs, ids):
    print(f"  - {doc['source_id']} ({doc['title']}) -> row id {doc_id}")
print("Step 3 done. Check Neon's table view for rows with real (non-zero) vectors.")