"""
Agents/agent2_calc/security_validation.py
=============================================
Request-body validation for Agent 2's /analyze endpoint.

Distinct from Security_Layer/sanitization.py (validates raw UPLOADED
FILES for Agent 1). Agent 2 doesn't receive files or a client-supplied
records array — it receives a small request body (which file/company to
analyze, plus optional caller-supplied overrides like a stated budget)
and pulls the actual data itself from Postgres, scoped by the JWT's
company_id. This module validates THAT smaller, different-shaped input.
"""

MAX_STRING_FIELD_LENGTH = 200

# Cheap defence against strings that could be replayed unescaped into an
# HTML report downstream — same philosophy as sanitization.py's CSV
# injection check, adapted for JSON string fields.
_DANGEROUS_SUBSTRINGS = ("<script", "javascript:", "../", "; rm ", "$(", "`")


def _string_field_is_safe(value: str) -> tuple:
    if len(value) > MAX_STRING_FIELD_LENGTH:
        return False, f"exceeds {MAX_STRING_FIELD_LENGTH} characters"
    lowered = value.lower()
    for bad in _DANGEROUS_SUBSTRINGS:
        if bad in lowered:
            return False, f"contains disallowed pattern: {bad!r}"
    return True, "ok"


def validate_analyze_request(file_id, monthly_budget_lkr=None,
                              effective_tariff_lkr_per_kwh=None, region=None,
                              sector=None) -> dict:
    """
    Returns {"valid": bool, "errors": [...]}. Never raises — the FastAPI
    route decides the HTTP status based on `valid`. `company_id` is
    deliberately NOT a parameter here: it must come from the verified
    JWT (Security_Layer.auth.get_current_company_id), never from the
    request body, so it can't be spoofed to read another company's data.
    """
    errors = []

    if not isinstance(file_id, int) or isinstance(file_id, bool) or file_id <= 0:
        errors.append(f"file_id must be a positive integer, got {file_id!r}")

    if sector is not None:
        if not isinstance(sector, str):
            errors.append(f"sector must be a string, got {type(sector).__name__}")
        else:
            safe, reason = _string_field_is_safe(sector)
            if not safe:
                errors.append(f"sector: {reason}")

    if monthly_budget_lkr is not None:
        if not isinstance(monthly_budget_lkr, (int, float)) or isinstance(monthly_budget_lkr, bool) or monthly_budget_lkr < 0:
            errors.append(f"monthly_budget_lkr must be a non-negative number, got {monthly_budget_lkr!r}")

    if effective_tariff_lkr_per_kwh is not None:
        if not isinstance(effective_tariff_lkr_per_kwh, (int, float)) or isinstance(effective_tariff_lkr_per_kwh, bool) or effective_tariff_lkr_per_kwh < 0:
            errors.append(f"effective_tariff_lkr_per_kwh must be a non-negative number, got {effective_tariff_lkr_per_kwh!r}")

    if region is not None:
        if not isinstance(region, str):
            errors.append(f"region must be a string, got {type(region).__name__}")
        elif region.lower() not in ("lowland_coastal", "mid_country", "hill_country"):
            errors.append(f"region must be one of lowland_coastal/mid_country/hill_country, got {region!r}")

    return {"valid": len(errors) == 0, "errors": errors}
