"""
generation.py — reusable RAG generation for Agent 3.

generate_standard_plan() retrieves separately for EACH signal (not one
combined query), then merges and dedupes the results before generation.
This matches the original design: a single combined-vector search lets
one signal's vocabulary dominate and crowd out others (e.g. renewable
sizing crowding out a specific consumption anomaly) -- per-signal
retrieval guarantees every signal gets a chance to surface its own
relevant documents.
"""

import os
from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector
from langchain_core.prompts import ChatPromptTemplate

from schemas import ActionPlanItem, SourceCitation, RecommendationTier

load_dotenv()


class LLMRecommendation(BaseModel):
    tier: RecommendationTier = Field(description="quick_win, medium_term, or transformative")
    action: str = Field(description="A specific, actionable recommendation")
    reasoning: str = Field(description="Why this action helps, grounded in the context")
    estimated_impact: str = Field(description="Expected impact, e.g. '40-60% reduction in lighting energy'")
    source_id: str = Field(description="The exact source_id (in brackets) this was grounded in")


class LLMOutput(BaseModel):
    recommendations: List[LLMRecommendation]


embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001",
    google_api_key=os.environ["GEMINI_API_KEY"],
    output_dimensionality=768,
)

vectorstore = PGVector(
    embeddings=embeddings,
    collection_name="knowledge_base",
    connection=os.environ["DATABASE_URL_POOLED"],
    use_jsonb=True,
)

llm = ChatGoogleGenerativeAI(
    model=os.environ["GEMINI_MODEL_NAME"],
    google_api_key=os.environ["GEMINI_API_KEY"],
)
structured_llm = llm.with_structured_output(LLMOutput)

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
and the exact source_id (from the brackets) it was grounded in.

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
- source_id: the exact source_id (from the brackets) of that context item."""
)

vendor_chain = VENDOR_PROMPT | structured_llm


def _retrieve_per_signal(signals: List[str], k_per_signal: int) -> dict:
    merged: dict[str, tuple] = {}

    for signal in signals:
        results = vectorstore.similarity_search_with_score(signal, k=k_per_signal)
        for doc, distance in results:
            source_id = doc.metadata["source_id"]
            relevance_score = round(1 - (distance / 2), 2)

            if source_id not in merged or relevance_score > merged[source_id][1]:
                merged[source_id] = (doc, relevance_score)

    return merged


def _build_action_plan(
    llm_result: LLMOutput,
    doc_by_source_id: dict,
) -> list[ActionPlanItem]:
    items = []
    for rec in llm_result.recommendations:
        entry = doc_by_source_id.get(rec.source_id)
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
    if signals:
        doc_by_source_id = _retrieve_per_signal(signals, k_per_signal)
        query_for_prompt = "; ".join(signals)
    else:
        results = vectorstore.similarity_search_with_score(fallback_query, k=k_fallback)
        doc_by_source_id = {
            doc.metadata["source_id"]: (doc, round(1 - (distance / 2), 2))
            for doc, distance in results
        }
        query_for_prompt = fallback_query

    docs = [doc for doc, _ in doc_by_source_id.values()]
    context = "\n".join(f"[{d.metadata['source_id']}] {d.page_content}" for d in docs)

    llm_result: LLMOutput = chain.invoke({"context": context, "query": query_for_prompt})

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
    'solarpunk') and, later, vendor matching (category='vendor').
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
    context = "\n".join(f"[{d.metadata['source_id']}] {d.page_content}" for d in docs)
    query_for_prompt = "; ".join(signals)

    selected_chain = vendor_chain if category == "vendor" else chain
    llm_result: LLMOutput = selected_chain.invoke({"context": context, "query": query_for_prompt})

    return _build_action_plan(llm_result, merged)