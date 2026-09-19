import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Agents.agent3_advisory.retrieval import (
    get_vectorstore,
    retrieve_standard,
    retrieve_solarpunk,
    retrieve_vendors,
)
from Agents.agent3_advisory.security_validation import vet_sources


def test_standard_retrieval_returns_docs():
    vs = get_vectorstore()
    docs = retrieve_standard("fuel usage spike generator maintenance", vs)
    assert len(docs) > 0


def test_standard_retrieval_only_returns_standard_categories():
    vs = get_vectorstore()
    docs = retrieve_standard("energy efficiency", vs)
    allowed = {"intervention", "slframework", "renewablesizing"}
    assert all(d.metadata.get("category") in allowed for d in docs)


def test_solarpunk_retrieval_only_returns_solarpunk_category():
    vs = get_vectorstore()
    docs = retrieve_solarpunk("agrivoltaics project ideas", vs)
    assert len(docs) > 0
    assert all(d.metadata.get("category") == "solarpunk" for d in docs)


def test_vendor_retrieval_only_returns_vendor_category():
    vs = get_vectorstore()
    docs = retrieve_vendors("solar installation vendors", vs)
    assert len(docs) > 0
    assert all(d.metadata.get("category") == "vendor" for d in docs)


def test_vet_sources_keeps_approved_docs():
    vs = get_vectorstore()
    docs = retrieve_standard("solar sizing", vs)
    vetted = vet_sources(docs)
    assert len(vetted) == len(docs)
    assert all(d.metadata.get("approved") is True for d in vetted)


def test_ngrs_documents_carry_official_provenance():
    vs = get_vectorstore()
    docs = retrieve_standard("Sri Lanka NGRS energy reporting", vs)
    ngrs_docs = [d for d in docs if d.metadata.get("category") == "slframework"]
    assert len(ngrs_docs) > 0
    # Every slframework doc must trace back to an official Sri Lankan source —
    # either directly (source_type == official_guideline, for the primary
    # NGRS documents) or as a summary of one (source_basis == official_guideline,
    # for the supplementary summary documents added later).
    assert all(
        d.metadata.get("source_type") == "official_guideline"
        or d.metadata.get("source_basis") == "official_guideline"
        for d in ngrs_docs
    )
    # Every slframework doc must name a real authority — the specific
    # authority varies by document (Ministry of Environment for NGRS,
    # SLSEA for the building code/rooftop solar/labelling docs, etc.),
    # so we check presence rather than a single fixed value.
    assert all(d.metadata.get("authority") for d in ngrs_docs)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))