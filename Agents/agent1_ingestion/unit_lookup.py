"""
unit_lookup.py
Person 3 -- IR (Information Retrieval) component of Agent 1.

Resolves unit terms found on real utility bills to a canonical unit,
handling exact matches, typos (fuzzy match), and unit conversions
(e.g. US gallons -> litres) via a per-alias multiplier.

Exposes: lookup_unit(raw_unit) -> dict with keys:
    resolved       bool
    canonical_unit str | None
    match_type     "exact" | "fuzzy:<score>" | None
    multiplier     float | None  (multiply the raw value by this to get
                                   the value in canonical_unit)

Design notes / bugs this guards against (found against the team's real
fuel_consumption CSV):
- "gallons" was previously fuzzy-matching the single-character key "l"
  (litres) with an implicit 1.0 multiplier, silently treating US gallons
  as litres. Fixed by making "gallons" its own EXACT alias that maps to
  canonical unit "L" with the real US-gallon-to-litre multiplier
  (3.78541), so it never needs to go through fuzzy matching at all.
- "DIESEL" (a fuel type, not a unit) was fuzzy-matching short keys like
  "l" for the same reason. Fixed two ways: (1) fuzzy matching only
  considers alias candidates of length >= 4, so a 1-character key like
  "l" can never be a fuzzy target: (2) known non-unit words are checked
  and rejected before any matching is attempted at all.
- "m³" (the Unicode superscript pdfplumber extracts from a real PDF bill)
  was silently failing to resolve -- the table only had plain ASCII "m3",
  and "m³" is too short to reach fuzzy matching anyway. Fixed by
  normalizing Unicode superscript digits to ASCII before any matching.

Site-name resolution used to live in this file too -- it's now in
site_lookup.py, since it's a separate lookup (different table, different
matching rules) that only shared this file by coincidence.
"""

from thefuzz import fuzz

# PDF text extraction (e.g. pdfplumber) commonly yields Unicode superscript
# digits for things like "m³" rather than the plain ASCII "m3" our table
# uses. Normalize these BEFORE any matching, so a real bill's "m³" resolves
# exactly like "m3" instead of silently failing (too short for fuzzy match
# too, since superscript "³" alone is only 1-2 chars).
_SUPERSCRIPT_MAP = str.maketrans({
    "\u00b9": "1", "\u00b2": "2", "\u00b3": "3",
    "\u2074": "4", "\u2075": "5", "\u2076": "6",
    "\u2077": "7", "\u2078": "8", "\u2079": "9", "\u2070": "0",
})

# ---------------------------------------------------------------------------
# Known non-unit words that must never resolve, no matter how similar they
# look to a real unit -- these are fuel/resource TYPES, not units.
# ---------------------------------------------------------------------------
NON_UNIT_WORDS = {
    "diesel", "petrol", "electricity", "fuel", "water", "gas",
}

# ---------------------------------------------------------------------------
# alias (lowercase, normalized) -> (canonical_unit, multiplier)
# multiplier converts a value expressed in this alias into canonical_unit.
# ---------------------------------------------------------------------------
UNIT_TABLE = {
    # --- kWh ---
    "kwh": ("kWh", 1.0),
    "units": ("kWh", 1.0),
    "unit": ("kWh", 1.0),
    "kw-h": ("kWh", 1.0),
    "kilowatt-hour": ("kWh", 1.0),
    "kilowatt-hours": ("kWh", 1.0),
    "kilowatthour": ("kWh", 1.0),
    "kilowatthours": ("kWh", 1.0),

    # --- Litres (L) ---
    "l": ("L", 1.0),
    "liter": ("L", 1.0),
    "liters": ("L", 1.0),
    "litre": ("L", 1.0),
    "litres": ("L", 1.0),
    "ltr": ("L", 1.0),
    "ltrs": ("L", 1.0),

    # --- Gallons -> Litres (real US gallon conversion, not 1:1) ---
    "gallon": ("L", 3.78541),
    "gallons": ("L", 3.78541),
    "gal": ("L", 3.78541),

    # --- Cubic metres (m3) ---
    "m3": ("m3", 1.0),
    "cum": ("m3", 1.0),
    "cu.m": ("m3", 1.0),
    "cubic meter": ("m3", 1.0),
    "cubic meters": ("m3", 1.0),
}

# Fuzzy matching only ever considers aliases at least this long, so short
# keys (like "l") can never accidentally absorb an unrelated word via a
# lucky-looking edit distance.
_MIN_FUZZY_ALIAS_LEN = 4
_FUZZY_THRESHOLD = 85


def _empty_result():
    return {"resolved": False, "canonical_unit": None, "match_type": None, "multiplier": None}


def lookup_unit(raw_unit) -> dict:
    if raw_unit is None:
        return _empty_result()

    key = str(raw_unit).strip().lower().translate(_SUPERSCRIPT_MAP)
    if not key:
        return _empty_result()

    if key in NON_UNIT_WORDS:
        return _empty_result()

    # Tier 1: exact match
    if key in UNIT_TABLE:
        canonical_unit, multiplier = UNIT_TABLE[key]
        return {
            "resolved": True,
            "canonical_unit": canonical_unit,
            "match_type": "exact",
            "multiplier": multiplier,
        }

    # Tier 2: fuzzy match, restricted to longer aliases only
    best_alias, best_score = None, 0
    for alias in UNIT_TABLE:
        if len(alias) < _MIN_FUZZY_ALIAS_LEN:
            continue
        score = fuzz.ratio(key, alias)
        if score > best_score:
            best_alias, best_score = alias, score

    if best_alias is not None and best_score >= _FUZZY_THRESHOLD:
        canonical_unit, multiplier = UNIT_TABLE[best_alias]
        return {
            "resolved": True,
            "canonical_unit": canonical_unit,
            "match_type": f"fuzzy:{best_score}",
            "multiplier": multiplier,
        }

    return _empty_result()