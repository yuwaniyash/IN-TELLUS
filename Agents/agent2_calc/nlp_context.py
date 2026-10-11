"""
Agents/agent2_calc/nlp_context.py
====================================
NLP processing of free-text for Agent 2 (the "N" in the LLM/NLP/IR/
Security/Agent-Communication requirement set).

Extracts named entities (ORG, GPE, FAC, DATE, PRODUCT) from any
free-text attached to a record or file (e.g. OCR'd margin notes, a site
description), and flags a small set of keywords that commonly explain
consumption anomalies (new equipment, renovation, generator use, etc.)
so Person 4's LLM narrative has something concrete to cite rather than
guessing a cause purely from the numbers.

Note: as of this build, neither ExtractionRecord nor the DB schema
carries a free-text notes field — Agent 1's `raw_text` (the full
OCR/PDF text) is extracted but currently discarded after building
records. This module is ready the moment either (a) raw_text is threaded
through to Agent 2, or (b) a manual "notes" field is added anywhere in
the pipeline. Until then, `process_free_text(None)` returns an empty
result rather than blocking anything.

Falls back to a keyword-only pass (no entity extraction) if spaCy or its
English model isn't installed, so a missing model download never
crashes the pipeline — it just degrades gracefully with a flag.
"""

from __future__ import annotations

_ANOMALY_EXPLANATION_KEYWORDS = {
    "new equipment": "possible new equipment installation",
    "renovation": "possible renovation/construction activity",
    "expansion": "possible facility expansion",
    "generator": "possible backup generator use (e.g. during an outage)",
    "outage": "possible grid outage requiring backup power",
    "new machinery": "possible new machinery installation",
    "increased production": "possible increased production/operating hours",
    "shutdown": "possible planned shutdown or reduced operations",
    "holiday": "possible holiday-period reduced operations",
    "leak": "possible water/fuel leak",
    "meter fault": "possible meter malfunction — verify reading before trusting this anomaly",
    "estimated reading": "reading was estimated, not actual — verify before trusting this anomaly",
}

_nlp = None
_SPACY_AVAILABLE = False

try:
    import spacy
    try:
        _nlp = spacy.load("en_core_web_sm")
        _SPACY_AVAILABLE = True
    except OSError:
        _nlp = None
        _SPACY_AVAILABLE = False
except ImportError:
    _SPACY_AVAILABLE = False


def extract_keyword_flags(text) -> list:
    """Keyword-only pass — always available, no spaCy dependency."""
    if not text:
        return []
    lowered = text.lower()
    return [
        explanation for keyword, explanation in _ANOMALY_EXPLANATION_KEYWORDS.items()
        if keyword in lowered
    ]


def extract_entities(text) -> list:
    """
    Named-entity extraction via spaCy, if available. Returns [] (not an
    error) if spaCy/the model isn't installed — this is a nice-to-have
    enrichment, not something that should block the pipeline.
    """
    if not text or not _SPACY_AVAILABLE:
        return []
    doc = _nlp(text)
    return [
        {"text": ent.text, "label": ent.label_}
        for ent in doc.ents
        if ent.label_ in ("ORG", "GPE", "FAC", "DATE", "PRODUCT")
    ]


def process_free_text(text) -> dict:
    """
    Single entry point the assembly step calls for any free-text
    attached to a record/file. Combines keyword flags (always available)
    with entity extraction (best-effort). Safe to call with None/"".
    """
    return {
        "source_text": text,
        "keyword_flags": extract_keyword_flags(text),
        "entities": extract_entities(text),
        "spacy_available": _SPACY_AVAILABLE,
    }
