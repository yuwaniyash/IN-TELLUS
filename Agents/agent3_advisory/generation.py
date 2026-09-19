"""
generation.py — reusable RAG generation for Agent 3.

Exposes generate_standard_plan(query) -> list[ActionPlanItem], the function
orchestration.py will call for Standard tier, and again (with a different
query/category) for Premium's solarpunk plan and vendor matching.
"""

import os
from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector
from langchain_core.prompts import ChatPromptTemplate

# Adjust this import path to wherever schema.py actually lives relative to this file.
from schema import ActionPlanItem, SourceCitation, RecommendationTier

load_dotenv()


# The LLM outputs this simpler shape -- it can name WHICH source it used,
# but it can't honestly know a title or a relevance_score, so we don't ask
# it for those. We fill those in ourselves from retrieval.
class LLMRecommendation(BaseModel):
    tier: RecommendationTier = Field(description="quick_win, medium_term, or transformative")
    action: str = Field(description="A specific, actionable recommendation")
    reasoning: str = Field(description="Why this action helps, grounded in the context")
    estimated_impact: str = Field(description="Expected impact, e.g. '40-60% reduction in lighting energy'")
    source_id: str = Field(description="The exact source_id (in brackets) this was grounded in")


class LLMOutput(BaseModel):
    recommendations: List[LLMRecommendation]


# --- Set up once at import time, reused across calls ---

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


def _build_action_plan(
    llm_result: LLMOutput,
    retrieved_docs,
    scores_by_source_id: dict[str, float],
) -> list[ActionPlanItem]:
    """
    Maps the LLM's simpler output onto the real ActionPlanItem/SourceCitation
    schema, filling in title and relevance_score from retrieval -- not
    trusting the LLM to self-report either. Drops any recommendation citing
    a source_id that wasn't actually retrieved (hallucination guard).
    """
    by_source_id = {d.metadata["source_id"]: d for d in retrieved_docs}

    items = []
    for rec in llm_result.recommendations:
        doc = by_source_id.get(rec.source_id)
        if doc is None:
            print(f"WARNING: dropping recommendation citing unretrieved source_id '{rec.source_id}'")
            continue

        items.append(
            ActionPlanItem(
                tier=rec.tier,
                action=rec.action,
                reasoning=rec.reasoning,
                estimated_impact=rec.estimated_impact,
                source=SourceCitation(
                    doc_id=doc.metadata["source_id"],
                    title=doc.metadata.get("title", "Untitled"),
                    relevance_score=scores_by_source_id[doc.metadata["source_id"]],
                ),
            )
        )
    return items


def generate_standard_plan(query: str, k: int = 3) -> list[ActionPlanItem]:
    """
    The main reusable entry point. Given a composed query string, retrieves
    relevant KB chunks, generates recommendations grounded in them, and
    returns a validated list of ActionPlanItem -- ready to drop into
    Agent3Output.action_plan.

    Also usable for Premium's solarpunk/vendor generation by passing a
    query built with different signals (e.g. category-specific phrasing) --
    same function, different input.
    """
    results = vectorstore.similarity_search_with_score(query, k=k)

    # pgvector cosine distance: 0 = identical, 2 = completely opposite.
    # Convert to a 0-1 relevance score where 1.0 = most relevant.
    docs = [doc for doc, _ in results]
    scores_by_source_id = {
        doc.metadata["source_id"]: round(1 - (distance / 2), 2)
        for doc, distance in results
    }

    context = "\n".join(f"[{d.metadata['source_id']}] {d.page_content}" for d in docs)

    llm_result: LLMOutput = chain.invoke({"context": context, "query": query})

    return _build_action_plan(llm_result, docs, scores_by_source_id)