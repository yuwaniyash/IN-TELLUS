"""
generation.py — reusable RAG generation for Agent 3.

generate_standard_plan() retrieves separately for EACH signal (not one
combined query), then merges and dedupes the results before generation.
This matches the original design: a single combined-vector search lets
one signal's vocabulary dominate and crowd out others (e.g. renewable
sizing crowding out a specific consumption anomaly) -- per-signal
retrieval guarantees every signal gets a chance to surface its own
relevant documents.

Changes in this version:
- Standard plans only search the Standard categories (no solarpunk/vendor leaks).
- The LLM is called once PER DOCUMENT, in parallel, instead of one big call.
- Source IDs written with square brackets by the model are cleaned up.
- Timeouts, retries and fallback models for Gemini overload (503/504).
"""

import os
import time
from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy import create_engine

from schemas import ActionPlanItem, SourceCitation, RecommendationTier

load_dotenv()

# Categories a Standard plan may draw from. Premium-only categories
# (solarpunk, vendor) are searched separately via generate_category_plan().
STANDARD_CATEGORIES = ["intervention", "slframework", "renewablesizing"]
STANDARD_FILTER = {"category": {"$in": STANDARD_CATEGORIES}}

# How many single-document LLM calls run at the same time.
# If you see 429 rate-limit errors, lower this to 2 or 3.
MAX_CONCURRENCY = 8


class LLMRecommendation(BaseModel):
    tier: RecommendationTier = Field(description="quick_win, medium_term, or transformative")
    action: str = Field(description="A specific, actionable recommendation")
    reasoning: str = Field(description="Why this action helps, grounded in the context")
    estimated_impact: str = Field(description="Expected impact, e.g. '40-60% reduction in lighting energy'")
    source_id: str = Field(description="The exact source_id this was grounded in, without square brackets")


class LLMOutput(BaseModel):
    recommendations: List[LLMRecommendation]


embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001",
    google_api_key=os.environ["GEMINI_API_KEY"],
    output_dimensionality=768,
)

engine = create_engine(
    os.environ["DATABASE_URL_POOLED"],
    pool_pre_ping=True,   # test the connection before each use; replace it if dead
    pool_recycle=300,     # never reuse a connection older than 5 minutes
    connect_args={
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    },
)

vectorstore = PGVector(
    embeddings=embeddings,
    collection_name="knowledge_base",
    connection=engine,    # pass the engine instead of the URL string
    use_jsonb=True,
    engine_args={
        "pool_pre_ping": True,   # test the connection before each use, replace it if dead
        "pool_recycle": 300,     # retire connections after 5 minutes
    },
)

llm = ChatGoogleGenerativeAI(
    model=os.environ["GEMINI_MODEL_NAME"],
    google_api_key=os.environ["GEMINI_API_KEY"],
    timeout=120,
    max_retries=1,
)

backup_1 = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.environ["GEMINI_API_KEY"],
    timeout=120,
    max_retries=1,
)
backup_2 = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    google_api_key=os.environ["GEMINI_API_KEY"],
    timeout=120,
    max_retries=1,
)

structured_llm = llm.with_structured_output(LLMOutput).with_fallbacks(
    [
        backup_1.with_structured_output(LLMOutput),
        backup_2.with_structured_output(LLMOutput),
    ]
)

PROMPT = ChatPromptTemplate.from_template(
    """You are a carbon-reduction advisor generating a tiered action plan
(quick_win / medium_term / transformative). Use ONLY the context below --
do not invent facts, interventions, or figures not present in it.

Context (each item tagged with its source_id in brackets):
{context}

Query: {query}

Generate exactly one recommendation PER context item provided -- do not
merge content from multiple context items into a single recommendation.
Each recommendation's source_id must match the ONE context item its action,
reasoning, and estimated_impact are actually drawn from.

For each recommendation, include: tier, action, reasoning, estimated_impact,
and the exact source_id it was grounded in. Write the source_id WITHOUT the
square brackets.

Every action must be a concrete step the company can take. If a context
item is a reference or definition (for example a government framework or
standard), do not restate it. Write the action as what the company should
do to align with it, such as "Align your reporting with ...".

Write each field with real substance:
- action: 2-3 sentences describing exactly what to do, including any
  specifics (equipment, frequency, thresholds) mentioned in the context.
- reasoning: explain WHY this works and what mechanism drives the benefit,
  not just that it "helps."
- estimated_impact: if the context gives a number, state it plainly (e.g.
  "40-60% reduction"). If no number is given, say "not quantified in the
  source material" rather than explaining around it.

Do not pad with generic sustainability language not grounded in the context --
depth should come from what's actually in the retrieved documents, not from
elaboration outside them."""
)

chain = PROMPT | structured_llm

VENDOR_PROMPT = ChatPromptTemplate.from_template(
    """You are helping a company find the right TYPE of service provider for
the actions in its carbon-reduction plan. Use ONLY the context below.

Context (each item tagged with its source_id in brackets):
{context}

Query: {query}

Generate exactly one item PER context item. For each:
- action: 2-3 sentences on what this provider category does and what to
  look for when choosing one, using the context's selection criteria. If the
  context lists example provider names, include them exactly as written and
  say they are fictional examples, not real businesses. Never present any
  name as a real or recommended business.
- reasoning: why this provider category fits the query.
- tier: always quick_win.
- estimated_impact: always "not applicable".
- source_id: the exact source_id of that context item, written WITHOUT the
  square brackets."""
)

