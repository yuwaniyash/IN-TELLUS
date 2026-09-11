import os
import json

from dotenv import load_dotenv
import google.generativeai as genai

from .schemas import ExtractionRecord

load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
_model = genai.GenerativeModel("gemini-2.5-flash")


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
- site refers to the physical location/branch/area office
  (e.g. "Area Office"), NOT the customer's personal mailing
  address unless no other location is given.

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

    print("LLM FALLBACK TRIGGERED")

    required_fields = [
        "resource_type", "consumption", "unit",
        "billing_period", "site"
    ]
    fields_before = {
        field: partial_data.get(field) for field in required_fields
    }

    try:
        response = _model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        recovered = json.loads(response.text)

    except (json.JSONDecodeError, Exception) as e:
        return {
            **partial_data,
            "extraction_method": "llm_fallback_failed",
            "confidence": 0.0,
            "warnings": partial_data.get("warnings", []) + [
                f"LLM fallback call/parse failed: {e}"
            ]
        }

    merged = {**partial_data}
    recovered_count = 0
    checked_count = 0

    for field in required_fields:
        # Only overwrite fields that were actually missing before —
        # never let the LLM clobber a value rule-based parsing already found.
        if fields_before[field] in (None, "", "unknown"):
            checked_count += 1
            value = recovered.get(field)
            if value not in (None, "", "null"):
                merged[field] = value
                recovered_count += 1

    # Optional fields: fill in if present and not already set.
    for field in ["fuel_type", "account_number", "previous_reading",
                   "current_reading", "amount_lkr"]:
        if not merged.get(field):
            value = recovered.get(field)
            if value not in (None, "", "null"):
                merged[field] = value

    confidence = round(recovered_count / checked_count, 2) if checked_count else 1.0
    still_missing = [
        f for f in required_fields
        if merged.get(f) in (None, "", "unknown")
    ]

    merged["extraction_method"] = "llm_fallback" if recovered_count > 0 else "llm_fallback_failed"
    merged["confidence"] = confidence
    merged["warnings"] = partial_data.get("warnings", []) + (
        [f"LLM fallback could not recover: {still_missing}"] if still_missing else []
    )

    return merged