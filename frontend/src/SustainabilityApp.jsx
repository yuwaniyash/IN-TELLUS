import React, { useState, useCallback, useEffect } from "react";
import { Upload, FileText, CheckCircle2, AlertTriangle, ChevronRight, Leaf, LogOut, Plus, MapPin, Download } from "lucide-react";
import { jsPDF } from "jspdf";

const API_BASE = "http://127.0.0.1:8001";
// Agent 2 is a SEPARATE FastAPI app/process from Agent 1 -- it never
// shares Agent 1's port. Update this if your team runs it elsewhere.
const AGENT2_API_BASE = "http://127.0.0.1:8002";
const TOKEN_KEY = "intellus_token";

// Display-only unit labels for the raw consumption summary in Step 2 --
// NOT used for any calculation. All real emissions math happens on the
// backend (Agent 2's emissions.py); the frontend never computes CO2e.
const UNIT_LABELS = { electricity: "kWh", water: "m3", fuel: "litres" };

const REGION_OPTIONS = [
  { value: "lowland_coastal", label: "Lowland / coastal" },
  { value: "mid_country", label: "Mid country" },
  { value: "hill_country", label: "Hill country" },
];
const SECTOR_OPTIONS = [
  { value: "", label: "Not sure / skip" },
  { value: "office", label: "Office" },
  { value: "retail_hospitality", label: "Retail / hospitality" },
  { value: "factory_industrial", label: "Factory / industrial" },
  { value: "warehouse", label: "Warehouse" },
];

const STEPS = [
  { id: 1, label: "Upload" },
  { id: 2, label: "Review" },
  { id: 3, label: "Summary" },
];

const UNMAPPED_WARNING_RE = /no site mapping for account '([^']+)'/;

function ContourMotif() {
  return (
    <svg aria-hidden="true" viewBox="0 0 400 400" className="ss-contour">
      <path d="M -20 260 Q 100 200 200 250 T 420 220" />
      <path d="M -20 300 Q 110 250 210 295 T 420 270" />
      <path d="M -20 340 Q 120 300 220 335 T 420 320" />
    </svg>
  );
}

function StepIndicator({ current }) {
  return (
    <ol className="ss-steps" aria-label="Progress">
      {STEPS.map((s, i) => (
        <li key={s.id} className="ss-step-item">
          <span
            className={"ss-step-dot " + (s.id === current ? "is-current" : s.id < current ? "is-done" : "")}
            aria-current={s.id === current ? "step" : undefined}
          >
            {s.id < current ? <CheckCircle2 size={13} strokeWidth={2.4} /> : s.id}
          </span>
          <span className="ss-step-label">{s.label}</span>
          {i < STEPS.length - 1 && <span className="ss-step-rule" aria-hidden="true" />}
        </li>
      ))}
    </ol>
  );
}

