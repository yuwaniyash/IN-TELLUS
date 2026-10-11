import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

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

prompt = ChatPromptTemplate.from_template(
    """You are a carbon-reduction advisor. Using ONLY the context below,
suggest one practical action for the facility described in the query.
If the context doesn't contain a relevant action, say so plainly.

Context:
{context}

Query: {query}

Answer:"""
)

query = "we have high electricity costs from an old office building"
docs = retriever.invoke(query)
context = "\n".join(d.page_content for d in docs)

chain = prompt | llm
response = chain.invoke({"context": context, "query": query})

print("Retrieved context:\n", context, "\n")
print("LLM answer:\n", response.content)
print("\nStep 5 done. Confirm the answer is actually grounded in the context above.")