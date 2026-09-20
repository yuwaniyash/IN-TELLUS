import os
import json

from dotenv import load_dotenv
import google.generativeai as genai

from .schemas import ExtractionRecord

load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-3.5-flash-lite")
_model = genai.GenerativeModel(MODEL_NAME)


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
- Do NOT return a "site" field. Site is resolved separately from the
  company's own account-to-site mapping, never from bill text -- a
  guessed site name has no real site_id behind it and would be shown
  as if confirmed when it isn't. If this field appears in your output
  it will be ignored.

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

    # "site" is deliberately excluded here -- see the prompt's note above.
    # Site must only ever come from a confirmed account->site mapping
    # (resolve_site() in pipeline.py), never from an LLM guess at bill
    # text, since a guessed name has no real site_id and would display
    # as if it were a confirmed mapping when it isn't.
    required_fields = [
        "resource_type", "consumption", "unit", "billing_period"
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
        if fields_before[field] in (None, "", "unknown"):
            checked_count += 1
            value = recovered.get(field)
            if value not in (None, "", "null"):
                merged[field] = value
                recovered_count += 1

    optional_recovered_count = 0
    optional_checked_count = 0

    for field in ["fuel_type", "account_number", "previous_reading",
                   "current_reading", "amount_lkr"]:
        if not merged.get(field):
            optional_checked_count += 1
            value = recovered.get(field)
            if value not in (None, "", "null"):
                merged[field] = value
                optional_recovered_count += 1

    total_recovered = recovered_count + optional_recovered_count
    total_checked = checked_count + optional_checked_count

    confidence = round(total_recovered / total_checked, 2) if total_checked else 1.0
    still_missing = [
        f for f in required_fields
        if merged.get(f) in (None, "", "unknown")
    ]

    merged["extraction_method"] = "llm_fallback" if total_recovered > 0 else "llm_fallback_failed"
    merged["confidence"] = confidence
    merged["warnings"] = partial_data.get("warnings", []) + (
        [f"LLM fallback could not recover: {still_missing}"] if still_missing else []
    )

    # Belt-and-suspenders: even if the model ignores the prompt instruction
    # and returns a "site" key anyway, never let it end up in the merged
    # result -- site only ever comes from resolve_site().
    merged.pop("site", None)
    merged["site"] = partial_data.get("site")

    return merged