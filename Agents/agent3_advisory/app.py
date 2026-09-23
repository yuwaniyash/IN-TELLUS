from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from Security_Layer.auth import get_current_company_id
from schemas import Agent3Input, Agent3ClientRequest, Agent3Output
from orchestration import agent3_recommend


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


@app.post("/agent3/recommend")
async def recommend(
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