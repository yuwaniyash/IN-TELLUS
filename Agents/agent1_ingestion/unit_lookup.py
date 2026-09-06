# Agents/agent1_ingestion/unit_lookup.py
"""
Person 3 - Step 1: Unit/format reference table + lookup function.

Goal: given a raw unit string pulled off a bill (e.g. "units", "Kw", "cu m"),
resolve it to one canonical unit so Agent 2's math is consistent.

Start with FAKE placeholder entries. Do not research real CEB/LECO formats yet -
that's Step 3, and it can happen later without blocking anyone.
"""

# --- The reference table ---
# key = raw unit text (lowercased), value = canonical unit + conversion multiplier
utility_format_reference = {
    "kwh":            {"canonical_unit": "kWh", "multiplier": 1.0},
    "units":          {"canonical_unit": "kWh", "multiplier": 1.0},   # CEB bills sometimes say "units"
    "kw":             {"canonical_unit": "kWh", "multiplier": 1.0},   # placeholder - refine in Step 3
    "kilowatt-hours": {"canonical_unit": "kWh", "multiplier": 1.0},   # alternate spelling
    "kilowatt hours": {"canonical_unit": "kWh", "multiplier": 1.0},   # alternate spelling (no hyphen)
    "cu m":           {"canonical_unit": "m3",  "multiplier": 1.0},   # water
    "m3":             {"canonical_unit": "m3",  "multiplier": 1.0},
    "litres":         {"canonical_unit": "L",   "multiplier": 1.0},   # fuel
    "liters":         {"canonical_unit": "L",   "multiplier": 1.0},   # US spelling
    "l":              {"canonical_unit": "L",   "multiplier": 1.0},
    "gallons":        {"canonical_unit": "L",   "multiplier": 3.78541},  # US gallon -> litres
    "gallon":         {"canonical_unit": "L",   "multiplier": 3.78541},
    "gal":            {"canonical_unit": "L",   "multiplier": 3.78541},
}

# Keys shorter than this are only ever matched exactly, never fuzzily.
# Fuzzy matching against a 1-2 character key (e.g. "l") is unreliable -
# almost any short string scores "close enough", which is how "gallons"
# was silently getting matched to "l" (litres, multiplier 1.0) and
# "DIESEL" (a fuel type, not a unit at all) was matching too.
_MIN_FUZZY_KEY_LENGTH = 3


def lookup_unit(raw_unit: str, fuzzy: bool = True, fuzzy_threshold: int = 85) -> dict:
    """
    Resolve a raw unit string to its canonical unit + multiplier.

    Tries an exact match first. If that fails and fuzzy=True, tries a
    fuzzy (typo-tolerant) match against the known keys before giving up.
    This is a middle tier: catches near-misses like "Kilowat-hours"
    (missing a 't') without needing to fall all the way to an LLM call.

    Short reference keys (e.g. "l") are excluded from fuzzy matching -
    see _MIN_FUZZY_KEY_LENGTH above.

    Returns a dict with 'resolved': True/False so callers can handle
    unknown units gracefully instead of crashing.
    """
    if not raw_unit or not isinstance(raw_unit, str):
        return {"canonical_unit": None, "multiplier": None, "resolved": False, "match_type": None}

    key = raw_unit.strip().lower()

    # 1. Exact match
    entry = utility_format_reference.get(key)
    if entry is not None:
        return {**entry, "resolved": True, "match_type": "exact"}

    # 2. Fuzzy match (typo-tolerant), only if enabled - and only against
    #    keys long enough that a fuzzy score actually means something.
    if fuzzy:
        from thefuzz import process
        fuzzy_candidates = [
            k for k in utility_format_reference.keys()
            if len(k) >= _MIN_FUZZY_KEY_LENGTH
        ]
        if fuzzy_candidates:
            candidate, score = process.extractOne(key, fuzzy_candidates)
            if score >= fuzzy_threshold:
                entry = utility_format_reference[candidate]
                return {**entry, "resolved": True, "match_type": f"fuzzy:{candidate}({score})"}

    # 3. Nothing matched - safe failure, hand off to LLM fallback (Person 4)
    return {"canonical_unit": None, "multiplier": None, "resolved": False, "match_type": None}


# --- Step 1 self-test: run this file directly to prove it works ---
if __name__ == "__main__":
    test_cases = ["kWh", "Units", "  cu m  ", "gibberish", "", None]

    for raw in test_cases:
        result = lookup_unit(raw)
        print(f"lookup_unit({raw!r}) -> {result}")