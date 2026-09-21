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


# ---- Mirrors Agent 2's REAL output shape (assemble.py / trends.py / renewable.py) ----

class HistoryCheck(BaseModel):
    sufficient: bool
    message: Optional[str] = None


class TrendAnomaly(BaseModel):
    period: str
    trigger: str  # "z_score" | "pct_deviation" | "both"
    direction: str  # e.g. "above" / "below"
    value: float
    baseline_mean: Optional[float] = None
    pct_deviation: Optional[float] = None
    flagged: bool = False


class TrendPattern(BaseModel):
    pattern: str
    message: Optional[str] = None


class TrendForecast(BaseModel):
    method: str
    forecast_value: Optional[float] = None
    confidence: Optional[str] = None
    message: Optional[str] = None


class BudgetCheck(BaseModel):
    status: str  # "over_budget" | "under_budget" | "not_evaluable" | ...
    message: Optional[str] = None


class Trend(BaseModel):
    history_check: HistoryCheck
    anomalies: list[TrendAnomaly] = []
    pattern: Optional[TrendPattern] = None
    forecast: Optional[TrendForecast] = None
    budget_check: Optional[BudgetCheck] = None


class RenewableSizingDetail(BaseModel):
    system_size_kwp: float
    actual_offset_pct: float


class SavingsAndPayback(BaseModel):
    status: str  # "ok" | "not_evaluable"
    payback_years: Optional[float] = None
    message: Optional[str] = None


class Renewable(BaseModel):
    sizing: Optional[RenewableSizingDetail] = None
    savings_and_payback: Optional[SavingsAndPayback] = None
    errors: list[str] = []


class BenchmarkComparisonDetail(BaseModel):
    status: str  # "not_evaluable" | ...
    message: Optional[str] = None


class BenchmarkComparison(BaseModel):
    comparison: Optional[BenchmarkComparisonDetail] = None


class SiteReport(BaseModel):
    site: str
    resource_type: str
    trend: Trend
    renewable: Optional[Renewable] = None
    benchmark_comparison: Optional[BenchmarkComparison] = None
    nlp_context: Optional[dict] = None
    explanation: Optional[str] = None


class FailedRecord(BaseModel):
    site: Optional[str] = None
    resource_type: Optional[str] = None
    billing_period: Optional[str] = None
    errors: list[str] = []


class CompanyTotal(BaseModel):
    total_kg: float
    scope1_kg: float = 0
    scope2_kg: float = 0
    excluded_from_total_kg: float = 0


class Footprint(BaseModel):
    company_total: CompanyTotal
    failed_records: list[FailedRecord] = []


class Agent2Diagnostics(BaseModel):
    """Matches assemble.py's run_full_analysis() -> result dict, exactly."""
    file_id: int
    resource_type: str
    footprint: Footprint
    suspicious_value_flags: list[str] = []
    site_reports: list[SiteReport] = []
    audit_fingerprint: Optional[str] = None


# ---- Agent 3's actual input contract ----

class ProjectProposal(BaseModel):
    budget: float
    site_id: Optional[str] = None
    timeline_months: Optional[int] = None
    goals_text: Optional[str] = None


class Agent3Input(BaseModel):
    # SECURITY: company_id must be set server-side from the verified JWT
    # (via Depends(get_current_company_id)), NEVER deserialized directly
    # from client-supplied request JSON. Agent3ClientRequest below is
    # what the client actually sends -- it has no company_id field, so
    # there's nothing for a client to override.
    company_id: int
    diagnostics: Agent2Diagnostics          # from Agent 2
    tier: Tier
    multi_site: bool = False
    sl_framework_applicable: bool = False
    user_context: Optional[str] = None      # free-text goal/notes from frontend
    proposal: Optional[ProjectProposal] = None   # only present if user submitted one


class Agent3ClientRequest(BaseModel):
    """What the client actually sends to /agent3/recommend. No company_id --
    that comes from the verified JWT, server-side, never from request JSON."""
    diagnostics: Agent2Diagnostics
    tier: Tier
    multi_site: bool = False
    sl_framework_applicable: bool = False
    user_context: Optional[str] = None
    proposal: Optional[ProjectProposal] = None


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
    company_id: int
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