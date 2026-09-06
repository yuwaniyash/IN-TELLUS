# Agents/agent1_ingestion/classifier.py
"""
Person 3 - Step 2: label raw extracted fragments as quantity/unit/date/site-name.

Input: a list of raw text fragments Person 2 pulled off a bill.
Output: a list of {fragment, label, resolved_by, meta} dicts.

Three genuinely distinct tiers, matching the three technologies the
assignment requires as separate pieces:

  1. Rules (regex + the unit_lookup dict/fuzzy table) - fast, free,
     exact for predictable fixed-shape fields: numbers, dates, known
     unit strings.
  2. Real NLP model (spaCy NER) - catches unpredictable proper nouns
     (company/site names) that no regex can anticipate. Only run when
     the rules tier couldn't already classify the fragment.
  3. LLM fallback (stub - Person 4 wires in the real call) - genuinely
     ambiguous leftovers that even the NLP model isn't confident on.
     Never guesses; returns "unknown" rather than a wrong label.
"""

import re
from unit_lookup import lookup_unit

try:
    from dateutil import parser as dateutil_parser
except ImportError:  # pragma: no cover - dateutil is in requirements.txt
    dateutil_parser = None

try:
    import spacy
    _NLP = spacy.load("en_core_web_sm")
except (ImportError, OSError):  # pragma: no cover - see requirements.txt
    _NLP = None

DATE_PATTERN = re.compile(
    r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$"      # 12/08/2026 or 12-08-26
    r"|^\d{4}[/-]\d{1,2}[/-]\d{1,2}$"       # 2026-08-12
)

QUANTITY_PATTERN = re.compile(r"^-?\d+(\.\d+)?$")  # 245.6, 245, 0.5, -38.93

# spaCy entity labels that plausibly mean "a place or organisation name"
_SITE_ENTITY_LABELS = {"ORG", "GPE", "FAC", "LOC"}

# Domain words that spaCy sometimes tags as ORG/site names (single
# capitalized fuel-type words look like company names to a small NER
# model) but must never be accepted as a site name here. Found this the
# same way we found the "gallons"->litres unit bug: by actually running
# real values through the classifier instead of assuming it works.
_NLP_SITE_DENYLIST = {
    "diesel", "petrol", "gasoline", "lpg", "electricity", "water",
    "gas", "fuel", "kerosene",
}


def _looks_like_date(text: str) -> bool:
    """Try the fast regex first, then fall back to dateutil for the
    formats regex can't reasonably keep up with (word-months like
    "03-Jul-2026", dot-separated "23.07.2026", etc.).

    Bare numbers (e.g. "245.6", "9999.99") are never treated as dates
    here, even via the dateutil fallback - dateutil will happily
    misread a plain decimal as a day/month, which silently corrupted
    quantities into dates the first time this was tried. Those are
    left to the quantity tier below instead.
    """
    if DATE_PATTERN.match(text):
        return True
    if QUANTITY_PATTERN.match(text):
        return False
    if dateutil_parser is None:
        return False
    if not re.search(r"\d", text):
        return False
    try:
        dateutil_parser.parse(text, fuzzy=False)
        return True
    except (ValueError, OverflowError):
        return False


def _nlp_site_guess(text: str) -> dict | None:
    """Tier 2: real NLP (spaCy NER). Returns a meta dict if spaCy is
    confident this fragment is an org/place name, otherwise None.

    Bills are frequently printed in ALL CAPS ("LANKA ELECTRICITY
    COMPANY"), and spaCy's small model is noticeably weaker on
    stylized/all-caps text than on natural sentence case. Normalizing
    to title case before running NER fixes most of that gap - it's a
    known limitation of en_core_web_sm, not a bug in how it's used.
    """
    if _NLP is None or not text:
        return None

    if text.strip().lower() in _NLP_SITE_DENYLIST:
        return None

    normalized = text.title() if text.isupper() else text
    doc = _NLP(normalized)
    for ent in doc.ents:
        if ent.label_ in _SITE_ENTITY_LABELS and ent.text.strip().lower() not in _NLP_SITE_DENYLIST:
            return {"entity_text": ent.text, "entity_label": ent.label_}
    return None


def _llm_fallback_stub(text: str) -> dict:
    """Tier 3: LLM fallback - PLACEHOLDER.

    TODO (Person 4): replace this with a real call to the LLM per
    docs/api_contract.md. It should attempt to classify `text` as
    quantity/unit/date/site-name from context, and honestly return
    "unknown" rather than guessing if it can't tell.
    """
    return {"label": "unknown", "resolved_by": "llm_stub", "meta": None}


def classify_fragment(fragment: str) -> dict:
    """Classify a single raw fragment. Returns
    {fragment, label, resolved_by, meta}."""
    text = fragment.strip()

    # --- Tier 1: rules ---

    # 1a. Is it a date?
    if _looks_like_date(text):
        return {"fragment": fragment, "label": "date", "resolved_by": "rules", "meta": None}

    # 1b. Is it a known unit? (check before quantity, since "kWh" isn't numeric anyway)
    unit_result = lookup_unit(text)
    if unit_result["resolved"]:
        return {"fragment": fragment, "label": "unit", "resolved_by": "rules", "meta": unit_result}

    # 1c. Is it a plain (positive) number? -> quantity
    #     Negative numbers and non-numeric junk ("N/A", blanks) fall
    #     through instead of being accepted as valid quantities - those
    #     are data-entry errors that need to be flagged, not silently
    #     treated as real values.
    if QUANTITY_PATTERN.match(text) and not text.startswith("-"):
        return {"fragment": fragment, "label": "quantity", "resolved_by": "rules", "meta": None}

    # --- Tier 2: real NLP (spaCy NER) ---
    nlp_guess = _nlp_site_guess(text)
    if nlp_guess is not None:
        return {"fragment": fragment, "label": "site-name", "resolved_by": "nlp", "meta": nlp_guess}

    # --- Tier 3: LLM fallback (stub) ---
    llm_result = _llm_fallback_stub(text)
    return {"fragment": fragment, "label": llm_result["label"], "resolved_by": "llm_stub", "meta": None}


def classify_fragments(fragments: list[str]) -> list[dict]:
    """Classify a whole list of fragments coming from Person 2's extraction."""
    return [classify_fragment(f) for f in fragments]


# --- Step 2 self-test: run this file directly ---
if __name__ == "__main__":
    # Made-up fragments, standing in for Person 2's real regex output
    sample_fragments = [
        "245.6", "kWh", "12/08/2026", "LANKA ELECTRICITY COMPANY",
        "Colombo Branch", "Units", "9999.99", "gallons", "DIESEL",
        "03-Jul-2026", "23.07.2026", "-38.93", "N/A",
    ]

    results = classify_fragments(sample_fragments)
    for r in results:
        print(r)