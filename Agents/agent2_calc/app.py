"""
Agents/agent2_calc/app.py
============================
Agent 2 - Analysis. FastAPI app exposing POST /analyze.

Mirrors Agent 1's app.py conventions: company_id comes from the
verified JWT (Security_Layer.auth.get_current_company_id), never from
the request body; validate the request first; never hard-fail the whole
request over one bad site/record when partial results are possible.

Agent Communication contract:
  - Input:  POST /analyze { file_id, monthly_budget_lkr?, effective_tariff_lkr_per_kwh?,
            region?, sector?, floor_area_m2? } + Bearer JWT
  - Output: { success, result: { file_id, resource_type, footprint,
            suspicious_value_flags, site_reports: [...], audit_fingerprint }, warnings }
  - `result` is exactly the payload Agent 3 (Recommendation) should
    consume as its own input — Person 4's assembly step in assemble.py
    is what builds this shape.
"""

from fastapi import FastAPI, HTTPException, Depends

from Security_Layer.auth import get_current_company_id
from Security_Layer.file_intake import update_processing_status

from .schemas import AnalyzeRequest, AnalyzeResponse
from .security_validation import validate_analyze_request
from .assemble import run_full_analysis

app = FastAPI(
    title="Agent 2 - Analysis",
    version="1.0.0",
)

# CORS: this is a SEPARATE FastAPI app/process from Agent 1 (different
# port), so it needs its own CORS middleware -- Agent 1's doesn't cover
# it. Same reasoning as Agent 1's app.py: any request carrying a custom
# header (Authorization: Bearer <token>) triggers a browser preflight
# OPTIONS request first, which fails without this.
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"agent": "Agent 2", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    request: AnalyzeRequest,
    company_id: int = Depends(get_current_company_id),
):
    validation = validate_analyze_request(
        file_id=request.file_id,
        monthly_budget_lkr=request.monthly_budget_lkr,
        effective_tariff_lkr_per_kwh=request.effective_tariff_lkr_per_kwh,
        region=request.region,
        sector=request.sector,
    )
    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail={"message": "Invalid request", "errors": validation["errors"]},
        )

    outcome = run_full_analysis(
        file_id=request.file_id,
        company_id=company_id,
        monthly_budget_lkr=request.monthly_budget_lkr,
        effective_tariff_lkr_per_kwh=request.effective_tariff_lkr_per_kwh,
        region=request.region,
        sector=request.sector,
        floor_area_m2=request.floor_area_m2,
    )

    if outcome["errors"]:
        raise HTTPException(
            status_code=404,
            detail={"message": "Analysis could not be completed", "errors": outcome["errors"]},
        )

    try:
        update_processing_status(request.file_id, "ANALYZED")
    except Exception:
        pass

    return AnalyzeResponse(success=True, result=outcome["result"], warnings=[])