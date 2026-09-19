# schemas.py
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Tier(str, Enum):
    FREE_TRIAL = "free_trial"
    STANDARD = "standard"
    PREMIUM = "premium"


class RecommendationTier(str, Enum):
    QUICK_WIN = "quick_win"
    MEDIUM_TERM = "medium_term"
    TRANSFORMATIVE = "transformative"


# ---- Mirrors Agent 2's output shape (nested, not flattened) ----

class Anomaly(BaseModel):
    type: str
    magnitude: str
    period: str
    explanation: Optional[str] = None


class RenewableSizing(BaseModel):
    recommended_solar_kw: float
    offset_percentage: float
    payback_years: Optional[float] = None


class BudgetOutlook(BaseModel):
    projected_spend_next_month: float
    stated_budget: Optional[float] = None
    overrun: Optional[float] = None


class Agent2Diagnostics(BaseModel):
    footprint: dict
    anomalies: Optional[list[Anomaly]] = None
    renewable_sizing: Optional[RenewableSizing] = None
    budget_outlook: Optional[BudgetOutlook] = None
    sufficient_history: bool


# ---- Agent 3's actual input contract ----

class ProjectProposal(BaseModel):
    budget: float
    site_id: Optional[str] = None
    timeline_months: Optional[int] = None
    goals_text: Optional[str] = None


class Agent3Input(BaseModel):
    diagnostics: Agent2Diagnostics          # from Agent 2
    tier: Tier
    multi_site: bool = False
    sl_framework_applicable: bool = False
    user_context: Optional[str] = None      # free-text goal/notes from frontend
    proposal: Optional[ProjectProposal] = None   # only present if user submitted one


# ---- Output pieces ----

class SourceCitation(BaseModel):
    doc_id: str
    title: str
    relevance_score: float = Field(ge=0, le=1)


class ActionPlanItem(BaseModel):
    tier: RecommendationTier
    action: str
    reasoning: str
    estimated_impact: str          # free text — "15-20% fuel reduction"
    timeline: Optional[str] = None
    cost_estimate: Optional[str] = None
    source: SourceCitation          # REQUIRED — no ungrounded recommendations

    @field_validator("source")
    @classmethod
    def source_must_be_real(cls, v):
        if not v.doc_id or not v.title:
            raise ValueError("Every recommendation must cite a real source_id and title")
        return v


class SolarpunkPlan(BaseModel):
    projects: list[str]
    estimated_investment: Optional[float] = None
    timeline: Optional[str] = None
    sources: list[SourceCitation] = []
    disclaimer: str = "Planning estimate, not a certified engineering assessment"


class VendorMatch(BaseModel):
    category: str            # e.g. "solar_epc"
    matches: list[str]        # example vendor category names, not real endorsements


class AuditTrailExport(BaseModel):
    company_id: str
    run_ids: list[int]
    export_format: str        # "pdf" | "json"
    file_path: Optional[str] = None


# ---- Final Agent 3 output ----

class Agent3Output(BaseModel):
    tier: Tier
    action_plan: list[ActionPlanItem] = Field(min_length=1)
    sl_framework_notes: list[str] = []
    used_fallback_query: bool = False   # surfaced in UI — see fallback note below

    # Premium-only — None on Standard tier, never "missing"
    solarpunk_plan: Optional[SolarpunkPlan] = None
    vendor_matching: Optional[list[VendorMatch]] = None
    audit_trail: Optional[AuditTrailExport] = None