vendor_chain = VENDOR_PROMPT | structured_llm


def _retrieve_per_signal(signals: List[str], k_per_signal: int) -> dict:
    merged: dict[str, tuple] = {}

    for signal in signals:
        results = vectorstore.similarity_search_with_score(
            signal,
            k=k_per_signal,
            filter=STANDARD_FILTER,
        )
        for doc, distance in results:
            source_id = doc.metadata["source_id"]
            relevance_score = round(1 - (distance / 2), 2)

            if source_id not in merged or relevance_score > merged[source_id][1]:
                merged[source_id] = (doc, relevance_score)

    return merged


def _run_chain_per_doc(selected_chain, docs: list, query_for_prompt: str) -> LLMOutput:
    """
    Calls the LLM once per document, in parallel, and merges the results.
    Each call stays small (a few seconds), so the total wait is roughly the
    slowest single call instead of the sum of all of them. If some calls fail
    the rest still succeed; only if ALL fail do we raise.
    """
    inputs = [
        {"context": f"[{d.metadata['source_id']}] {d.page_content}", "query": query_for_prompt}
        for d in docs
    ]

    results = selected_chain.batch(
        inputs,
        config={"max_concurrency": MAX_CONCURRENCY},
        return_exceptions=True,
    )

    recommendations = []
    errors = []
    for r in results:
        if isinstance(r, Exception):
            print(f"WARNING: one recommendation call failed: {r}")
            errors.append(r)
            continue
        recommendations.extend(r.recommendations)

    if not recommendations:
        # Include the first error text so app.py can recognise 503/504 and
        # show the friendly "AI service is busy" message.
        first = errors[0] if errors else "no documents to generate from"
        raise RuntimeError(f"All recommendation calls failed: {first}")

    return LLMOutput(recommendations=recommendations)


def _build_action_plan(
    llm_result: LLMOutput,
    doc_by_source_id: dict,
) -> list[ActionPlanItem]:
    items = []
    for rec in llm_result.recommendations:
        # The model sometimes copies the brackets from the prompt, e.g.
        # "[intervention_19_...]". Strip them before looking the ID up.
        clean_id = rec.source_id.strip().strip("[]").strip()
        entry = doc_by_source_id.get(clean_id)
        if entry is None:
            print(f"WARNING: dropping recommendation citing unretrieved source_id '{rec.source_id}'")
            continue

        doc, relevance_score = entry
        items.append(
            ActionPlanItem(
                tier=rec.tier,
                action=rec.action,
                reasoning=rec.reasoning,
                estimated_impact=rec.estimated_impact,
                source=SourceCitation(
                    doc_id=doc.metadata["source_id"],
                    title=doc.metadata.get("title", "Untitled"),
                    relevance_score=relevance_score,
                ),
            )
        )
    return items


def generate_standard_plan(
    signals: List[str] | None = None,
    fallback_query: str | None = None,
    k_per_signal: int = 2,
    k_fallback: int = 3,
) -> list[ActionPlanItem]:
    t0 = time.perf_counter()
    if signals:
        doc_by_source_id = _retrieve_per_signal(signals, k_per_signal)
        query_for_prompt = "; ".join(signals)
    else:
        results = vectorstore.similarity_search_with_score(
            fallback_query,
            k=k_fallback,
            filter=STANDARD_FILTER,
        )
        doc_by_source_id = {
            doc.metadata["source_id"]: (doc, round(1 - (distance / 2), 2))
            for doc, distance in results
        }
        query_for_prompt = fallback_query

    docs = [doc for doc, _ in doc_by_source_id.values()]

    t1 = time.perf_counter()
    llm_result = _run_chain_per_doc(chain, docs, query_for_prompt)
    print(f"[timing] LLM calls (parallel): {time.perf_counter() - t1:.1f}s, {len(docs)} docs")

    return _build_action_plan(llm_result, doc_by_source_id)


def generate_category_plan(
    signals: List[str],
    category: str,
    k_per_signal: int = 3,
) -> list[ActionPlanItem]:
    """
    Same per-signal retrieval + merge + generate pattern as
    generate_standard_plan, but restricted to a single KB category via
    a metadata filter. Used for Premium's solarpunk plan (category=
    'solarpunk') and vendor matching (category='vendor').
    """
    merged: dict[str, tuple] = {}

    for signal in signals:
        results = vectorstore.similarity_search_with_score(
            signal,
            k=k_per_signal,
            filter={"category": category},
        )
        for doc, distance in results:
            source_id = doc.metadata["source_id"]
            relevance_score = round(1 - (distance / 2), 2)
            if source_id not in merged or relevance_score > merged[source_id][1]:
                merged[source_id] = (doc, relevance_score)

    if not merged:
        return []

    docs = [doc for doc, _ in merged.values()]
    query_for_prompt = "; ".join(signals)

    selected_chain = vendor_chain if category == "vendor" else chain
    llm_result = _run_chain_per_doc(selected_chain, docs, query_for_prompt)

    return _build_action_plan(llm_result, merged)