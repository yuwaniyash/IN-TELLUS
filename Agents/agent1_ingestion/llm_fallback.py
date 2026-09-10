import os
import json

from .schemas import ExtractionRecord


def build_fallback_prompt(raw_text: str, partial_data: dict) -> str:

    return f"""
You are a data extraction assistant.

Extract sustainability consumption information from the
following messy utility/fuel document.

Return ONLY valid JSON.

Required fields:
- resource_type
- consumption
- unit
- billing_period
- site

Optional fields:
- fuel_type
- account_number
- previous_reading
- current_reading
- amount_lkr

Rules:
- Do not invent values.
- If a value cannot be found, return null.
- Keep numerical values as numbers.
- Normalize resource_type to:
  electricity, water, fuel
- Normalize common units:
  electricity -> kWh
  water -> m3
  fuel -> litres
- Account numbers should be masked if necessary.

Partial information already extracted:

{json.dumps(partial_data, indent=2)}

Raw document:

{raw_text}
"""


def llm_fallback(
    raw_text: str,
    partial_data: dict
) -> dict:

    prompt = build_fallback_prompt(
        raw_text,
        partial_data
    )

    # -------------------------------------------------------
    # TEMPORARY FALLBACK
    # Replace this section with your team's LLM client.
    # -------------------------------------------------------

    print("LLM FALLBACK TRIGGERED")

    # Placeholder mode: no real LLM call yet, so fill required fields with
    # a safe sentinel instead of leaving them None. This lets Pydantic
    # validation and the rest of the pipeline be tested end-to-end before
    # Person 2/3's real parsing exists. Replace this block with the actual
    # LLM call + JSON parse once that's ready.
    filled = {
        "resource_type": partial_data.get("resource_type") or "unknown",
        "consumption": partial_data.get("consumption"),
        "unit": partial_data.get("unit") or "unknown",
        "billing_period": partial_data.get("billing_period") or "unknown",
        "site": partial_data.get("site") or "unknown",
    }

    return {
        **partial_data,
        **filled,
        "extraction_method": "llm_fallback",
        "confidence": 0.0,
        "warnings": [
            "LLM fallback currently running in placeholder mode — values are sentinels, not real extractions."
        ]
    }