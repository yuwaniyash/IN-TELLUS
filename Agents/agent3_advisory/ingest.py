import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector

load_dotenv()

CONNECTION_STRING = os.environ["DATABASE_URL_POOLED"]
COLLECTION_NAME = "knowledge_base"
DOCS_FOLDER = Path(__file__).resolve().parent / "knowledge_base_docs"

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
    pre_delete_collection=True,
)

splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)

SOURCE_OVERRIDES = {
    "slframework_01_energy_indicators": {
        "authority": "Ministry of Environment, Sri Lanka",
        "document_type": "official_guideline",
        "document_title": "National Green Reporting System (NGRS) - Revised Reporting Guidelines",
        "year": 2026,
        "source_type": "official_guideline",
    },
    "slframework_02_ghg_emissions": {
        "authority": "Ministry of Environment, Sri Lanka",
        "document_type": "official_guideline",
        "document_title": "National Green Reporting System (NGRS) - Revised Reporting Guidelines",
        "year": 2026,
        "source_type": "official_guideline",
    },
    "slframework_03_ngrs_overview": {
        "authority": "Ministry of Environment, Sri Lanka",
        "document_type": "supplementary_summary",
        "document_title": "National Green Reporting System (NGRS) - Revised Reporting Guidelines",
        "year": 2026,
        "source_type": "supplementary",
        "source_basis": "official_guideline",
    },
    "slframework_04_ngrs_data_and_reporting": {
        "authority": "Ministry of Environment, Sri Lanka",
        "document_type": "supplementary_summary",
        "document_title": "National Green Reporting System (NGRS) - Revised Reporting Guidelines",
        "year": 2026,
        "source_type": "supplementary",
        "source_basis": "official_guideline",
    },
    "slframework_05_national_energy_policy": {
        "authority": "Government of Sri Lanka",
        "document_type": "supplementary_summary",
        "document_title": "National Energy Policy and Strategies",
        "year": 2019,
        "source_type": "supplementary",
        "source_basis": "official_policy",
    },
    "slframework_06_energy_efficiency_building_code": {
        "authority": "Sri Lanka Sustainable Energy Authority",
        "document_type": "supplementary_summary",
        "document_title": "Energy Efficiency Building Code of Sri Lanka",
        "year": 2021,
        "source_type": "supplementary",
        "source_basis": "official_code",
    },
    "slframework_07_rooftop_solar_requirements": {
        "authority": "Sri Lanka Sustainable Energy Authority",
        "document_type": "supplementary_summary",
        "document_title": "Rooftop Solar PV Programme and Guidelines",
        "source_type": "supplementary",
        "source_basis": "official_guideline",
    },
    "slframework_08_energy_labelling_and_standards": {
        "authority": "Sri Lanka Sustainable Energy Authority",
        "document_type": "supplementary_summary",
        "document_title": "Energy Performance Standards and Energy Labelling Programme",
        "source_type": "supplementary",
        "source_basis": "official_guidance",
    },
}


def category_from_filename(filename: str) -> str:
    return filename.split("_")[0]


def title_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    parts = stem.split("_")[2:]
    return " ".join(p.capitalize() for p in parts) or stem


def main():
    total_chunks = 0
    files = sorted(DOCS_FOLDER.glob("*.txt"))

    if not files:
        print(f"No .txt files found in {DOCS_FOLDER} - check the folder exists and has files in it.")
        return

    for file_path in files:
        text = file_path.read_text(encoding="utf-8")
        category = category_from_filename(file_path.name)
        title = title_from_filename(file_path.name)
        source_id = file_path.stem

        chunks = splitter.split_text(text)

        base_metadata = {
            "source_id": source_id,
            "title": title,
            "category": category,
            "approved": True,
            "document_type": "handwritten",
            "source_type": "supplementary",
        }

        if source_id in SOURCE_OVERRIDES:
            base_metadata.update(SOURCE_OVERRIDES[source_id])

        vectorstore.add_texts(
            texts=chunks,
            metadatas=[base_metadata for _ in chunks],
        )

        total_chunks += len(chunks)
        print(f"Ingested {file_path.name}: {len(chunks)} chunks (category: {category})")

    print(f"\nDone. {total_chunks} total chunks inserted across {len(files)} documents.")


if __name__ == "__main__":
    main()