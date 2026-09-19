# retrieval.py
"""
Agent 3 - Step 3 (IR): Category-filtered retrieval.

Takes a composed query string (from query_composition.py) and returns
vetted Document objects from the knowledge base, filtered by category.

Standard tier always queries all 3 Standard categories with the same
composed query text - see the design decision earlier in this project:
compose_query() already folds framework-relevance into the query text
itself, so a weak-fit category naturally returns weak/irrelevant results
rather than needing separate signal-checking logic here.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector

load_dotenv()

STANDARD_CATEGORIES = ["intervention", "slframework", "renewablesizing"]


def get_vectorstore():
    embeddings = GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-001",
        google_api_key=os.environ["GEMINI_API_KEY"],
        output_dimensionality=768,
    )
    return PGVector(
        embeddings=embeddings,
        collection_name="knowledge_base",
        connection=os.environ["DATABASE_URL_POOLED"],
        use_jsonb=True,
    )


def retrieve_standard(query_text: str, vectorstore, k: int = 3) -> list:
    """
    Standard tier retrieval - queries intervention, slframework, and
    renewablesizing categories, merges results.
    """
    all_docs = []
    for category in STANDARD_CATEGORIES:
        retriever = vectorstore.as_retriever(
            search_kwargs={"k": k, "filter": {"category": category}}
        )
        all_docs.extend(retriever.invoke(query_text))
    return all_docs


def retrieve_solarpunk(query_text: str, vectorstore, k: int = 3) -> list:
    """Premium tier - solarpunk innovation plan retrieval."""
    retriever = vectorstore.as_retriever(
        search_kwargs={"k": k, "filter": {"category": "solarpunk"}}
    )
    return retriever.invoke(query_text)


def retrieve_vendors(query_text: str, vectorstore, k: int = 3) -> list:
    """Premium tier - vendor category matching retrieval."""
    retriever = vectorstore.as_retriever(
        search_kwargs={"k": k, "filter": {"category": "vendor"}}
    )
    return retriever.invoke(query_text)


if __name__ == "__main__":
    # Quick manual smoke test - run this file directly to sanity check retrieval
    vs = get_vectorstore()

    print("=== Standard retrieval ===")
    docs = retrieve_standard("fuel usage spike generator maintenance", vs)
    for d in docs:
        print(f"[{d.metadata.get('category')}] {d.page_content[:70]}")

    print("\n=== Solarpunk retrieval ===")
    docs = retrieve_solarpunk("agrivoltaics project ideas", vs)
    for d in docs:
        print(f"[{d.metadata.get('category')}] {d.page_content[:70]}")

    print("\n=== Vendor retrieval ===")
    docs = retrieve_vendors("solar installation vendors", vs)
    for d in docs:
        print(f"[{d.metadata.get('category')}] {d.page_content[:70]}")