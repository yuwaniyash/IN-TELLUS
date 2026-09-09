# Agent 1 Internal API Contract

This documents the interfaces between Person 3's (NLP/IR) code and
Person 4's (LLM fallback + integration) code, so Person 4 can wire in
a real LLM call without guessing the shapes involved.

## `classify_fragment(fragment: str) -> dict`

Classifies a single raw text fragment pulled off a bill by Person 2's
extraction step. Returns:

```json
{
  "fragment": "<the original input string>",
  "label": "quantity" | "unit" | "date" | "site-name" | "unknown",
  "resolved_by": "rules" | "nlp" | "llm_stub",
  "meta": null | { ... tier-specific detail, see below }
}
```

- `resolved_by: "rules"` — matched by regex or the `unit_lookup` table.
  `meta` is `null` for quantity/date; for `unit` it's the full
  `lookup_unit()` result (see below).
- `resolved_by: "nlp"` — matched by spaCy NER as a site/org name.
  `meta` is `{"entity_text": str, "entity_label": str}`.
- `resolved_by: "llm_stub"` — fell through to the LLM tier. **This is
  the tier Person 4 replaces.** `label` is currently always
  `"unknown"` here — the real LLM call should attempt to classify the
  fragment as one of `quantity`/`unit`/`date`/`site-name` from
  context, and return `"unknown"` honestly if it genuinely can't tell
  (never guess).

## `_llm_fallback_stub(text: str) -> dict`  — Person 4 replaces this

Current placeholder in `Agents/agent1_ingestion/classifier.py`:

```python
def _llm_fallback_stub(text: str) -> dict:
    return {"label": "unknown", "resolved_by": "llm_stub", "meta": None}
```

**Contract the real implementation must satisfy:**
- Input: `text` (str) — a single raw fragment that rules + NLP could
  not classify.
- Output: same shape as above — `{"label": ..., "resolved_by":
  "llm_stub", "meta": ...}`.
- `label` must be one of: `"quantity"`, `"unit"`, `"date"`,
  `"site-name"`, `"unknown"`.
- Must not raise on ambiguous/garbage input — return `"unknown"`
  instead of crashing, matching the rest of the cascade's
  fail-safe behavior.
- Should not silently guess a label with low confidence — honest
  `"unknown"` is preferred to a wrong label, since these values feed
  into emissions calculations downstream (Agent 2).

## `lookup_unit(raw_unit: str, fuzzy: bool = True, fuzzy_threshold: int = 85) -> dict`

Resolves a raw unit string (e.g. `"units"`, `"gallons"`, `"Kilowat-hours"`)
to a canonical unit + conversion multiplier. Returns:

```json
{
  "canonical_unit": "kWh" | "L" | "m3" | null,
  "multiplier": <float> | null,
  "resolved": true | false,
  "match_type": "exact" | "fuzzy:<matched_key>(<score>)" | null
}
```

- `resolved: false` means the unit is unknown — callers should treat
  this the same as an unresolved classification and hand off to the
  LLM tier, not assume a default unit.
- Fuzzy matching is only applied to reference keys 3+ characters
  long, to avoid short keys (like `"l"`) matching almost anything.

## Full record shape (for Agent 1 → Agent 2 handoff)

Not yet finalized — placeholder until Person 4's integration step
assembles the final JSON. Should match the shape from the team's
Agent 1 walkthrough:

```json
{
  "type": "electricity" | "fuel" | "water",
  "value": <float>,
  "unit": "kWh" | "L" | "m3",
  "date": "YYYY-MM-DD" or "YYYY-MM",
  "site": <string> | "unknown"
}
```

TODO (whoever owns Pydantic schema validation): confirm this against
the actual `electricity_consumption` / `fuel_consumption` /
`water_consumption` table columns in the Neon DB.