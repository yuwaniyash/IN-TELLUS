import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector

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

query = "how can we reduce electricity-related emissions"
results = retriever.invoke(query)

print(f"Query: {query!r}\nGot {len(results)} results:\n")
for i, doc in enumerate(results, 1):
    print(f"[{i}] {doc.page_content}")
    print(f"    metadata: {doc.metadata}\n")

print("Step 4 done. Confirm these results are actually relevant to the query.")