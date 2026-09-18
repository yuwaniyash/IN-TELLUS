import os
from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()


class Recommendation(BaseModel):
    action: str = Field(description="A specific, actionable recommendation")
    rationale: str = Field(description="Why this action helps, grounded in the context")
    source_ids: List[int] = Field(description="IDs of the KB chunks this recommendation is based on")


class Agent3Output(BaseModel):
    recommendations: List[Recommendation]
    summary: str = Field(description="One-sentence summary of the overall advice")


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

retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    google_api_key=os.environ["GEMINI_API_KEY"],
)
structured_llm = llm.with_structured_output(Agent3Output)

prompt = ChatPromptTemplate.from_template(
    """You are a carbon-reduction advisor. Using ONLY the context below,
produce 1-3 recommendations. Each must cite which numbered context item(s) it's based on.

Context (numbered):
{context}

Query: {query}"""
)

query = "we have high electricity costs from an old office building"
docs = retriever.invoke(query)
numbered_context = "\n".join(f"[{i+1}] {d.page_content}" for i, d in enumerate(docs))

chain = prompt | structured_llm
result: Agent3Output = chain.invoke({"context": numbered_context, "query": query})

print("Structured output:\n")
print(result.model_dump_json(indent=2))
print("\nStep 6 done. Confirm this matches the Agent3Output shape you need.")