function AuthScreen({ mode, form, onField, onSubmit, error, loading, onSwitchMode }) {
  return (
    <div className="ss-panel">
      <h1 className="ss-h1">{mode === "login" ? "Welcome back" : "Set up your company"}</h1>
      <p className="ss-sub">
        {mode === "login"
          ? "Log in to track and review your consumption data."
          : "Creates your company workspace and an admin account."}
      </p>
      <div className="ss-card">
        <form onSubmit={onSubmit}>
          {mode === "register" && (
            <>
              <div className="ss-form-row">
                <label className="ss-label" htmlFor="companyName">Company name</label>
                <input id="companyName" className="ss-input" type="text" required value={form.companyName} onChange={onField("companyName")} />
              </div>
              <div className="ss-form-row">
                <label className="ss-label" htmlFor="fullName">Your name</label>
                <input id="fullName" className="ss-input" type="text" required value={form.fullName} onChange={onField("fullName")} />
              </div>
            </>
          )}
          <div className="ss-form-row">
            <label className="ss-label" htmlFor="email">Email</label>
            <input id="email" className="ss-input" type="email" required value={form.email} onChange={onField("email")} />
          </div>
          <div className="ss-form-row">
            <label className="ss-label" htmlFor="password">Password</label>
            <input id="password" className="ss-input" type="password" required value={form.password} onChange={onField("password")} />
          </div>
          {error && (
            <div className="ss-error">
              <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>{error}</span>
            </div>
          )}
          <div className="ss-actions" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <button type="button" className="ss-btn ss-btn-ghost" onClick={() => onSwitchMode(mode === "login" ? "register" : "login")}>
              {mode === "login" ? "Need an account? Register" : "Have an account? Log in"}
            </button>
            <button className="ss-btn" disabled={loading}>
              {loading ? "Please wait\u2026" : mode === "login" ? "Log in" : "Create account"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function SiteSetupScreen({ sites, form, onField, onSubmit, error, loading, onContinue }) {
  return (
    <div className="ss-panel">
      <h1 className="ss-h1">Add your first site</h1>
      <p className="ss-sub">
        A site is a physical location you track separately -- like "Colombo South" or "Kandy Branch".
        You'll map utility accounts to sites as bills come in.
      </p>

      {sites.length > 0 && (
        <div className="ss-card">
          <div className="ss-card-head">
            <span style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)" }}>Your sites</span>
          </div>
          <div className="ss-mini-list">
            {sites.map((s) => (
              <div className="ss-mini-row" key={s.site_id}>
                <span className="ss-mini-row-left"><MapPin size={13} style={{ marginRight: 6, verticalAlign: -2 }} />{s.site_name}</span>
                <span className="ss-mini-row-right">{s.address || ""}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="ss-card">
        <form onSubmit={onSubmit}>
          <div className="ss-form-row">
            <label className="ss-label" htmlFor="siteName">Site name</label>
            <input id="siteName" className="ss-input" type="text" required value={form.siteName} onChange={onField("siteName")} placeholder="e.g. Colombo South" />
          </div>
          <div className="ss-form-row">
            <label className="ss-label" htmlFor="siteAddress">Address (optional)</label>
            <input id="siteAddress" className="ss-input" type="text" value={form.siteAddress} onChange={onField("siteAddress")} />
          </div>
          {error && (
            <div className="ss-error">
              <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>{error}</span>
            </div>
          )}
          <div className="ss-actions">
            <button className="ss-btn" disabled={loading}>
              {loading ? "Adding\u2026" : "Add site"}
              {!loading && <Plus size={15} />}
            </button>
          </div>
        </form>
      </div>

      {sites.length > 0 && (
        <div className="ss-actions">
          <button className="ss-btn ss-btn-ghost" onClick={onContinue}>Continue to upload</button>
        </div>
      )}
    </div>
  );
}

function UnmappedAccountRow({ accountNumber, resourceType, sites, mapping, onChange, onSave, onAddSiteToggle, newSiteForm, onNewSiteField, onNewSiteSave }) {
  return (
    <div className="ss-card" style={{ marginBottom: 12 }}>
      <div className="ss-card-head">
        <span style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)" }}>New utility account detected</span>
        {mapping.saved && <span className="ss-pill">Saved</span>}
      </div>
      <p className="ss-sub" style={{ marginBottom: 16, fontSize: 13 }}>
        Account <strong>{accountNumber}</strong> ({resourceType || "unknown type"}) hasn't been mapped to a site yet.
        Confirm once and future bills from this account will resolve automatically.
      </p>

      {!mapping.saved && (
        <>
          <div className="ss-form-row">
            <label className="ss-label">Site</label>
            <select className="ss-input" value={mapping.siteId || ""} onChange={(e) => onChange(accountNumber, "siteId", e.target.value)}>
              <option value="">{"Choose a site\u2026"}</option>
              {sites.map((s) => (
                <option key={s.site_id} value={s.site_id}>{s.site_name}</option>
              ))}
            </select>
          </div>

          {!mapping.addingSite ? (
            <button type="button" className="ss-btn ss-btn-ghost" style={{ padding: "4px 0", fontSize: 13 }} onClick={() => onAddSiteToggle(accountNumber, true)}>
              + Add a new site instead
            </button>
          ) : (
            <div className="ss-card" style={{ background: "var(--cream)", padding: 16, marginTop: 8 }}>
              <div className="ss-form-row">
                <label className="ss-label">New site name</label>
                <input className="ss-input" type="text" value={newSiteForm.siteName} onChange={onNewSiteField(accountNumber, "siteName")} />
              </div>
              <div className="ss-actions" style={{ marginTop: 0 }}>
                <button type="button" className="ss-btn ss-btn-ghost" onClick={() => onAddSiteToggle(accountNumber, false)}>Cancel</button>
                <button type="button" className="ss-btn" onClick={() => onNewSiteSave(accountNumber)}>Create & use this site</button>
              </div>
            </div>
          )}

          {mapping.error && (
            <div className="ss-error">
              <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>{mapping.error}</span>
            </div>
          )}

          <div className="ss-actions">
            <button className="ss-btn" disabled={!mapping.siteId || mapping.saving} onClick={() => onSave(accountNumber, resourceType)}>
              {mapping.saving ? "Saving\u2026" : "Save mapping"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// One trend anomaly (a single flagged period from trends.py's detect_anomalies).
// trigger: "z_score" | "pct_deviation" | "both" -> mapped to a severity-style
// pill since the real payload doesn't carry a "severity" field directly.
function AnomalyPeriodRow({ a }) {
  const severity = a.trigger === "pct_deviation" ? "medium" : "high";
  return (
    <div className="ss-anomaly-row">
      <div className="ss-anomaly-head">
        <span style={{ fontWeight: 500 }}>{a.period}</span>
        <span className={"ss-severity-pill is-" + severity}>{a.direction} baseline</span>
      </div>
      <p className="ss-anomaly-reason">
        {a.value?.toLocaleString()} vs. baseline average {a.baseline_mean?.toLocaleString()}
        {" ("}{a.pct_deviation != null ? `${(a.pct_deviation * 100).toFixed(1)}%` : "\u2014"}{")"}
      </p>
    </div>
  );
}

// Renders one entry of analysis.site_reports -- trend/anomalies, renewable
// sizing, benchmark comparison, and the LLM explanation for one site.
function SiteReportCard({ report }) {
  const trend = report.trend || {};
  const historySufficient = trend.history_check?.sufficient;
  const flaggedAnomalies = (trend.anomalies || []).filter((a) => a.flagged);
  const renewable = report.renewable;
  const benchmark = report.benchmark_comparison;
  const explanation = typeof report.explanation === "string" ? report.explanation : null;

  return (
    <div className="ss-card">
      <div className="ss-card-head">
        <span style={{ fontSize: 15, fontWeight: 500, color: "var(--ink)" }}>{report.site}</span>
      </div>

      {!historySufficient ? (
        <p className="ss-optional-note" style={{ marginTop: 0 }}>{trend.history_check?.message}</p>
      ) : (
        <>
          {flaggedAnomalies.length > 0 ? (
            <>
              <p style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)", margin: "0 0 4px" }}>
                {flaggedAnomalies.length} period{flaggedAnomalies.length === 1 ? "" : "s"} flagged
              </p>
              {flaggedAnomalies.map((a, i) => <AnomalyPeriodRow key={i} a={a} />)}
            </>
          ) : (
            <p className="ss-optional-note" style={{ marginTop: 0 }}>No anomalies detected in this site's history.</p>
          )}

          {trend.pattern && trend.pattern.pattern !== "none" && (
            <p className="ss-optional-note">{trend.pattern.message}</p>
          )}

          {trend.forecast && trend.forecast.method !== "insufficient_data" && (
            <p className="ss-optional-note">
              Next period forecast: {trend.forecast.forecast_value?.toLocaleString()} ({trend.forecast.confidence} confidence)
            </p>
          )}

          {trend.budget_check && trend.budget_check.status !== "not_evaluable" && (
            <p className={trend.budget_check.status === "over_budget" ? "ss-warning" : "ss-optional-note"}>
              {trend.budget_check.status === "over_budget" && (
                <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 1, marginRight: 8 }} />
              )}
              {trend.budget_check.message}
            </p>
          )}
        </>
      )}

      {renewable && !renewable.errors?.length && (
        <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--hairline)" }}>
          <p style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)", margin: "0 0 8px" }}>Solar potential</p>
          <div className="ss-summary-row">
            <span>Recommended system size</span>
            <span>{renewable.sizing?.system_size_kwp} kWp</span>
          </div>
          <div className="ss-summary-row">
            <span>Offset of current usage</span>
            <span>{Math.round((renewable.sizing?.actual_offset_pct || 0) * 100)}%</span>
          </div>
          {renewable.savings_and_payback?.status === "ok" ? (
            <div className="ss-summary-row">
              <span>Estimated payback</span>
              <span>{renewable.savings_and_payback.payback_years} years</span>
            </div>
          ) : (
            <p className="ss-optional-note">{renewable.savings_and_payback?.message}</p>
          )}
        </div>
      )}

      {benchmark?.comparison && benchmark.comparison.status !== "not_evaluable" && (
        <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--hairline)" }}>
          <p style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)", margin: "0 0 8px" }}>Industry comparison</p>
          <p style={{ fontSize: 13, color: "var(--ink)", margin: 0, lineHeight: 1.5 }}>{benchmark.comparison.message}</p>
        </div>
      )}

      {explanation && (
        <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--hairline)" }}>
          <p style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)", margin: "0 0 8px" }}>What's driving this</p>
          <p style={{ fontSize: 13, color: "var(--ink)", margin: 0, lineHeight: 1.6 }}>{explanation}</p>
        </div>
      )}
    </div>
  );
}

export default function SustainabilityApp() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [authMode, setAuthMode] = useState("login");
  const [authForm, setAuthForm] = useState({ companyName: "", fullName: "", email: "", password: "" });
  const [authError, setAuthError] = useState(null);
  const [authLoading, setAuthLoading] = useState(false);

  const [sites, setSites] = useState([]);
  const [sitesLoaded, setSitesLoaded] = useState(false);
  const [siteSetupComplete, setSiteSetupComplete] = useState(false);
  const [manageSitesOpen, setManageSitesOpen] = useState(false);
  const [siteForm, setSiteForm] = useState({ siteName: "", siteAddress: "" });
  const [siteError, setSiteError] = useState(null);
  const [siteLoading, setSiteLoading] = useState(false);

  const [step, setStep] = useState(1);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [records, setRecords] = useState([]);
  const [fileId, setFileId] = useState(null);
  const [accountMappings, setAccountMappings] = useState({});

  const [analysisInputs, setAnalysisInputs] = useState({
    monthlyBudgetLkr: "", effectiveTariffLkrPerKwh: "", region: "mid_country", sector: "", floorAreaM2: "",
  });
  const [analysis, setAnalysis] = useState(null); // holds the /analyze response's "result" object
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  const authFetch = useCallback(
    async (path, options = {}, base = API_BASE) => {
      const res = await fetch(`${base}${path}`, {
        ...options,
        headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) {
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        throw new Error("Your session expired. Please log in again.");
      }
      return res;
    },
    [token]
  );

  const loadSites = useCallback(async () => {
    try {
      const res = await authFetch("/sites");
      if (!res.ok) return;
      const data = await res.json();
      setSites(data);
      setSitesLoaded(true);
      if (data.length > 0) setSiteSetupComplete(true);
    } catch {
      setSitesLoaded(true);
    }
  }, [authFetch]);

  useEffect(() => {
    if (token) loadSites();
  }, [token, loadSites]);

  const onAuthField = (key) => (e) => setAuthForm((prev) => ({ ...prev, [key]: e.target.value }));
  const onSiteField = (key) => (e) => setSiteForm((prev) => ({ ...prev, [key]: e.target.value }));
  const onAnalysisInputField = (key) => (e) => setAnalysisInputs((prev) => ({ ...prev, [key]: e.target.value }));

  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    try {
      const body = new URLSearchParams();
      body.append("username", authForm.email);
      body.append("password", authForm.password);
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || "Incorrect email or password");
      }
      const data = await res.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
    } catch (err) {
      setAuthError(err.message === "Failed to fetch" ? `Couldn't reach the backend. Is it running at ${API_BASE}?` : err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company_name: authForm.companyName,
          full_name: authForm.fullName,
          email: authForm.email,
          password: authForm.password,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || "Registration failed");
      }
      const data = await res.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
    } catch (err) {
      setAuthError(err.message === "Failed to fetch" ? `Couldn't reach the backend. Is it running at ${API_BASE}?` : err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setSites([]);
    setSitesLoaded(false);
    setSiteSetupComplete(false);
    setStep(1);
    setRecords([]);
    setFileId(null);
    setSelectedFile(null);
    setError(null);
    setAnalysis(null);
  };

  const handleAddSite = async (e) => {
    e.preventDefault();
    setSiteLoading(true);
    setSiteError(null);
    try {
      const res = await authFetch("/sites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ site_name: siteForm.siteName, address: siteForm.siteAddress || null }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || "Failed to add site");
      }
      const newSite = await res.json();
      setSites((prev) => [...prev, newSite]);
      setSiteForm({ siteName: "", siteAddress: "" });
    } catch (err) {
      setSiteError(err.message);
    } finally {
      setSiteLoading(false);
    }
  };

  const handleFile = useCallback((f) => {
    if (!f) return;
    setSelectedFile(f);
    setError(null);
  }, []);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    handleFile(e.dataTransfer.files?.[0]);
  }, [handleFile]);

  const runExtraction = async () => {
    if (!selectedFile) return;
    setIsProcessing(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", selectedFile);
      const res = await authFetch("/extract", { method: "POST", body: form });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail?.message || body?.detail || `Request failed (${res.status})`);
      }
      const data = await res.json();
      if (!data.records || data.records.length === 0) {
        throw new Error("No records could be extracted from this file.");
      }
      if (!data.file_id) {
        throw new Error("Agent 1 did not return a file_id -- check that ExtractionResponse and app.py have been updated.");
      }
      setFileId(data.file_id);
      setRecords(data.records);
      setAccountMappings({});
      setAnalysis(null);
      setAnalysisError(null);
      setStep(2);
    } catch (err) {
      setError(err.message === "Failed to fetch" ? "Couldn't reach the backend. Is it running at " + API_BASE + "?" : err.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const unmappedAccounts = React.useMemo(() => {
    const seen = new Map();
    for (const r of records) {
      const hasUnmappedWarning = r.warnings?.some((w) => UNMAPPED_WARNING_RE.test(w) || w.includes("no site mapping"));
      if (hasUnmappedWarning && r.account_number && !seen.has(r.account_number)) {
        seen.set(r.account_number, r.resource_type);
      }
    }
    return Array.from(seen.entries()).map(([accountNumber, resourceType]) => ({ accountNumber, resourceType }));
  }, [records]);

  const updateMapping = (accountNumber, key, value) => {
    setAccountMappings((prev) => ({ ...prev, [accountNumber]: { ...prev[accountNumber], [key]: value } }));
  };

  const toggleAddSite = (accountNumber, on) => {
    updateMapping(accountNumber, "addingSite", on);
    updateMapping(accountNumber, "newSiteName", "");
  };

  const saveNewSiteForMapping = async (accountNumber) => {
    const name = accountMappings[accountNumber]?.newSiteName;
    if (!name) return;
    try {
      const res = await authFetch("/sites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ site_name: name }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || "Failed to create site");
      }
      const newSite = await res.json();
      setSites((prev) => [...prev, newSite]);
      updateMapping(accountNumber, "siteId", String(newSite.site_id));
      updateMapping(accountNumber, "addingSite", false);
    } catch (err) {
      updateMapping(accountNumber, "error", err.message);
    }
  };

  const saveAccountMapping = async (accountNumber, resourceType) => {
    const siteId = accountMappings[accountNumber]?.siteId;
    if (!siteId) return;
    updateMapping(accountNumber, "saving", true);
    updateMapping(accountNumber, "error", null);
    try {
      const res = await authFetch("/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account_number: accountNumber, site_id: Number(siteId), resource_type: resourceType || null }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || "Failed to save mapping");
      }
      updateMapping(accountNumber, "saved", true);
    } catch (err) {
      updateMapping(accountNumber, "error", err.message);
    } finally {
      updateMapping(accountNumber, "saving", false);
    }
  };

  // Calls the REAL Agent 2 endpoint -- POST /analyze { file_id, ... }.
  // No fallback estimate: if this fails, we show the real error and stay
  // on Step 2, rather than pretending with a fabricated number.
  const runAnalysis = async () => {
    if (!fileId) {
      setAnalysisError("No file ID available for analysis.");
      return;
    }
    setIsAnalyzing(true);
    setAnalysisError(null);
    try {
      const body = {
        file_id: fileId,
        monthly_budget_lkr: analysisInputs.monthlyBudgetLkr ? Number(analysisInputs.monthlyBudgetLkr) : null,
        effective_tariff_lkr_per_kwh: analysisInputs.effectiveTariffLkrPerKwh ? Number(analysisInputs.effectiveTariffLkrPerKwh) : null,
        region: analysisInputs.region || "mid_country",
        sector: analysisInputs.sector || null,
        floor_area_m2: analysisInputs.floorAreaM2 ? Number(analysisInputs.floorAreaM2) : null,
      };
      const res = await authFetch("/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }, AGENT2_API_BASE);
      const data = await res.json();
      if (!res.ok) {
        const errs = data?.detail?.errors;
        throw new Error(data?.detail?.message || (errs ? errs.join(" ") : data?.detail) || `Analysis failed (${res.status})`);
      }
      setAnalysis(data.result);
      setStep(3);
    } catch (err) {
      setAnalysisError(err.message === "Failed to fetch" ? "Couldn't reach the backend. Is Agent 2 running?" : err.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Raw consumption totals for the Step 2 summary card -- display only,
  // computed from the extraction records, no emissions math involved.
  const totals = records.reduce((acc, r) => {
    if (!r.resource_type || r.consumption == null) return acc;
    acc[r.resource_type] = (acc[r.resource_type] || 0) + r.consumption;
    return acc;
  }, {});
  const warningCount = records.filter((r) => r.warnings?.length > 0).length;
  const previewRecords = records.slice(0, 5);

  // Real analysis-derived values for Step 3, from Agent 2's actual response.
  const footprint = analysis?.footprint;
  const companyTotal = footprint?.company_total;
  const totalCo2eKg = companyTotal ? Math.round(companyTotal.total_kg) : 0;
  // Only Fuel (Scope 1) and Electricity (Scope 2) are ever real, non-zero
  // scope-tagged values -- emissions.py never assigns scope=3 to anything
  // currently, so a "Scope 3" row would always show a misleading 0kg.
  // Water is excluded from the GHG total by policy but genuinely has a
  // real value -- shown as its own honest row below, not faked into a
  // scope bucket it doesn't belong to.
  const scopeRows = [
    { label: "Fuel (Scope 1)", kg: Math.round(companyTotal?.scope1_kg || 0), color: "var(--tan)" },
    { label: "Electricity (Scope 2)", kg: Math.round(companyTotal?.scope2_kg || 0), color: "var(--forest)" },
  ];
  const excludedKg = Math.round(companyTotal?.excluded_from_total_kg || 0);
  const maxScopeKg = Math.max(...scopeRows.map((r) => r.kg), excludedKg, 1);
  const suspiciousFlags = analysis?.suspicious_value_flags || [];
  const siteReports = analysis?.site_reports || [];
  const failedRecords = footprint?.failed_records || [];

  const downloadPdfReport = () => {
    if (!analysis) return;

    // Derived locally, self-contained -- "site" and "period" aren't
    // hoisted component-level values (the real Agent 2 result has no
    // single top-level period at all; siteReports can cover MULTIPLE
    // sites, not one). Building these here means this function can't
    // silently go stale if the rest of the component's variable names
    // change again.
    const reportSite = siteReports.length > 0
      ? siteReports.map((r) => r.site).join(", ")
      : (records[0]?.site || "Unknown site");
    const reportPeriod = records[0]?.billing_period || "\u2014";
    const site = reportSite;
    const period = reportPeriod;

    const doc = new jsPDF({ unit: "mm", format: "a4" });
    const marginX = 20;
    const pageWidth = 210;
    const contentWidth = pageWidth - marginX * 2;
    let y = 24;

    const COLOR = {
      forest: [59, 107, 82],
      forestDeep: [46, 84, 66],
      tan: [188, 138, 74],
      ink: [46, 42, 34],
      inkSoft: [122, 114, 100],
      sageDeep: [143, 184, 162],
      hairline: [227, 217, 195],
    };

    const ensureSpace = (needed) => {
      if (y + needed > 280) {
        doc.addPage();
        y = 24;
      }
    };

    const sectionTitle = (text) => {
      ensureSpace(14);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(12);
      doc.setTextColor(...COLOR.forestDeep);
      doc.text(text, marginX, y);
      y += 3;
      doc.setDrawColor(...COLOR.hairline);
      doc.line(marginX, y, marginX + contentWidth, y);
      y += 8;
    };

    const bodyLine = (text, opts = {}) => {
      const { bold = false, color = COLOR.ink, size = 10, indent = 0 } = opts;
      doc.setFont("helvetica", bold ? "bold" : "normal");
      doc.setFontSize(size);
      doc.setTextColor(...color);
      const lines = doc.splitTextToSize(text, contentWidth - indent);
      lines.forEach((line) => {
        ensureSpace(6);
        doc.text(line, marginX + indent, y);
        y += 5.5;
      });
    };

    const keyValueRow = (label, value) => {
      ensureSpace(6);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      doc.setTextColor(...COLOR.inkSoft);
      doc.text(label, marginX, y);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(...COLOR.ink);
      doc.text(String(value), marginX + contentWidth, y, { align: "right" });
      y += 6.5;
    };

    // --- Header ---
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(...COLOR.inkSoft);
    doc.text("IN-TELLUS", marginX, y);
    y += 8;

    doc.setFont("helvetica", "normal");
    doc.setFontSize(20);
    doc.setTextColor(...COLOR.ink);
    doc.text("Sustainability Report", marginX, y);
    y += 8;

    doc.setFontSize(11);
    doc.setTextColor(...COLOR.inkSoft);
    doc.text(`${site}  \u00b7  ${period}  \u00b7  Generated ${new Date().toLocaleDateString()}`, marginX, y);
    y += 12;

    // --- Emissions summary ---
    sectionTitle("Emissions Summary");
    keyValueRow("Total emissions (Scope 1 + 2)", `${totalCo2eKg.toLocaleString()} kg CO\u2082e`);
    scopeRows.forEach((r) => keyValueRow(r.label, `${r.kg.toLocaleString()} kg`));
    if (excludedKg > 0) {
      y += 2;
      bodyLine(`Plus ${excludedKg.toLocaleString()} kg from water, reported for context but excluded from the GHG total by policy.`, { size: 9, color: COLOR.inkSoft });
    }
    y += 4;

    // --- Failed records ---
    if (failedRecords.length > 0) {
      sectionTitle("Records Excluded From Totals");
      failedRecords.forEach((r) => {
        bodyLine(`${r.site || "Unknown site"} \u00b7 ${r.resource_type} \u00b7 ${r.billing_period}: ${r.errors.join("; ")}`, { size: 9, color: COLOR.tan });
      });
      y += 4;
    }

    // --- Suspicious value flags ---
    if (suspiciousFlags.length > 0) {
      sectionTitle("Flagged For Review");
      suspiciousFlags.forEach((f) => bodyLine(`\u2022 ${f}`, { size: 9.5 }));
      y += 4;
    }

    // --- Per-site reports ---
    siteReports.forEach((report) => {
      sectionTitle(`Site: ${report.site}`);

      const trend = report.trend;
      if (trend?.history_check && !trend.history_check.sufficient) {
        bodyLine(trend.history_check.message, { size: 9.5, color: COLOR.inkSoft });
      } else if (trend) {
        if (trend.pattern?.message) bodyLine(trend.pattern.message, { size: 9.5 });
        if (trend.forecast?.message) bodyLine(trend.forecast.message, { size: 9.5, color: COLOR.inkSoft });
        if (trend.budget_check?.status === "over_budget") {
          bodyLine(trend.budget_check.message, { size: 9.5, color: COLOR.tan, bold: true });
        } else if (trend.budget_check?.message) {
          bodyLine(trend.budget_check.message, { size: 9.5, color: COLOR.inkSoft });
        }
        const flaggedAnomalies = (trend.anomalies || []).filter((a) => a.flagged);
        flaggedAnomalies.forEach((a) => {
          bodyLine(
            `\u2022 ${a.period}: ${a.value.toLocaleString()} (${a.direction} baseline of ${a.baseline_mean?.toLocaleString()}, ${(a.pct_deviation * 100).toFixed(1)}% deviation)`,
            { size: 9, indent: 2 }
          );
        });
      }
      y += 2;

      if (report.renewable && !report.renewable.errors?.length) {
        bodyLine("Solar potential:", { bold: true, size: 10 });
        keyValueRow("Recommended system size", `${report.renewable.sizing.system_size_kwp.toLocaleString()} kWp`);
        keyValueRow("Offset of current usage", `${Math.round(report.renewable.sizing.actual_offset_pct * 100)}%`);
        if (report.renewable.savings_and_payback?.status === "ok") {
          keyValueRow("Estimated payback", `${report.renewable.savings_and_payback.payback_years} years`);
        } else if (report.renewable.savings_and_payback?.message) {
          bodyLine(report.renewable.savings_and_payback.message, { size: 9, color: COLOR.inkSoft });
        }
        y += 2;
      }

      if (report.benchmark_comparison?.comparison?.message) {
        bodyLine("Benchmark comparison:", { bold: true, size: 10 });
        bodyLine(report.benchmark_comparison.comparison.message, { size: 9.5 });
        y += 2;
      }

      if (report.explanation && typeof report.explanation === "string") {
        bodyLine("Summary:", { bold: true, size: 10 });
        bodyLine(report.explanation, { size: 9.5 });
      }

      y += 6;
    });

    // --- Footer ---
    ensureSpace(10);
    doc.setDrawColor(...COLOR.hairline);
    doc.line(marginX, y, marginX + contentWidth, y);
    y += 6;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(...COLOR.inkSoft);
    doc.text(`Report ID: ${analysis.audit_fingerprint || "n/a"}`, marginX, y);

    const filenameSafe = `${site}_${period}`.replace(/[^a-z0-9]+/gi, "_").toLowerCase();
    doc.save(`sustainability_report_${filenameSafe}.pdf`);
  };

  const showSiteSetup = token && sitesLoaded && (!siteSetupComplete || manageSitesOpen);

  return (
    <div className="ss-root">
      <style>{`
        .ss-root {
          --cream: #F4EFE4; --surface: #FBF8F1; --tan: #BC8A4A; --tan-soft: #D9B888;
          --sage: #B9D6C4; --sage-deep: #8FB8A2; --forest: #3B6B52; --forest-deep: #2E5442;
          --ink: #2E2A22; --ink-soft: #7A7264; --hairline: #E3D9C3;
          background: var(--cream); color: var(--ink);
          font-family: 'Manrope', ui-sans-serif, system-ui, sans-serif;
          min-height: 100%; position: relative; overflow: hidden; padding: 48px 24px 80px;
        }
        .ss-root * { box-sizing: border-box; }
        .ss-root :focus-visible { outline: 2px solid var(--forest); outline-offset: 2px; border-radius: 4px; }
        .ss-contour { position: absolute; right: -60px; bottom: -40px; width: 460px; height: 460px; opacity: 0.5; pointer-events: none; }
        .ss-contour path { fill: none; stroke: var(--sage-deep); stroke-width: 1.2; }
        .ss-contour path:nth-child(2) { stroke: var(--tan-soft); opacity: 0.7; }
        .ss-contour path:nth-child(3) { stroke: var(--sage-deep); opacity: 0.5; }
        .ss-shell { max-width: 640px; margin: 0 auto; position: relative; z-index: 1; }
        .ss-brand { display: flex; align-items: center; justify-content: space-between; margin-bottom: 40px; color: var(--forest-deep); }
        .ss-brand-mark { display: flex; align-items: center; gap: 8px; }
        .ss-brand span { font-weight: 600; font-size: 15px; letter-spacing: 0.01em; }
        .ss-logout-btn { display: inline-flex; align-items: center; gap: 6px; background: none; border: none; cursor: pointer; color: var(--ink-soft); font-family: inherit; font-size: 13px; }
        .ss-logout-btn:hover { color: var(--ink); }
        .ss-steps { display: flex; align-items: center; list-style: none; margin: 0 0 44px; padding: 0; }
        .ss-step-item { display: flex; align-items: center; }
        .ss-step-dot { width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; background: var(--surface); border: 1px solid var(--hairline); color: var(--ink-soft); flex-shrink: 0; }
        .ss-step-dot.is-current { background: var(--forest); border-color: var(--forest); color: var(--cream); }
        .ss-step-dot.is-done { background: var(--sage); border-color: var(--sage-deep); color: var(--forest-deep); }
        .ss-step-label { margin: 0 14px 0 8px; font-size: 13px; color: var(--ink-soft); }
        .ss-step-rule { width: 28px; height: 1px; background: var(--hairline); margin-right: 14px; }
        .ss-panel { animation: ss-fade 0.35s ease; }
        @media (prefers-reduced-motion: reduce) { .ss-panel { animation: none; } }
        @keyframes ss-fade { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
        .ss-h1 { font-weight: 250; font-size: clamp(28px, 4vw, 38px); line-height: 1.15; margin: 0 0 10px; color: var(--ink); letter-spacing: -0.01em; }
        .ss-sub { font-size: 15px; color: var(--ink-soft); margin: 0 0 36px; max-width: 50ch; line-height: 1.6; }
        .ss-form-row { margin-bottom: 18px; }
        .ss-label { display: block; font-size: 13px; color: var(--ink-soft); margin-bottom: 6px; }
        .ss-input { width: 100%; font-family: inherit; font-size: 14px; color: var(--ink); background: var(--cream); border: 1px solid var(--hairline); border-radius: 8px; padding: 10px 12px; }
        .ss-input:focus { outline: 2px solid var(--forest); outline-offset: 1px; border-color: var(--forest); }
        .ss-dropzone { border: 1.5px dashed var(--tan-soft); border-radius: 14px; padding: 48px 32px; text-align: center; background: var(--surface); transition: background 0.15s ease, border-color 0.15s ease; cursor: pointer; }
        .ss-dropzone.is-dragging { background: var(--sage); border-color: var(--sage-deep); }
        .ss-dropzone-icon { width: 44px; height: 44px; border-radius: 50%; background: var(--sage); display: flex; align-items: center; justify-content: center; margin: 0 auto 18px; color: var(--forest-deep); }
        .ss-dropzone-title { font-weight: 500; font-size: 15px; color: var(--ink); margin: 0 0 4px; }
        .ss-dropzone-hint { font-size: 13px; color: var(--ink-soft); margin: 0; }
        .ss-file-chip { display: inline-flex; align-items: center; gap: 8px; margin-top: 18px; padding: 7px 14px; background: var(--cream); border: 1px solid var(--hairline); border-radius: 999px; font-size: 13px; color: var(--ink); }
        .ss-error { display: flex; gap: 10px; margin-top: 18px; padding: 12px 14px; background: var(--surface); border-left: 2px solid var(--tan); border-radius: 4px; font-size: 13px; color: var(--ink); line-height: 1.5; }
        .ss-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 28px; }
        .ss-btn { display: inline-flex; align-items: center; gap: 6px; font-family: inherit; font-weight: 600; font-size: 14px; padding: 11px 20px; border-radius: 9px; border: none; cursor: pointer; background: var(--forest); color: var(--cream); transition: background 0.15s ease; }
        .ss-btn:hover:not(:disabled) { background: var(--forest-deep); }
        .ss-btn:disabled { background: var(--hairline); color: var(--ink-soft); cursor: not-allowed; }
        .ss-btn-ghost { background: transparent; color: var(--forest-deep); padding: 11px 8px; }
        .ss-btn-ghost:hover:not(:disabled) { background: transparent; text-decoration: underline; }
        .ss-card { background: var(--surface); border: 1px solid var(--hairline); border-radius: 14px; padding: 28px; }
        .ss-card + .ss-card { margin-top: 16px; }
        .ss-card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
        .ss-pill { font-size: 12px; font-weight: 600; padding: 4px 11px; border-radius: 999px; background: var(--sage); color: var(--forest-deep); }
        .ss-pill.is-flag { background: var(--tan-soft); color: var(--ink); }
        .ss-summary-row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--hairline); font-size: 14px; }
        .ss-summary-row:last-child { border-bottom: none; }
        .ss-summary-row span:first-child { color: var(--ink-soft); }
        .ss-summary-row span:last-child { font-weight: 500; }
        .ss-field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px 24px; }
        .ss-field label { display: block; font-size: 12px; color: var(--ink-soft); margin-bottom: 4px; }
        .ss-field div { font-size: 15px; font-weight: 500; color: var(--ink); }
        .ss-mini-list { margin-top: 4px; }
        .ss-mini-row { display: flex; justify-content: space-between; align-items: center; padding: 9px 0; border-bottom: 1px solid var(--hairline); font-size: 13px; }
        .ss-mini-row:last-child { border-bottom: none; }
        .ss-mini-row-left { color: var(--ink); }
        .ss-mini-row-right { color: var(--ink-soft); }
        .ss-warning { display: flex; gap: 10px; margin-top: 20px; padding: 12px 14px; background: var(--cream); border-left: 2px solid var(--tan); border-radius: 4px; font-size: 13px; color: var(--ink); line-height: 1.5; }
        .ss-optional-note { margin-top: 16px; font-size: 13px; color: var(--ink-soft); line-height: 1.5; }
        .ss-anomaly-row { padding: 10px 0; border-bottom: 1px solid var(--hairline); }
        .ss-anomaly-row:last-child { border-bottom: none; }
        .ss-anomaly-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; font-size: 13px; }
        .ss-severity-pill { font-size: 11px; font-weight: 600; padding: 3px 9px; border-radius: 999px; text-transform: capitalize; }
        .ss-severity-pill.is-low { background: var(--sage); color: var(--forest-deep); }
        .ss-severity-pill.is-medium { background: var(--tan-soft); color: var(--ink); }
        .ss-severity-pill.is-high { background: var(--tan); color: var(--surface); }
        .ss-anomaly-reason { font-size: 12px; color: var(--ink-soft); margin: 0; }
        .ss-hero { padding: 8px 0 32px; }
        .ss-hero-label { font-size: 13px; color: var(--ink-soft); margin: 0 0 6px; }
        .ss-hero-value { font-weight: 200; font-size: clamp(48px, 9vw, 72px); line-height: 1; color: var(--forest-deep); letter-spacing: -0.02em; }
        .ss-hero-unit { font-size: 20px; font-weight: 400; color: var(--ink-soft); margin-left: 8px; }
        .ss-bars { margin-top: 8px; }
        .ss-bar-row { display: grid; grid-template-columns: 150px 1fr 84px; align-items: center; gap: 12px; margin-bottom: 14px; font-size: 13px; }
        .ss-bar-row span:first-child { text-transform: capitalize; }
        .ss-bar-track { height: 10px; border-radius: 999px; background: var(--hairline); overflow: hidden; }
        .ss-bar-fill { height: 100%; border-radius: 999px; }
        .ss-bar-value { text-align: right; color: var(--ink-soft); }
        .ss-optional-toggle { font-size: 13px; color: var(--forest-deep); background: none; border: none; cursor: pointer; padding: 0; text-decoration: underline; }
        @media (max-width: 480px) { .ss-field-grid { grid-template-columns: 1fr; } .ss-root { padding: 32px 16px 60px; } }
      `}</style>

      <ContourMotif />

      <div className="ss-shell">
        <div className="ss-brand">
          <div className="ss-brand-mark"><Leaf size={18} strokeWidth={2} /><span>IN-TELLUS</span></div>
          {token && (
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <button className="ss-logout-btn" onClick={() => setManageSitesOpen(true)}><MapPin size={14} /> Manage sites</button>
              <button className="ss-logout-btn" onClick={handleLogout}><LogOut size={14} /> Log out</button>
            </div>
          )}
        </div>

        {!token ? (
          <AuthScreen
            mode={authMode} form={authForm} onField={onAuthField}
            onSubmit={authMode === "login" ? handleLogin : handleRegister}
            error={authError} loading={authLoading}
            onSwitchMode={(m) => { setAuthMode(m); setAuthError(null); }}
          />
        ) : showSiteSetup ? (
          <SiteSetupScreen
            sites={sites} form={siteForm} onField={onSiteField} onSubmit={handleAddSite}
            error={siteError} loading={siteLoading} onContinue={() => { setSiteSetupComplete(true); setManageSitesOpen(false); }}
          />
        ) : (
          <>
            <StepIndicator current={step} />

            {step === 1 && (
              <div className="ss-panel">
                <h1 className="ss-h1">Add a utility bill or usage log</h1>
                <p className="ss-sub">Upload an electricity bill, water bill, or fuel transaction log. We'll pull out the consumption data automatically.</p>
                <div
                  className={"ss-dropzone" + (isDragging ? " is-dragging" : "")}
                  onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={onDrop}
                  onClick={() => document.getElementById("ss-file-input").click()}
                  role="button" tabIndex={0}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") document.getElementById("ss-file-input").click(); }}
                >
                  <div className="ss-dropzone-icon"><Upload size={20} strokeWidth={2} /></div>
                  <p className="ss-dropzone-title">Drag a file here, or click to browse</p>
                  <p className="ss-dropzone-hint">PDF or CSV, up to 10MB</p>
                  <input id="ss-file-input" type="file" accept=".pdf,.csv" style={{ display: "none" }} onChange={(e) => handleFile(e.target.files?.[0])} />
                  {selectedFile && <div className="ss-file-chip"><FileText size={14} />{selectedFile.name}</div>}
                </div>
                {error && <div className="ss-error"><AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 1 }} /><span>{error}</span></div>}
                <div className="ss-actions">
                  <button className="ss-btn" disabled={!selectedFile || isProcessing} onClick={runExtraction}>
                    {isProcessing ? "Reading file\u2026" : "Continue"}
                    {!isProcessing && <ChevronRight size={15} />}
                  </button>
                </div>
              </div>
            )}

            {step === 2 && records.length > 0 && (
              <div className="ss-panel">
                <h1 className="ss-h1">Here's what we found</h1>
                <p className="ss-sub">
                  {records.length === 1 ? "Check the details below before we calculate emissions." : `${records.length} records extracted. Check the summary below before we calculate emissions.`}
                </p>

                {unmappedAccounts.map(({ accountNumber, resourceType }) => (
                  <UnmappedAccountRow
                    key={accountNumber}
                    accountNumber={accountNumber}
                    resourceType={resourceType}
                    sites={sites}
                    mapping={accountMappings[accountNumber] || {}}
                    onChange={updateMapping}
                    onSave={saveAccountMapping}
                    onAddSiteToggle={toggleAddSite}
                    newSiteForm={{ siteName: accountMappings[accountNumber]?.newSiteName || "" }}
                    onNewSiteField={(acc, key) => (e) => updateMapping(acc, key, e.target.value)}
                    onNewSiteSave={saveNewSiteForMapping}
                  />
                ))}

                {records.length === 1 ? (
                  <div className="ss-card">
                    <div className="ss-card-head">
                      <span className="ss-pill">{Math.round((records[0].confidence || 0) * 100)}% confident</span>
                      <span style={{ fontSize: 13, color: "var(--ink-soft)" }}>{selectedFile?.name}</span>
                    </div>
                    <div className="ss-field-grid">
                      <div className="ss-field"><label>Resource type</label><div style={{ textTransform: "capitalize" }}>{records[0].resource_type}</div></div>
                      <div className="ss-field"><label>Site</label><div>{records[0].site || "\u2014"}</div></div>
                      <div className="ss-field"><label>Consumption</label><div>{records[0].consumption?.toLocaleString()} {records[0].unit}</div></div>
                      <div className="ss-field"><label>Billing period</label><div>{records[0].billing_period || "\u2014"}</div></div>
                    </div>
                    {(() => {
                      const allWarnings = records[0].warnings || [];
                      const isOptionalFieldNote = (w) => /^(previous_reading|current_reading|amount_lkr) not found by rule-based parser$/.test(w);
                      const isSiteMappingNote = (w) => w.includes("no site mapping");
                      const optionalNotes = allWarnings.filter(isOptionalFieldNote);
                      const realWarnings = allWarnings.filter((w) => !isOptionalFieldNote(w) && !isSiteMappingNote(w));
                      return (
                        <>
                          {realWarnings.length > 0 && (
                            <div className="ss-warning">
                              <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                              <span>{realWarnings.join(" ")}</span>
                            </div>
                          )}
                        </>
                      );
                    })()}
                  </div>
                ) : (
                  <>
                    <div className="ss-card">
                      <div className="ss-summary-row"><span>File</span><span>{selectedFile?.name}</span></div>
                      <div className="ss-summary-row"><span>Records extracted</span><span>{records.length}</span></div>
                      <div className="ss-summary-row"><span>Flagged for review</span><span>{warningCount}</span></div>
                      {Object.entries(totals).map(([type, amount]) => (
                        <div className="ss-summary-row" key={type}>
                          <span style={{ textTransform: "capitalize" }}>{type} total</span>
                          <span>{amount.toLocaleString(undefined, { maximumFractionDigits: 1 })} {UNIT_LABELS[type] || ""}</span>
                        </div>
                      ))}
                    </div>
                    <div className="ss-card">
                      <div className="ss-card-head"><span style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)" }}>First 5 records</span></div>
                      <div className="ss-mini-list">
                        {previewRecords.map((r, i) => (
                          <div className="ss-mini-row" key={i}>
                            <span className="ss-mini-row-left">{r.fuel_type || r.resource_type || "unknown"} \u00b7 {r.site || "unknown site"}</span>
                            <span className="ss-mini-row-right">
                              {r.consumption != null ? `${r.consumption} ${r.unit || ""}` : "\u2014"}
                              {r.warnings?.length > 0 && <AlertTriangle size={12} style={{ marginLeft: 6, verticalAlign: -2, color: "var(--tan)" }} />}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}

                <div className="ss-card">
                  <div className="ss-card-head">
                    <span style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)" }}>Add details for a fuller analysis</span>
                    <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>Optional</span>
                  </div>
                  <div className="ss-field-grid">
                    <div className="ss-form-row" style={{ marginBottom: 0 }}>
                      <label className="ss-label">Monthly budget (LKR)</label>
                      <input className="ss-input" type="number" min="0" value={analysisInputs.monthlyBudgetLkr} onChange={onAnalysisInputField("monthlyBudgetLkr")} placeholder="e.g. 150000" />
                    </div>
                    <div className="ss-form-row" style={{ marginBottom: 0 }}>
                      <label className="ss-label">Electricity rate (LKR/kWh)</label>
                      <input className="ss-input" type="number" min="0" step="0.01" value={analysisInputs.effectiveTariffLkrPerKwh} onChange={onAnalysisInputField("effectiveTariffLkrPerKwh")} placeholder="Auto-estimated if left blank" />
                    </div>
                    <div className="ss-form-row" style={{ marginBottom: 0 }}>
                      <label className="ss-label">Region (for solar sizing)</label>
                      <select className="ss-input" value={analysisInputs.region} onChange={onAnalysisInputField("region")}>
                        {REGION_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                    </div>
                    <div className="ss-form-row" style={{ marginBottom: 0 }}>
                      <label className="ss-label">Sector (for benchmarking)</label>
                      <select className="ss-input" value={analysisInputs.sector} onChange={onAnalysisInputField("sector")}>
                        {SECTOR_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                    </div>
                    {analysisInputs.sector && (
                      <div className="ss-form-row" style={{ marginBottom: 0 }}>
                        <label className="ss-label">Floor area (m2)</label>
                        <input className="ss-input" type="number" min="0" value={analysisInputs.floorAreaM2} onChange={onAnalysisInputField("floorAreaM2")} />
                      </div>
                    )}
                  </div>
                </div>

                {analysisError && (
                  <div className="ss-error">
                    <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                    <span>{analysisError}</span>
                  </div>
                )}

                <div className="ss-actions">
                  <button className="ss-btn ss-btn-ghost" onClick={() => setStep(1)}>Back</button>
                  <button className="ss-btn" disabled={isAnalyzing} onClick={runAnalysis}>
                    {isAnalyzing ? "Analyzing\u2026" : "Calculate emissions"}
                    {!isAnalyzing && <ChevronRight size={15} />}
                  </button>
                </div>
              </div>
            )}

            {step === 3 && analysis && (
              <div className="ss-panel">
                <h1 className="ss-h1">Your footprint</h1>
                <p className="ss-sub">
                  {analysis.resource_type} \u2014 across {siteReports.length} site{siteReports.length === 1 ? "" : "s"}.
                </p>

                <div className="ss-hero">
                  <p className="ss-hero-label">Total emissions (Scope 1 + 2)</p>
                  <span className="ss-hero-value">{totalCo2eKg.toLocaleString()}<span className="ss-hero-unit">{" kg CO\u2082e"}</span></span>
                </div>

                <div className="ss-card">
                  <div className="ss-bars">
                    {scopeRows.map((r) => (
                      <div className="ss-bar-row" key={r.label}>
                        <span>{r.label}</span>
                        <div className="ss-bar-track"><div className="ss-bar-fill" style={{ width: `${(r.kg / maxScopeKg) * 100}%`, background: r.color }} /></div>
                        <span className="ss-bar-value">{r.kg.toLocaleString()} kg</span>
                      </div>
                    ))}
                    {excludedKg > 0 && (
                      <div className="ss-bar-row">
                        <span>Water (scope 3)</span>
                        <div className="ss-bar-track"><div className="ss-bar-fill" style={{ width: `${(excludedKg / maxScopeKg) * 100}%`, background: "var(--sage-deep)" }} /></div>
                        <span className="ss-bar-value">{excludedKg.toLocaleString()} kg</span>
                      </div>
                    )}
                  </div>
                </div>

                {suspiciousFlags.length > 0 && (
                  <div className="ss-card">
                    <div className="ss-card-head">
                      <span style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)" }}>Unusual values flagged</span>
                      <span className="ss-pill is-flag">{suspiciousFlags.length}</span>
                    </div>
                    {suspiciousFlags.map((f, i) => (
                      <p key={i} className="ss-anomaly-reason" style={{ marginBottom: 8 }}>{f}</p>
                    ))}
                  </div>
                )}

                {failedRecords.length > 0 && (
                  <div className="ss-warning">
                    <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                    <div>
                      <span>{failedRecords.length} record{failedRecords.length === 1 ? "" : "s"} couldn't be included in the emissions total due to data issues.</span>
                      {failedRecords.map((fr, i) => (
                        <div key={i} style={{ marginTop: 6, fontSize: 12, color: "var(--ink-soft)" }}>
                          {fr.site || "unknown site"} \u00b7 {fr.resource_type || "unknown type"} \u00b7 {fr.billing_period || "unknown period"}: {(fr.errors || []).join("; ")}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {siteReports.map((report, i) => <SiteReportCard key={i} report={report} />)}

                <div className="ss-actions">
                  <button
                    className="ss-btn ss-btn-ghost"
                    onClick={() => { setStep(1); setRecords([]); setSelectedFile(null); setFileId(null); setAnalysis(null); }}
                  >
                    Add another file
                  </button>
                  {analysis && (
                    <button className="ss-btn" onClick={downloadPdfReport}>
                      <Download size={15} /> Download PDF report
                    </button>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}