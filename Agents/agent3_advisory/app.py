from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from Security_Layer.auth import get_current_company_id
from schemas import Agent3Input, Agent3ClientRequest, Agent3Output, SolarpunkRequest, SolarpunkOutput
from orchestration import agent3_recommend, agent3_solarpunk_only
from proposal_extraction import extract_proposal, ProposalExtractionResult, MAX_BYTES


app = FastAPI(
    title="Agent 3 - Sustainability Advisory",
    version="1.0.0",
)

# CORS: same reasoning as Agent 1 -- the React frontend (localhost:5173)
# calls this API from a different origin/port, and the Authorization
# header on every request triggers a browser preflight OPTIONS request
# that FastAPI won't answer correctly without this middleware.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"agent": "Agent 3", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


# Plain `def` (not `async def`): the work inside is blocking (database,
# embeddings, LLM calls), so FastAPI runs it in a worker thread.
@app.post("/agent3/recommend")
def recommend(
    request: Agent3ClientRequest,
    company_id: int = Depends(get_current_company_id),
) -> Agent3Output | None:
    """
    company_id comes from the verified JWT via get_current_company_id --
    never from `request`, since Agent3ClientRequest has no company_id
    field for a client to supply or override.
    """
    agent_input = Agent3Input(
        company_id=company_id,
        diagnostics=request.diagnostics,
        tier=request.tier,
        multi_site=request.multi_site,
        sl_framework_applicable=request.sl_framework_applicable,
        user_context=request.user_context,
        proposal=request.proposal,
    )
    return agent3_recommend(agent_input)


@app.post("/agent3/extract-proposal")
def extract_proposal_endpoint(
    file: UploadFile = File(...),
    company_id: int = Depends(get_current_company_id),  # login required
) -> ProposalExtractionResult:
    """
    Reads an uploaded proposal (PDF/CSV) and returns DRAFT fields for the
    user to confirm. Nothing is saved and no plan is generated here.
    """
    name = (file.filename or "").lower()
    if not name.endswith((".pdf", ".csv")):
        raise HTTPException(status_code=400, detail="Only PDF and CSV files are supported.")

    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (10MB maximum).")

    try:
        return extract_proposal(name, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/agent3/solarpunk")
def solarpunk(
    request: SolarpunkRequest,
    company_id: int = Depends(get_current_company_id),
) -> SolarpunkOutput:
    """
    Premium, proposal-only flow: builds a solarpunk plan, vendor matches and
    the audit trail from the proposal alone. No utility bill required.
    company_id comes from the verified JWT, never from the request body.
    """
    result = agent3_solarpunk_only(company_id, request.proposal)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="We couldn't build a plan from this proposal. Try adding more detail to the goals.",
        )
    return result
