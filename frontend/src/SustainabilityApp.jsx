import React, { useState, useCallback, useEffect, useRef } from "react";
import { HeroLanding } from './HeroLanding';
import { DrawCircleText } from './DrawCircleText';
import { CardsFeatures } from './CardsFeatures';
import { Upload, FileText, CheckCircle2, AlertTriangle, ChevronRight, Leaf, LogOut, Plus, MapPin, Download, ArrowDown, BarChart2, Shield, Zap } from "lucide-react";
import { jsPDF } from "jspdf";

const API_BASE = "http://127.0.0.1:8001";
const AGENT2_API_BASE = "http://127.0.0.1:8002";
const AGENT3_API_BASE = "http://127.0.0.1:8003";
const TOKEN_KEY = "intellus_token";

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

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');

  * { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --navy: #f9fafb;
    --slate: #f0fdf9;
    --mint: #0d9488;
    --mint-dim: rgba(13,148,136,0.08);
    --mint-border: rgba(13,148,136,0.25);
    --white: #0f172a;
    --muted: rgba(15,23,42,0.5);
    --line: rgba(15,23,42,0.1);
    --danger: #dc2626;
  }

  #root, body { border: none !important; border-inline: none !important; max-width: 100% !important; width: 100% !important; margin: 0 !important; padding: 0 !important; text-align: left !important; }
  body { background: var(--navy); color: var(--white); font-family: 'Montserrat', sans-serif; }

  /* ── LANDING ── */
  .lp-root { min-height: 100vh; background: var(--navy); overflow-x: hidden; }

  .lp-nav {
    position: fixed; top: 0; left: 0; right: 0; z-index: 100;
    display: flex; align-items: center; justify-content: space-between;
    padding: 20px 48px;
    border-bottom: 1px solid transparent;
    transition: background 0.3s, border-color 0.3s, backdrop-filter 0.3s;
  }
  .lp-nav.scrolled {
    background: rgba(249,250,251,0.92);
    border-color: var(--line);
    
  }
  .lp-brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 15px; letter-spacing: 0.06em; color: var(--white); }
  .lp-brand-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--mint); flex-shrink: 0; }
  .lp-nav-actions { display: flex; align-items: center; gap: 12px; }

  .lp-hero {
    min-height: 100vh; display: flex; flex-direction: column;
    justify-content: center; padding: 0 48px; position: relative; overflow: hidden;
  }
  .lp-orb {
    position: absolute; top: -180px; right: -180px;
    width: 600px; height: 600px; border-radius: 50%;
    background: radial-gradient(circle, rgba(152,255,235,0.18) 0%, rgba(152,255,235,0.04) 50%, transparent 70%);
    pointer-events: none;
  }
  .lp-orb-2 {
    position: absolute; bottom: -200px; left: -100px;
    width: 400px; height: 400px; border-radius: 50%;
    background: radial-gradient(circle, rgba(152,255,235,0.07) 0%, transparent 60%);
    pointer-events: none;
  }
  .lp-hero-inner { max-width: 720px; position: relative; z-index: 1; }
  .lp-eyebrow { font-size: 12px; font-weight: 600; letter-spacing: 0.14em; color: var(--mint); margin-bottom: 28px; }
  .lp-headline {
    font-size: clamp(38px, 5.5vw, 68px); font-weight: 300; line-height: 1.1;
    color: var(--white); letter-spacing: -0.02em; margin-bottom: 24px;
  }
  .lp-headline strong { font-weight: 700; color: var(--mint); }
  .lp-hero-sub { font-size: 16px; font-weight: 400; color: var(--muted); line-height: 1.7; max-width: 48ch; margin-bottom: 48px; }
  .lp-hero-cta { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }

  .lp-scroll-hint {
    position: absolute; bottom: 40px; left: 48px; z-index: 1;
    display: flex; align-items: center; gap: 8px;
    font-size: 12px; color: var(--muted); letter-spacing: 0.08em; font-weight: 500;
    animation: lp-bob 2.4s ease-in-out infinite;
  }
  @keyframes lp-bob { 0%,100%{transform:translateY(0)} 50%{transform:translateY(6px)} }

  /* features */
  .lp-features { padding: 120px 48px; max-width: 1100px; margin: 0 auto; }
  .lp-section-label { font-size: 11px; font-weight: 600; letter-spacing: 0.14em; color: var(--mint); margin-bottom: 16px; }
  .lp-section-title { font-size: clamp(28px, 3.5vw, 42px); font-weight: 300; color: var(--white); margin-bottom: 64px; letter-spacing: -0.01em; }
  .lp-section-title b { font-weight: 700; }
  .lp-feature-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 2px; }
  .lp-feature {
    background: var(--slate); padding: 40px 36px;
    border: 1px solid var(--line); transition: border-color 0.2s;
  }
  .lp-feature:first-child { border-radius: 16px 0 0 16px; }
  .lp-feature:last-child { border-radius: 0 16px 16px 0; }
  .lp-feature:hover { border-color: var(--mint-border); }
  .lp-feature-icon { width: 40px; height: 40px; border-radius: 0; background: var(--mint-dim); display: flex; align-items: center; justify-content: center; color: var(--mint); margin-bottom: 24px; }
  .lp-feature h3 { font-size: 16px; font-weight: 600; color: var(--white); margin-bottom: 10px; }
  .lp-feature p { font-size: 13px; color: var(--muted); line-height: 1.7; }

  /* tiers */
  .lp-tiers { padding: 80px 48px 120px; max-width: 1100px; margin: 0 auto; }
  .lp-tier-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
  .lp-tier {
    background: var(--slate); border: 1px solid var(--line); border-radius: 0;
    padding: 36px 32px; display: flex; flex-direction: column; gap: 20px;
    transition: border-color 0.2s, transform 0.2s;
    cursor: pointer;
  }
  .lp-tier:hover { border-color: var(--mint-border); transform: translateY(-4px); }
  .lp-tier.is-featured { border-color: var(--mint-border); background: linear-gradient(135deg, rgba(13,148,136,0.07) 0%, var(--slate) 100%); }
  .lp-tier-badge { display: inline-flex; align-items: center; padding: 4px 12px; border-radius: 999px; background: var(--mint); color: #f9fafb; font-size: 11px; font-weight: 700; letter-spacing: 0.06em; width: fit-content; }
  .lp-tier h3 { font-size: 20px; font-weight: 600; color: var(--white); }
  .lp-tier p { font-size: 13px; color: var(--muted); line-height: 1.65; flex: 1; }

  /* auth */
  .auth-root { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--navy); padding: 24px; }
  .auth-card { width: 100%; max-width: 420px; background: var(--slate); border: 1px solid var(--line); border-radius: 0; padding: 40px; }
  .auth-logo { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 14px; letter-spacing: 0.06em; color: var(--white); margin-bottom: 32px; }
  .auth-logo-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--mint); }
  .auth-title { font-size: 24px; font-weight: 600; color: var(--white); margin-bottom: 6px; }
  .auth-sub { font-size: 13px; color: var(--muted); margin-bottom: 28px; line-height: 1.5; }
  .auth-switch { font-size: 13px; color: var(--muted); margin-top: 20px; text-align: center; }
  .auth-switch button { background: none; border: none; color: var(--mint); cursor: pointer; font-family: inherit; font-size: 13px; font-weight: 600; padding: 0; }

  /* shared app chrome */
  .app-root { min-height: 100vh; background: var(--navy); display: flex; flex-direction: column; }
  .app-nav {
    position: sticky; top: 0; z-index: 50;
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 40px; background: rgba(249,250,251,0.95);
    border-bottom: 1px solid var(--line); 
  }
  .app-brand { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 14px; letter-spacing: 0.06em; color: var(--white); }
  .app-brand-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--mint); }
  .app-nav-links { display: flex; align-items: center; gap: 4px; }
  .app-nav-btn { display: flex; align-items: center; gap: 6px; background: none; border: none; cursor: pointer; color: var(--muted); font-family: inherit; font-size: 13px; font-weight: 500; padding: 7px 12px; border-radius: 0; transition: color 0.15s, background 0.15s; }
  .app-nav-btn:hover { color: var(--white); background: var(--mint-dim); }

  .app-body { flex: 1; padding: 40px; max-width: 720px; margin: 0 auto; width: 100%; }

  /* steps */
  .steps-bar { display: flex; align-items: center; margin-bottom: 44px; }
  .step-item { display: flex; align-items: center; }
  .step-dot {
    width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; flex-shrink: 0;
    background: var(--slate); border: 1px solid var(--line); color: var(--muted);
    transition: background 0.2s, border-color 0.2s, color 0.2s;
  }
  .step-dot.is-current { background: var(--mint); border-color: var(--mint); color: var(--navy); }
  .step-dot.is-done { background: var(--mint-dim); border-color: var(--mint-border); color: var(--mint); }
  .step-label { margin: 0 16px 0 10px; font-size: 12px; font-weight: 600; letter-spacing: 0.05em; color: var(--muted); }
  .step-dot.is-current + .step-label { color: var(--white); }
  .step-rule { width: 32px; height: 1px; background: var(--line); margin-right: 16px; }

  /* panels */
  .panel { animation: panel-in 0.3s ease; }
  @keyframes panel-in { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }

  .panel-title { font-size: clamp(24px, 3vw, 32px); font-weight: 300; color: var(--white); margin-bottom: 8px; letter-spacing: -0.01em; }
  .panel-sub { font-size: 14px; color: var(--muted); margin-bottom: 32px; line-height: 1.65; }

  /* cards */
  .card { background: var(--slate); border: 1px solid var(--line); border-radius: 0; padding: 28px; }
  .card + .card { margin-top: 16px; }
  .card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
  .card-label { font-size: 13px; font-weight: 600; color: var(--white); }

  /* form */
  .form-row { margin-bottom: 16px; }
  .form-label { display: block; font-size: 12px; font-weight: 600; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 8px; }
  .form-input {
    width: 100%; font-family: inherit; font-size: 14px; color: var(--white);
    background: rgba(249,250,251,0.05); border: 1px solid var(--line);
    border-radius: 0; padding: 11px 14px; transition: border-color 0.15s, background 0.15s;
  }
  .form-input::placeholder { color: rgba(249,250,251,0.25); }
  .form-input:focus { outline: none; border-color: var(--mint-border); background: var(--mint-dim); }
  select.form-input option { background: var(--navy); color: var(--white); }
  textarea.form-input { resize: vertical; }

  /* buttons */
  .btn {
    display: inline-flex; align-items: center; gap: 8px;
    font-family: inherit; font-weight: 700; font-size: 13px; letter-spacing: 0.04em;
    padding: 12px 22px; border-radius: 0; border: none; cursor: pointer;
    background: var(--mint); color: #f9fafb; transition: opacity 0.15s, transform 0.15s;
  }
  .btn:hover:not(:disabled) { opacity: 0.88; transform: translateY(-1px); }
  .btn:disabled { opacity: 0.35; cursor: not-allowed; transform: none; }
  .btn-ghost {
    background: transparent; color: var(--muted);
    border: 1px solid var(--line);
  }
  .btn-ghost:hover:not(:disabled) { color: var(--white); border-color: rgba(249,250,251,0.25); background: transparent; transform: none; }
  .btn-outline {
    background: transparent; color: var(--white);
    border: 1px solid rgba(249,250,251,0.25);
  }
  .btn-outline:hover:not(:disabled) { border-color: var(--mint); color: var(--mint); background: transparent; transform: none; }

  .actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }

  /* dropzone */
  .dropzone {
    border: 1.5px dashed var(--line); border-radius: 0; padding: 56px 32px;
    text-align: center; background: rgba(249,250,251,0.02);
    transition: background 0.15s, border-color 0.15s; cursor: pointer;
  }
  .dropzone:hover, .dropzone.dragging { background: var(--mint-dim); border-color: var(--mint-border); }
  .dropzone-icon { width: 48px; height: 48px; border-radius: 0; background: var(--mint-dim); display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; color: var(--mint); }
  .dropzone-title { font-size: 15px; font-weight: 600; color: var(--white); margin-bottom: 6px; }
  .dropzone-hint { font-size: 13px; color: var(--muted); }
  .file-chip { display: inline-flex; align-items: center; gap: 8px; margin-top: 20px; padding: 8px 16px; background: var(--mint-dim); border: 1px solid var(--mint-border); border-radius: 999px; font-size: 13px; color: var(--mint); font-weight: 600; }

  /* alerts */
  .alert-error { display: flex; gap: 10px; margin-top: 16px; padding: 14px 16px; background: rgba(251,146,60,0.1); border-left: 2px solid var(--danger); border-radius: 0; font-size: 13px; color: var(--white); line-height: 1.5; }
  .alert-warn { display: flex; gap: 10px; margin-top: 16px; padding: 14px 16px; background: rgba(251,146,60,0.08); border-left: 2px solid rgba(251,146,60,0.5); border-radius: 0; font-size: 13px; color: var(--muted); line-height: 1.5; }

  /* summary rows */
  .sum-row { display: flex; justify-content: space-between; align-items: center; padding: 11px 0; border-bottom: 1px solid var(--line); font-size: 14px; }
  .sum-row:last-child { border-bottom: none; }
  .sum-row span:first-child { color: var(--muted); }
  .sum-row span:last-child { font-weight: 600; color: var(--white); }

  /* mini list */
  .mini-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--line); font-size: 13px; }
  .mini-row:last-child { border-bottom: none; }

  /* field grid */
  .field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px 24px; }
  .field label { display: block; font-size: 11px; font-weight: 600; letter-spacing: 0.07em; color: var(--muted); margin-bottom: 5px; }
  .field div { font-size: 15px; font-weight: 500; color: var(--white); }

  /* pills */
  .pill { font-size: 11px; font-weight: 700; padding: 4px 12px; border-radius: 999px; letter-spacing: 0.04em; }
  .pill-mint { background: var(--mint-dim); color: var(--mint); border: 1px solid var(--mint-border); }
  .pill-warn { background: rgba(251,146,60,0.15); color: var(--danger); border: 1px solid rgba(251,146,60,0.3); }

  /* hero number */
  .hero-num { padding: 8px 0 28px; }
  .hero-num-label { font-size: 12px; font-weight: 600; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 8px; }
  .hero-num-value { font-size: clamp(52px, 8vw, 80px); font-weight: 200; line-height: 1; color: var(--white); letter-spacing: -0.03em; }
  .hero-num-unit { font-size: 18px; font-weight: 400; color: var(--muted); margin-left: 10px; }

  /* bars */
  .bar-row { display: grid; grid-template-columns: 160px 1fr 80px; align-items: center; gap: 14px; margin-bottom: 16px; font-size: 13px; }
  .bar-track { height: 8px; border-radius: 999px; background: var(--line); overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 999px; transition: width 0.8s ease; }
  .bar-val { text-align: right; color: var(--muted); font-weight: 500; }

  /* anomaly */
  .anomaly-row { padding: 12px 0; border-bottom: 1px solid var(--line); }
  .anomaly-row:last-child { border-bottom: none; }
  .anomaly-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; font-size: 13px; font-weight: 500; }
  .anomaly-body { font-size: 12px; color: var(--muted); }
  .sev-pill { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 999px; }
  .sev-high { background: rgba(251,146,60,0.2); color: var(--danger); }
  .sev-medium { background: rgba(251,220,60,0.15); color: #fbbf24; }

  /* note */
  .note { font-size: 13px; color: var(--muted); margin-top: 14px; line-height: 1.6; }

  /* optional inputs toggle */
  .optional-toggle { font-size: 13px; color: var(--mint); background: none; border: none; cursor: pointer; font-family: inherit; font-weight: 600; padding: 0; }

  /* site setup */
  .setup-root { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--navy); padding: 24px; }
  .setup-card { width: 100%; max-width: 520px; }

  @media (max-width: 640px) {
    .lp-hero { padding: 0 24px; }
    .lp-features, .lp-tiers { padding: 80px 24px; }
    .lp-feature-grid, .lp-tier-grid { grid-template-columns: 1fr; }
    .lp-feature:first-child, .lp-feature:last-child { border-radius: 0; }
    .app-body { padding: 24px 20px; }
    .field-grid { grid-template-columns: 1fr; }
    .lp-nav { padding: 16px 24px; }
    .app-nav { padding: 14px 20px; }
  }
`;

// ── LANDING ──────────────────────────────────────────────────────────
function LandingPage({ onLogin, onSelectTier }) {
  const [scrolled, setScrolled] = useState(false);
  const featuresRef = useRef(null);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 60);
    window.addEventListener("scroll", fn);
    return () => window.removeEventListener("scroll", fn);
  }, []);

  const scrollToFeatures = () => featuresRef.current?.scrollIntoView({ behavior: "smooth" });

  const features = [
    { icon: <Zap size={18} />, title: "Instant extraction", desc: "Upload any PDF or CSV utility bill. We pull consumption, site, and period automatically — no manual entry." },
    { icon: <BarChart2 size={18} />, title: "Emissions & trends", desc: "Scope 1 & 2 footprint, anomaly detection, forecasting, and solar-sizing — all from a single file." },
    { icon: <Shield size={18} />, title: "Audit-ready output", desc: "Every calculation is logged with a fingerprint. Download a PDF report ready for your sustainability disclosures." },
  ];

  const tiers = [
    { id: "free_trial", title: "Emissions report", desc: "Upload a bill and get your Scope 1 & 2 footprint, trends, and anomaly flags.", cta: "Get my report", featured: false },
    { id: "standard", title: "Action plan", desc: "Everything in the emissions report, plus a tiered, cited action plan for reducing your footprint.", cta: "Get my action plan", featured: true },
    { id: "premium", title: "Premium", desc: "Everything in the action plan, plus vendor matching, a custom solarpunk investment plan, and a full audit trail.", cta: "Go premium", featured: false },
  ];

  return (
    <div className="lp-root">
      <nav className={`lp-nav${scrolled ? " scrolled" : ""}`}>
        <div className="lp-brand"><div className="lp-brand-dot" /><span>IN-TELLUS</span></div>
        <div className="lp-nav-actions">
          <button className="btn btn-ghost" style={{ fontSize: 13 }} onClick={onLogin}>Log in</button>
          <button className="btn" style={{ fontSize: 13 }} onClick={onLogin}>Get started</button>
        </div>
      </nav>

      <HeroLanding onGetStarted={onLogin} onLearnMore={scrollToFeatures} />
      <DrawCircleText />

      <div ref={featuresRef}>
        <CardsFeatures />
      </div>

      <section className="lp-tiers">
        <p className="lp-section-label">Choose your output</p>
        <h2 className="lp-section-title">Pick what <b>you need</b></h2>
        <div className="lp-tier-grid">
          {tiers.map((t) => (
            <div className={`lp-tier${t.featured ? " is-featured" : ""}`} key={t.id} onClick={() => onSelectTier(t.id)}>
              {t.featured && <span className="lp-tier-badge">Most popular</span>}
              <h3>{t.title}</h3>
              <p>{t.desc}</p>
              <button className={`btn${t.featured ? "" : " btn-outline"}`} style={{ fontSize: 13, width: "100%", justifyContent: "center" }}>
                {t.cta} <ChevronRight size={14} />
              </button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

// ── AUTH ──────────────────────────────────────────────────────────────
function AuthScreen({ mode, form, onField, onSubmit, error, loading, onSwitchMode }) {
  return (
    <div className="auth-root">
      <div className="auth-card">
        <div className="auth-logo"><div className="auth-logo-dot" /><span>IN-TELLUS</span></div>
        <h2 className="auth-title">{mode === "login" ? "Welcome back" : "Create your workspace"}</h2>
        <p className="auth-sub">{mode === "login" ? "Log in to track and review your consumption data." : "Set up your company account and get started."}</p>
        <form onSubmit={onSubmit}>
          {mode === "register" && (
            <>
              <div className="form-row"><label className="form-label">Company name</label><input className="form-input" type="text" required value={form.companyName} onChange={onField("companyName")} /></div>
              <div className="form-row"><label className="form-label">Your name</label><input className="form-input" type="text" required value={form.fullName} onChange={onField("fullName")} /></div>
            </>
          )}
          <div className="form-row"><label className="form-label">Email</label><input className="form-input" type="email" required value={form.email} onChange={onField("email")} /></div>
          <div className="form-row"><label className="form-label">Password</label><input className="form-input" type="password" required value={form.password} onChange={onField("password")} /></div>
          {error && <div className="alert-error"><AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 1 }} /><span>{error}</span></div>}
          <button className="btn" type="submit" disabled={loading} style={{ width: "100%", justifyContent: "center", marginTop: 20 }}>
            {loading ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>
        <p className="auth-switch">
          {mode === "login" ? "No account? " : "Already have one? "}
          <button onClick={() => onSwitchMode(mode === "login" ? "register" : "login")}>
            {mode === "login" ? "Register" : "Log in"}
          </button>
        </p>
      </div>
    </div>
  );
}

// ── SITE SETUP ────────────────────────────────────────────────────────
function SiteSetupScreen({ sites, form, onField, onSubmit, error, loading, onContinue }) {
  return (
    <div className="setup-root">
      <div className="setup-card">
        <div style={{ marginBottom: 32 }}>
          <div className="lp-brand" style={{ marginBottom: 24 }}><div className="lp-brand-dot" /><span>IN-TELLUS</span></div>
          <h2 className="panel-title">Add your first site</h2>
          <p className="panel-sub">A site is a physical location — like "Colombo South" or "Kandy Branch". You'll map utility accounts to sites as bills come in.</p>
        </div>
        {sites.length > 0 && (
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-head"><span className="card-label">Your sites</span></div>
            {sites.map((s) => (
              <div className="mini-row" key={s.site_id}>
                <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}><MapPin size={13} style={{ color: "var(--mint)" }} />{s.site_name}</span>
                <span style={{ fontSize: 12, color: "var(--muted)" }}>{s.address || ""}</span>
              </div>
            ))}
          </div>
        )}
        <div className="card">
          <form onSubmit={onSubmit}>
            <div className="form-row"><label className="form-label">Site name</label><input className="form-input" type="text" required value={form.siteName} onChange={onField("siteName")} placeholder="e.g. Colombo South" /></div>
            <div className="form-row"><label className="form-label">Address (optional)</label><input className="form-input" type="text" value={form.siteAddress} onChange={onField("siteAddress")} /></div>
            {error && <div className="alert-error"><AlertTriangle size={15} style={{ flexShrink: 0 }} /><span>{error}</span></div>}
            <div className="actions" style={{ marginTop: 16 }}>
              <button className="btn" disabled={loading}>{loading ? "Adding…" : "Add site"}<Plus size={14} /></button>
            </div>
          </form>
        </div>
        {sites.length > 0 && (
          <div className="actions" style={{ marginTop: 16 }}>
            <button className="btn btn-ghost" onClick={onContinue}>Continue to upload</button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── APP NAV ───────────────────────────────────────────────────────────
function AppNav({ onManageSites, onHome, onLogout }) {
  return (
    <nav className="app-nav">
      <div className="app-brand"><div className="app-brand-dot" /><span>IN-TELLUS</span></div>
      <div className="app-nav-links">
        <button className="app-nav-btn" onClick={onManageSites}><MapPin size={14} />Sites</button>
        <button className="app-nav-btn" onClick={onHome}><Leaf size={14} />Home</button>
        <button className="app-nav-btn" onClick={onLogout}><LogOut size={14} />Log out</button>
      </div>
    </nav>
  );
}

// ── STEP INDICATOR ────────────────────────────────────────────────────
function StepIndicator({ current }) {
  return (
    <ol className="steps-bar" style={{ listStyle: "none" }}>
      {STEPS.map((s, i) => (
        <li key={s.id} className="step-item">
          <span className={`step-dot${s.id === current ? " is-current" : s.id < current ? " is-done" : ""}`}>
            {s.id < current ? <CheckCircle2 size={13} strokeWidth={2.5} /> : s.id}
          </span>
          <span className="step-label">{s.label}</span>
          {i < STEPS.length - 1 && <span className="step-rule" />}
        </li>
      ))}
    </ol>
  );
}

// ── UNMAPPED ACCOUNT ──────────────────────────────────────────────────
function UnmappedAccountRow({ accountNumber, resourceType, sites, mapping, onChange, onSave, onAddSiteToggle, newSiteForm, onNewSiteField, onNewSiteSave }) {
  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div className="card-head">
        <span className="card-label">New utility account</span>
        {mapping.saved && <span className="pill pill-mint">Saved</span>}
      </div>
      <p className="note" style={{ marginTop: 0, marginBottom: 16 }}>
        Account <strong style={{ color: "var(--white)" }}>{accountNumber}</strong> ({resourceType || "unknown"}) hasn't been mapped to a site yet.
      </p>
      {!mapping.saved && (
        <>
          <div className="form-row">
            <label className="form-label">Site</label>
            <select className="form-input" value={mapping.siteId || ""} onChange={(e) => onChange(accountNumber, "siteId", e.target.value)}>
              <option value="">Choose a site…</option>
              {sites.map((s) => <option key={s.site_id} value={s.site_id}>{s.site_name}</option>)}
            </select>
          </div>
          {!mapping.addingSite
            ? <button type="button" className="optional-toggle" onClick={() => onAddSiteToggle(accountNumber, true)}>+ Add a new site instead</button>
            : (
              <div className="card" style={{ background: "rgba(249,250,251,0.03)", padding: 16, marginTop: 8 }}>
                <div className="form-row"><label className="form-label">New site name</label><input className="form-input" type="text" value={newSiteForm.siteName} onChange={onNewSiteField(accountNumber, "newSiteName")} /></div>
                <div className="actions" style={{ marginTop: 0 }}>
                  <button type="button" className="btn btn-ghost" onClick={() => onAddSiteToggle(accountNumber, false)}>Cancel</button>
                  <button type="button" className="btn" onClick={() => onNewSiteSave(accountNumber)}>Create & use</button>
                </div>
              </div>
            )}
          {mapping.error && <div className="alert-error"><AlertTriangle size={15} /><span>{mapping.error}</span></div>}
          <div className="actions">
            <button className="btn" disabled={!mapping.siteId || mapping.saving} onClick={() => onSave(accountNumber, resourceType)}>
              {mapping.saving ? "Saving…" : "Save mapping"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ── ANOMALY ROW ───────────────────────────────────────────────────────
function AnomalyPeriodRow({ a }) {
  const severity = a.trigger === "pct_deviation" ? "medium" : "high";
  return (
    <div className="anomaly-row">
      <div className="anomaly-head">
        <span>{a.period}</span>
        <span className={`sev-pill sev-${severity}`}>{a.direction} baseline</span>
      </div>
      <p className="anomaly-body">
        {a.value?.toLocaleString()} vs. {a.baseline_mean?.toLocaleString()} ({a.pct_deviation != null ? `${(a.pct_deviation * 100).toFixed(1)}%` : "—"})
      </p>
    </div>
  );
}

// ── SITE REPORT CARD ──────────────────────────────────────────────────
function SiteReportCard({ report }) {
  const trend = report.trend || {};
  const flaggedAnomalies = (trend.anomalies || []).filter((a) => a.flagged);
  const renewable = report.renewable;
  const benchmark = report.benchmark_comparison;
  const explanation = typeof report.explanation === "string" ? report.explanation : null;

  return (
    <div className="card">
      <div className="card-head">
        <span className="card-label">{report.site}</span>
        <span className="pill pill-mint" style={{ textTransform: "capitalize" }}>{report.resource_type}</span>
      </div>
      {!trend.history_check?.sufficient
        ? <p className="note">{trend.history_check?.message}</p>
        : (
          <>
            {flaggedAnomalies.length > 0
              ? <>{flaggedAnomalies.map((a, i) => <AnomalyPeriodRow key={i} a={a} />)}</>
              : <p className="note">No anomalies detected.</p>}
            {trend.pattern?.pattern !== "none" && <p className="note">{trend.pattern?.message}</p>}
            {trend.forecast?.method !== "insufficient_data" && (
              <p className="note">Next period forecast: <strong style={{ color: "var(--white)" }}>{trend.forecast?.forecast_value?.toLocaleString()}</strong> ({trend.forecast?.confidence} confidence)</p>
            )}
            {trend.budget_check?.status === "over_budget" && (
              <div className="alert-warn"><AlertTriangle size={15} style={{ flexShrink: 0 }} /><span>{trend.budget_check.message}</span></div>
            )}
          </>
        )}
      {renewable && !renewable.errors?.length && (
        <div style={{ marginTop: 20, paddingTop: 20, borderTop: "1px solid var(--line)" }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.06em", color: "var(--mint)", marginBottom: 12 }}>Solar potential</p>
          <div className="sum-row"><span>System size</span><span>{renewable.sizing?.system_size_kwp} kWp</span></div>
          <div className="sum-row"><span>Usage offset</span><span>{Math.round((renewable.sizing?.actual_offset_pct || 0) * 100)}%</span></div>
          {renewable.savings_and_payback?.status === "ok"
            ? <div className="sum-row"><span>Estimated payback</span><span>{renewable.savings_and_payback.payback_years} years</span></div>
            : <p className="note">{renewable.savings_and_payback?.message}</p>}
        </div>
      )}
      {benchmark?.comparison?.status !== "not_evaluable" && benchmark?.comparison && (
        <div style={{ marginTop: 20, paddingTop: 20, borderTop: "1px solid var(--line)" }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.06em", color: "var(--mint)", marginBottom: 10 }}>Industry comparison</p>
          <p style={{ fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>{benchmark.comparison.message}</p>
        </div>
      )}
      {explanation && (
        <div style={{ marginTop: 20, paddingTop: 20, borderTop: "1px solid var(--line)" }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.06em", color: "var(--mint)", marginBottom: 10 }}>What's driving this</p>
          <p style={{ fontSize: 13, color: "var(--muted)", lineHeight: 1.65 }}>{explanation}</p>
        </div>
      )}
    </div>
  );
}

// ── AGENT 3 CARDS ─────────────────────────────────────────────────────
function downloadAuditJson(audit) {
  if (!audit) return;
  const blob = new Blob([JSON.stringify(audit, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `audit_trail_company_${audit.company_id}.json`; a.click();
  URL.revokeObjectURL(url);
}

function SolarpunkCard({ plan }) {
  return (
    <div className="card">
      <div className="card-head">
        <span className="card-label">Solarpunk plan</span>
        {plan.timeline && <span className="pill pill-mint">{plan.timeline}</span>}
      </div>
      {plan.estimated_investment != null && (
        <div className="sum-row"><span>Planned investment</span><span>LKR {Number(plan.estimated_investment).toLocaleString()}</span></div>
      )}
      {(plan.projects || []).map((p, i) => (
        <p key={i} style={{ fontSize: 14, color: "var(--white)", margin: "16px 0 0", lineHeight: 1.5 }}>{p}</p>
      ))}
      {plan.sources?.length > 0 && <p className="note">Based on: {plan.sources.map((s) => s.title).join(" · ")}</p>}
      <p className="note" style={{ marginTop: 8 }}>{plan.disclaimer}</p>
    </div>
  );
}

function VendorCard({ vendors }) {
  return (
    <div className="card">
      <div className="card-head"><span className="card-label">Vendor matching</span></div>
      {vendors.map((m, i) => (
        <div key={i} style={{ marginBottom: 16 }}>
          <p style={{ fontSize: 13, fontWeight: 600, color: "var(--white)", margin: "0 0 4px" }}>{m.category}</p>
          {m.matches.map((t, j) => <p key={j} style={{ fontSize: 13, color: "var(--muted)", margin: 0, lineHeight: 1.5 }}>{t}</p>)}
        </div>
      ))}
      <p className="note" style={{ marginTop: 0 }}>Provider names shown are fictional examples, not real businesses.</p>
    </div>
  );
}

function AuditCard({ audit }) {
  return (
    <div className="card">
      <div className="card-head">
        <span className="card-label">Audit trail</span>
        <span className="pill pill-mint">{audit.run_ids.length} runs</span>
      </div>
      <p className="note" style={{ marginTop: 0 }}>Every plan generated for your company is logged. Most recent run: #{audit.run_ids[0]}.</p>
      <button className="optional-toggle" style={{ marginTop: 8 }} onClick={() => downloadAuditJson(audit)}>Download audit trail (JSON)</button>
    </div>
  );
}

// Results screen for the proposal-only Premium flow (no utility bill).
function SolarpunkOnlyView({ result, onReset }) {
  const vendors = Array.isArray(result?.vendor_matching) ? result.vendor_matching : [];
  return (
    <div className="panel">
      <h1 className="panel-title">Your solarpunk plan</h1>
      <p className="panel-sub">Built from your project proposal.</p>
      {result?.solarpunk_plan && <SolarpunkCard plan={result.solarpunk_plan} />}
      {vendors.length > 0 && <VendorCard vendors={vendors} />}
      {result?.audit_trail && <AuditCard audit={result.audit_trail} />}
      <div className="actions"><button className="btn btn-ghost" onClick={onReset}>Start over</button></div>
    </div>
  );
}

// ── MAIN ──────────────────────────────────────────────────────────────
export default function SustainabilityApp() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [showAuth, setShowAuth] = useState(false);
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

  const [showHome, setShowHome] = useState(true);
  const [tier, setTier] = useState(null);

  const [step, setStep] = useState(1);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [records, setRecords] = useState([]);
  const [fileId, setFileId] = useState(null);
  const [accountMappings, setAccountMappings] = useState({});

  const [analysisInputs, setAnalysisInputs] = useState({ monthlyBudgetLkr: "", effectiveTariffLkrPerKwh: "", region: "mid_country", sector: "", floorAreaM2: "" });
  const [analysis, setAnalysis] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  // Agent 3 (action plan) -- standard + premium tiers only
  const [recommendation, setRecommendation] = useState(null);
  const [isRecommending, setIsRecommending] = useState(false);
  const [recommendationError, setRecommendationError] = useState(null);

  // Premium: project proposal (extracted, then confirmed by the user)
  const [proposalDraft, setProposalDraft] = useState(null);
  const [proposalWarnings, setProposalWarnings] = useState([]);
  const [isExtractingProposal, setIsExtractingProposal] = useState(false);
  const [proposalError, setProposalError] = useState(null);
  const [isBuildingSolarpunk, setIsBuildingSolarpunk] = useState(false);
  const [solarpunkOnly, setSolarpunkOnly] = useState(null);
  const [solarpunkError, setSolarpunkError] = useState(null);

  const authFetch = useCallback(async (path, options = {}, base = API_BASE) => {
    const res = await fetch(`${base}${path}`, { ...options, headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` } });
    if (res.status === 401) { localStorage.removeItem(TOKEN_KEY); setToken(null); throw new Error("Session expired. Please log in again."); }
    return res;
  }, [token]);

  const loadSites = useCallback(async () => {
    try {
      const res = await authFetch("/sites");
      if (!res.ok) return;
      const data = await res.json();
      setSites(data); setSitesLoaded(true);
      if (data.length > 0) setSiteSetupComplete(true);
    } catch { setSitesLoaded(true); }
  }, [authFetch]);

  useEffect(() => { if (token) loadSites(); }, [token, loadSites]);

  const onAuthField = (key) => (e) => setAuthForm((p) => ({ ...p, [key]: e.target.value }));
  const onSiteField = (key) => (e) => setSiteForm((p) => ({ ...p, [key]: e.target.value }));
  const onAnalField = (key) => (e) => setAnalysisInputs((p) => ({ ...p, [key]: e.target.value }));

  // Clears everything belonging to one upload -> report run.
  const resetRun = () => {
    setStep(1); setRecords([]); setFileId(null); setSelectedFile(null); setError(null);
    setAccountMappings({}); setAnalysis(null); setAnalysisError(null);
    setRecommendation(null); setRecommendationError(null);
    setProposalDraft(null); setProposalWarnings([]); setProposalError(null);
    setSolarpunkOnly(null); setSolarpunkError(null); setIsBuildingSolarpunk(false);
  };

  const handleLogin = async (e) => {
    e.preventDefault(); setAuthLoading(true); setAuthError(null);
    try {
      const body = new URLSearchParams(); body.append("username", authForm.email); body.append("password", authForm.password);
      const res = await fetch(`${API_BASE}/auth/login`, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body });
      if (!res.ok) { const b = await res.json().catch(() => ({})); throw new Error(b.detail || "Incorrect email or password"); }
      const data = await res.json();
      localStorage.setItem(TOKEN_KEY, data.access_token); setToken(data.access_token); setShowAuth(false);
    } catch (err) { setAuthError(err.message === "Failed to fetch" ? `Couldn't reach the backend.` : err.message); }
    finally { setAuthLoading(false); }
  };

  const handleRegister = async (e) => {
    e.preventDefault(); setAuthLoading(true); setAuthError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/register`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ company_name: authForm.companyName, full_name: authForm.fullName, email: authForm.email, password: authForm.password }) });
      if (!res.ok) { const b = await res.json().catch(() => ({})); throw new Error(b.detail || "Registration failed"); }
      const data = await res.json();
      localStorage.setItem(TOKEN_KEY, data.access_token); setToken(data.access_token); setShowAuth(false);
    } catch (err) { setAuthError(err.message === "Failed to fetch" ? `Couldn't reach the backend.` : err.message); }
    finally { setAuthLoading(false); }
  };

  const handleLogout = () => {
    localStorage.removeItem(TOKEN_KEY); setToken(null); setSites([]); setSitesLoaded(false);
    setSiteSetupComplete(false); setShowHome(true); setTier(null); resetRun();
    setRecords([]); setFileId(null); setSelectedFile(null); setError(null); setAnalysis(null); setShowAuth(false);
  };

  const handleAddSite = async (e) => {
    e.preventDefault(); setSiteLoading(true); setSiteError(null);
    try {
      const res = await authFetch("/sites", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ site_name: siteForm.siteName, address: siteForm.siteAddress || null }) });
      if (!res.ok) { const b = await res.json().catch(() => ({})); throw new Error(b.detail || "Failed to add site"); }
      const newSite = await res.json(); setSites((p) => [...p, newSite]); setSiteForm({ siteName: "", siteAddress: "" });
    } catch (err) { setSiteError(err.message); } finally { setSiteLoading(false); }
  };

  const handleFile = useCallback((f) => { if (!f) return; setSelectedFile(f); setError(null); }, []);
  const onDrop = useCallback((e) => { e.preventDefault(); setIsDragging(false); handleFile(e.dataTransfer.files?.[0]); }, [handleFile]);

  const runExtraction = async () => {
    if (!selectedFile) return; setIsProcessing(true); setError(null);
    try {
      const form = new FormData(); form.append("file", selectedFile);
      const res = await authFetch("/extract", { method: "POST", body: form });
      if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(body?.detail?.message || body?.detail || `Request failed (${res.status})`); }
      const data = await res.json();
      if (!data.records?.length) throw new Error("No records could be extracted.");
      if (!data.file_id) throw new Error("Agent 1 did not return a file_id.");
      setFileId(data.file_id); setRecords(data.records); setAccountMappings({}); setAnalysis(null); setAnalysisError(null); setRecommendation(null); setRecommendationError(null); setSolarpunkOnly(null); setStep(2);
    } catch (err) { setError(err.message === "Failed to fetch" ? "Couldn't reach the backend." : err.message); }
    finally { setIsProcessing(false); }
  };

  const handleProposalFile = async (file) => {
    if (!file) return;
    setIsExtractingProposal(true); setProposalError(null); setProposalWarnings([]);
    try {
      const form = new FormData(); form.append("file", file);
      const res = await authFetch("/agent3/extract-proposal", { method: "POST", body: form }, AGENT3_API_BASE);
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `Could not read the proposal (${res.status})`);
      const p = data.proposal || {};
      const name = (p.site_name || "").toLowerCase();
      const match = sites.find((s) => { const sn = s.site_name.toLowerCase(); return name && (name.includes(sn) || sn.includes(name)); });
      setProposalDraft({ budget: p.budget_lkr ?? "", siteId: match ? String(match.site_id) : "", timelineMonths: p.timeline_months ?? "", goals: p.goals_text ?? "" });
      setProposalWarnings(data.warnings || []);
    } catch (err) {
      setProposalDraft(null);
      setProposalError(err.message === "Failed to fetch" ? "Couldn't reach the backend. Is Agent 3 running?" : err.message);
    } finally { setIsExtractingProposal(false); }
  };

  const buildProposalPayload = () => ({
    budget: Number(proposalDraft.budget),
    site_id: proposalDraft.siteId || null,
    timeline_months: proposalDraft.timelineMonths ? Math.round(Number(proposalDraft.timelineMonths)) : null,
    goals_text: proposalDraft.goals || null,
  });

  const parseAgent3Error = (data, res, fallback) => {
    const d = data?.detail;
    return Array.isArray(d) ? d.map((e) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`).join("; ")
      : d?.message || (typeof d === "string" ? d : `${fallback} (${res.status})`);
  };

  const runSolarpunkOnly = async () => {
    if (!proposalDraft || !(Number(proposalDraft.budget) > 0)) return;
    setIsBuildingSolarpunk(true); setSolarpunkError(null);
    try {
      const res = await authFetch("/agent3/solarpunk", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ proposal: buildProposalPayload() }) }, AGENT3_API_BASE);
      const data = await res.json();
      if (!res.ok) throw new Error(parseAgent3Error(data, res, "Could not build the plan"));
      setSolarpunkOnly(data); setStep(3);
    } catch (err) {
      setSolarpunkError(err.message === "Failed to fetch" ? "Couldn't reach the backend. Is Agent 3 running?" : err.message);
    } finally { setIsBuildingSolarpunk(false); }
  };

  const unmappedAccounts = React.useMemo(() => {
    const seen = new Map();
    for (const r of records) {
      if (r.warnings?.some((w) => UNMAPPED_WARNING_RE.test(w) || w.includes("no site mapping")) && r.account_number && !seen.has(r.account_number)) seen.set(r.account_number, r.resource_type);
    }
    return Array.from(seen.entries()).map(([accountNumber, resourceType]) => ({ accountNumber, resourceType }));
  }, [records]);

  const allAccountsMapped = unmappedAccounts.every((a) => accountMappings[a.accountNumber]?.saved);
  const updateMapping = (acc, key, val) => setAccountMappings((p) => ({ ...p, [acc]: { ...p[acc], [key]: val } }));
  const toggleAddSite = (acc, on) => { updateMapping(acc, "addingSite", on); updateMapping(acc, "newSiteName", ""); };
  const saveNewSiteForMapping = async (acc) => {
    const name = accountMappings[acc]?.newSiteName; if (!name) return;
    try {
      const res = await authFetch("/sites", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ site_name: name }) });
      if (!res.ok) { const b = await res.json().catch(() => ({})); throw new Error(b.detail || "Failed to create site"); }
      const s = await res.json(); setSites((p) => [...p, s]); updateMapping(acc, "siteId", String(s.site_id)); updateMapping(acc, "addingSite", false);
    } catch (err) { updateMapping(acc, "error", err.message); }
  };
  const saveAccountMapping = async (acc, resourceType) => {
    const siteId = accountMappings[acc]?.siteId; if (!siteId) return;
    updateMapping(acc, "saving", true); updateMapping(acc, "error", null);
    try {
      const res = await authFetch("/accounts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ account_number: acc, site_id: Number(siteId), resource_type: resourceType || null }) });
      if (!res.ok) { const b = await res.json().catch(() => ({})); throw new Error(b.detail || "Failed to save mapping"); }
      updateMapping(acc, "saved", true);
    } catch (err) { updateMapping(acc, "error", err.message); } finally { updateMapping(acc, "saving", false); }
  };

  const runAnalysis = async () => {
    if (!fileId) { setAnalysisError("No file ID available."); return; }
    setIsAnalyzing(true); setAnalysisError(null); setRecommendation(null); setRecommendationError(null);
    try {
      const body = { file_id: fileId, monthly_budget_lkr: analysisInputs.monthlyBudgetLkr ? Number(analysisInputs.monthlyBudgetLkr) : null, effective_tariff_lkr_per_kwh: analysisInputs.effectiveTariffLkrPerKwh ? Number(analysisInputs.effectiveTariffLkrPerKwh) : null, region: analysisInputs.region || "mid_country", sector: analysisInputs.sector || null, floor_area_m2: analysisInputs.floorAreaM2 ? Number(analysisInputs.floorAreaM2) : null };
      const res = await authFetch("/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, AGENT2_API_BASE);
      const data = await res.json();
      if (!res.ok) { const errs = data?.detail?.errors; throw new Error(data?.detail?.message || (errs ? errs.join(" ") : data?.detail) || `Analysis failed (${res.status})`); }
      setAnalysis(data.result); setStep(3);
      // Agent 2 -> Agent 3 hand-off for paid tiers
      if (tier && tier !== "free_trial") runRecommendation(data.result);
    } catch (err) { setAnalysisError(err.message === "Failed to fetch" ? "Couldn't reach Agent 2." : err.message); }
    finally { setIsAnalyzing(false); }
  };

  const runRecommendation = async (analysisResult) => {
    setIsRecommending(true); setRecommendationError(null);
    try {
      const body = {
        diagnostics: analysisResult,
        tier,
        multi_site: (analysisResult.site_reports || []).length > 1,
        sl_framework_applicable: false,
        user_context: null,
        proposal: tier === "premium" && proposalDraft && Number(proposalDraft.budget) > 0 ? buildProposalPayload() : null,
      };
      const res = await authFetch("/agent3/recommend", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, AGENT3_API_BASE);
      const data = await res.json();
      if (!res.ok) throw new Error(parseAgent3Error(data, res, "Recommendation failed"));
      setRecommendation(data);
    } catch (err) {
      setRecommendationError(err.message === "Failed to fetch" ? "Couldn't reach the backend. Is Agent 3 running?" : err.message);
    } finally { setIsRecommending(false); }
  };

  const totals = records.reduce((acc, r) => { if (!r.resource_type || r.consumption == null) return acc; acc[r.resource_type] = (acc[r.resource_type] || 0) + r.consumption; return acc; }, {});
  const warningCount = records.filter((r) => r.warnings?.length > 0).length;

  const footprint = analysis?.footprint;
  const companyTotal = footprint?.company_total;
  const totalCo2eKg = companyTotal ? Math.round(companyTotal.total_kg) : 0;
  const scopeRows = [
    { label: "Fuel (Scope 1)", kg: Math.round(companyTotal?.scope1_kg || 0), color: "#0d9488" },
    { label: "Electricity (Scope 2)", kg: Math.round(companyTotal?.scope2_kg || 0), color: "rgba(13,148,136,0.4)" },
  ];
  const excludedKg = Math.round(companyTotal?.excluded_from_total_kg || 0);
  const maxScopeKg = Math.max(...scopeRows.map((r) => r.kg), excludedKg, 1);
  const suspiciousFlags = analysis?.suspicious_value_flags || [];
  const siteReports = analysis?.site_reports || [];
  const failedRecords = footprint?.failed_records || [];
  const actionPlanItems = Array.isArray(recommendation?.action_plan) ? recommendation.action_plan : [];
  const solarpunkPlan = recommendation?.solarpunk_plan || null;
  const vendorMatches = Array.isArray(recommendation?.vendor_matching) ? recommendation.vendor_matching : [];
  const auditTrail = recommendation?.audit_trail || null;
  const proposalReady = tier === "premium" && proposalDraft && Number(proposalDraft.budget) > 0;
  const proposalOnly = !selectedFile && proposalReady;
  const busy = isProcessing || isExtractingProposal || isBuildingSolarpunk;

  const downloadPdfReport = () => {
    if (!analysis) return;
    const reportSite = siteReports.length > 0 ? siteReports.map((r) => r.site).join(", ") : (records[0]?.site || "Unknown site");
    const reportPeriod = records[0]?.billing_period || "—";
    const doc = new jsPDF({ unit: "mm", format: "a4" });
    const marginX = 20, pageWidth = 210, contentWidth = pageWidth - marginX * 2;
    let y = 24;
    const C = { navy: [249,250,251], mint: [13,148,136], white: [15,23,42], muted: [100,116,139], line: [226,232,240], tan: [188,138,74] };
    const ensureSpace = (n) => { if (y + n > 280) { doc.addPage(); y = 24; } };
    const sectionTitle = (text) => { ensureSpace(14); doc.setFont("helvetica","bold"); doc.setFontSize(12); doc.setTextColor(...C.mint); doc.text(text, marginX, y); y += 3; doc.setDrawColor(...C.line); doc.line(marginX, y, marginX+contentWidth, y); y += 8; };
    const bodyLine = (text, opts={}) => { const {bold=false,color=C.white,size=10,indent=0}=opts; doc.setFont("helvetica",bold?"bold":"normal"); doc.setFontSize(size); doc.setTextColor(...color); doc.splitTextToSize(text,contentWidth-indent).forEach((l)=>{ ensureSpace(6); doc.text(l,marginX+indent,y); y+=5.5; }); };
    const kvRow = (label,value) => { ensureSpace(6); doc.setFont("helvetica","normal"); doc.setFontSize(10); doc.setTextColor(...C.muted); doc.text(label,marginX,y); doc.setFont("helvetica","bold"); doc.setTextColor(...C.white); doc.text(String(value),marginX+contentWidth,y,{align:"right"}); y+=6.5; };
    doc.setFillColor(...C.navy); doc.rect(0,0,210,297,"F");
    doc.setFont("helvetica","normal"); doc.setFontSize(9); doc.setTextColor(...C.muted); doc.text("IN-TELLUS",marginX,y); y+=8;
    doc.setFontSize(20); doc.setTextColor(...C.white); doc.text("Sustainability Report",marginX,y); y+=8;
    doc.setFontSize(11); doc.setTextColor(...C.muted); doc.text(`${reportSite}  ·  ${reportPeriod}  ·  Generated ${new Date().toLocaleDateString()}`,marginX,y); y+=12;
    sectionTitle("Emissions Summary");
    kvRow("Total emissions (Scope 1 + 2)", `${totalCo2eKg.toLocaleString()} kg CO₂e`);
    scopeRows.forEach((r)=>kvRow(r.label,`${r.kg.toLocaleString()} kg`));
    if(excludedKg>0){y+=2;bodyLine(`Plus ${excludedKg.toLocaleString()} kg from water (excluded from GHG total by policy).`,{size:9,color:C.muted});}
    y+=4;
    if(failedRecords.length>0){sectionTitle("Records Excluded");failedRecords.forEach((r)=>bodyLine(`${r.site||"Unknown"} · ${r.resource_type} · ${r.billing_period}: ${r.errors.join("; ")}`,{size:9,color:[251,146,60]}));y+=4;}
    if(suspiciousFlags.length>0){sectionTitle("Flagged For Review");suspiciousFlags.forEach((f)=>bodyLine(`• ${f}`,{size:9.5}));y+=4;}
    siteReports.forEach((report)=>{
      sectionTitle(`Site: ${report.site}`);
      const trend=report.trend;
      if(trend?.history_check&&!trend.history_check.sufficient){bodyLine(trend.history_check.message,{size:9.5,color:C.muted});}
      else if(trend){
        if(trend.pattern?.message)bodyLine(trend.pattern.message,{size:9.5});
        if(trend.forecast?.message)bodyLine(trend.forecast.message,{size:9.5,color:C.muted});
        if(trend.budget_check?.status==="over_budget")bodyLine(trend.budget_check.message,{size:9.5,color:C.tan,bold:true});
        const flagged=(trend.anomalies||[]).filter((a)=>a.flagged);
        flagged.forEach((a)=>bodyLine(`• ${a.period}: ${a.value?.toLocaleString()} (${a.direction} baseline, ${(a.pct_deviation*100).toFixed(1)}%)`,{size:9,indent:2}));
      }
      y+=2;
      if(report.renewable&&!report.renewable.errors?.length){bodyLine("Solar potential:",{bold:true,size:10});kvRow("System size",`${report.renewable.sizing.system_size_kwp} kWp`);kvRow("Usage offset",`${Math.round(report.renewable.sizing.actual_offset_pct*100)}%`);if(report.renewable.savings_and_payback?.status==="ok")kvRow("Estimated payback",`${report.renewable.savings_and_payback.payback_years} years`);y+=2;}
      if(report.benchmark_comparison?.comparison?.message){bodyLine("Benchmark comparison:",{bold:true,size:10});bodyLine(report.benchmark_comparison.comparison.message,{size:9.5});y+=2;}
      if(report.explanation&&typeof report.explanation==="string"){bodyLine("Summary:",{bold:true,size:10});bodyLine(report.explanation,{size:9.5,color:C.muted});}
      y+=6;
    });
    if(actionPlanItems.length>0){sectionTitle("Action Plan");actionPlanItems.forEach((item)=>{bodyLine((item.tier||"").replace("_"," ").toUpperCase(),{bold:true,size:9,color:C.mint});bodyLine(item.action,{size:9.5});bodyLine(item.reasoning,{size:9,color:C.muted});y+=3;});y+=2;}
    if(solarpunkPlan){sectionTitle("Solarpunk Plan");if(solarpunkPlan.estimated_investment!=null)kvRow("Planned investment",`LKR ${Number(solarpunkPlan.estimated_investment).toLocaleString()}`);if(solarpunkPlan.timeline)kvRow("Timeline",solarpunkPlan.timeline);y+=2;solarpunkPlan.projects.forEach((p)=>bodyLine(`• ${p}`,{size:9.5}));bodyLine(solarpunkPlan.disclaimer,{size:8.5,color:C.muted});y+=4;}
    if(vendorMatches.length>0){sectionTitle("Vendor Matching");vendorMatches.forEach((m)=>{bodyLine(m.category,{bold:true,size:9.5});m.matches.forEach((t)=>bodyLine(t,{size:9,color:C.muted}));y+=2;});bodyLine("Provider names shown are fictional examples, not real businesses.",{size:8.5,color:C.muted});y+=4;}
    if(auditTrail){bodyLine(`Audit trail: ${auditTrail.run_ids.length} runs logged for this company.`,{size:8.5,color:C.muted});y+=2;}
    ensureSpace(10); doc.setDrawColor(...C.line); doc.line(marginX,y,marginX+contentWidth,y); y+=6;
    doc.setFont("helvetica","normal"); doc.setFontSize(8); doc.setTextColor(...C.muted); doc.text(`Report ID: ${analysis.audit_fingerprint||"n/a"}`,marginX,y);
    doc.save(`intellus_report_${reportSite.replace(/[^a-z0-9]+/gi,"_").toLowerCase()}.pdf`);
  };

  // ── ROUTING ─────────────────────────────────────────────────────────
  if (showAuth || (!token && showAuth)) {
    return (
      <>
        <style>{CSS}</style>
        <AuthScreen mode={authMode} form={authForm} onField={onAuthField}
          onSubmit={authMode === "login" ? handleLogin : handleRegister}
          error={authError} loading={authLoading}
          onSwitchMode={(m) => { setAuthMode(m); setAuthError(null); }} />
      </>
    );
  }

  if (!token) {
    return (
      <>
        <style>{CSS}</style>
        <LandingPage
          onLogin={() => { setShowAuth(true); setAuthMode("login"); }}
          onSelectTier={(t) => { setTier(t); setShowAuth(true); setAuthMode("login"); }}
        />
      </>
    );
  }

  if (!sitesLoaded) {
    return (
      <>
        <style>{CSS}</style>
        <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--navy)" }}>
          <p style={{ color: "var(--muted)", fontSize: 14 }}>Loading…</p>
        </div>
      </>
    );
  }

  if (!siteSetupComplete || manageSitesOpen) {
    return (
      <>
        <style>{CSS}</style>
        <SiteSetupScreen sites={sites} form={siteForm} onField={onSiteField} onSubmit={handleAddSite}
          error={siteError} loading={siteLoading}
          onContinue={() => { setSiteSetupComplete(true); setManageSitesOpen(false); }} />
      </>
    );
  }

  if (showHome) {
    return (
      <>
        <style>{CSS}</style>
        <LandingPage
          onLogin={() => {}}
          onSelectTier={(t) => { setTier(t); setShowHome(false); }}
        />
        <AppNav
          onManageSites={() => setManageSitesOpen(true)}
          onHome={() => { setShowHome(true); resetRun(); }}
          onLogout={handleLogout}
        />
      </>
    );
  }

  return (
    <>
      <style>{CSS}</style>
      <div className="app-root">
        <AppNav
          onManageSites={() => setManageSitesOpen(true)}
          onHome={() => { setShowHome(true); resetRun(); }}
          onLogout={handleLogout}
        />
        <div className="app-body">
          <StepIndicator current={step} />

          {step === 1 && (
            <div className="panel">
              <h1 className="panel-title">{tier === "premium" ? "Plan your project" : "Add a utility bill"}</h1>
              <p className="panel-sub">{tier === "premium"
                ? "Upload your project proposal and we'll build a solarpunk plan around it. You can also add a utility bill for your emissions report and action plan."
                : "Upload an electricity, water, or fuel bill. We'll extract the consumption data automatically."}</p>
              {tier === "premium" && (
                <div className="card" style={{ marginBottom: 24 }}>
                  <div className="card-head"><span className="card-label">Project proposal</span></div>
                  <p className="note" style={{ marginTop: 0, marginBottom: 12 }}>Upload a proposal (PDF or CSV) and we'll build a solarpunk plan around it.</p>
                  <input type="file" accept=".pdf,.csv" onChange={(e) => handleProposalFile(e.target.files?.[0])} />
                  {isExtractingProposal && <p className="note">Reading your proposal…</p>}
                  {proposalError && <div className="alert-error"><AlertTriangle size={15} style={{ flexShrink: 0 }} /><span>{proposalError}</span></div>}
                  {proposalDraft && (
                    <div style={{ marginTop: 16 }}>
                      <p className="note" style={{ marginTop: 0 }}>Please check these details before continuing.</p>
                      {proposalWarnings.map((w, i) => <p key={i} className="note" style={{ color: "var(--danger)" }}>{w}</p>)}
                      <div className="field-grid">
                        <div className="form-row" style={{ marginBottom: 0 }}><label className="form-label">Budget (LKR)</label><input className="form-input" type="number" min="0" value={proposalDraft.budget} onChange={(e) => setProposalDraft((d) => ({ ...d, budget: e.target.value }))} /></div>
                        <div className="form-row" style={{ marginBottom: 0 }}><label className="form-label">Timeline (months)</label><input className="form-input" type="number" min="0" value={proposalDraft.timelineMonths} onChange={(e) => setProposalDraft((d) => ({ ...d, timelineMonths: e.target.value }))} /></div>
                        <div className="form-row" style={{ marginBottom: 0 }}><label className="form-label">Site</label>
                          <select className="form-input" value={proposalDraft.siteId} onChange={(e) => setProposalDraft((d) => ({ ...d, siteId: e.target.value }))}>
                            <option value="">Not specified</option>
                            {sites.map((s) => <option key={s.site_id} value={s.site_id}>{s.site_name}</option>)}
                          </select>
                        </div>
                      </div>
                      <div className="form-row" style={{ marginTop: 16, marginBottom: 0 }}><label className="form-label">Goals</label><textarea className="form-input" rows={3} value={proposalDraft.goals} onChange={(e) => setProposalDraft((d) => ({ ...d, goals: e.target.value }))} /></div>
                    </div>
                  )}
                </div>
              )}
              <div className={`dropzone${isDragging ? " dragging" : ""}`}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)} onDrop={onDrop}
                onClick={() => document.getElementById("ss-file-input").click()}
                role="button" tabIndex={0}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") document.getElementById("ss-file-input").click(); }}>
                <div className="dropzone-icon"><Upload size={20} /></div>
                <p className="dropzone-title">{tier === "premium" ? "Optional: add a utility bill for your emissions report and action plan" : "Drag a file here, or click to browse"}</p>
                <p className="dropzone-hint">PDF or CSV, up to 10 MB</p>
                <input id="ss-file-input" type="file" accept=".pdf,.csv" style={{ display: "none" }} onChange={(e) => handleFile(e.target.files?.[0])} />
                {selectedFile && <div className="file-chip"><FileText size={14} />{selectedFile.name}</div>}
              </div>
              {error && <div className="alert-error"><AlertTriangle size={15} style={{ flexShrink: 0 }} /><span>{error}</span></div>}
              <div className="actions">
                {solarpunkError && <span style={{ fontSize: 13, color: "var(--danger)", alignSelf: "center" }}>{solarpunkError}</span>}
                <button className="btn" disabled={(!selectedFile && !proposalReady) || busy} onClick={selectedFile ? runExtraction : runSolarpunkOnly}>
                  {isBuildingSolarpunk ? "Building your solarpunk plan…" : isProcessing ? "Reading file…" : proposalOnly ? "Build my solarpunk plan" : "Continue"}{!busy && <ChevronRight size={15} />}
                </button>
              </div>
            </div>
          )}

          {step === 2 && records.length > 0 && (
            <div className="panel">
              <h1 className="panel-title">What we found</h1>
              <p className="panel-sub">{records.length} record{records.length !== 1 ? "s" : ""} extracted. Review before calculating emissions.</p>

              {unmappedAccounts.map(({ accountNumber, resourceType }) => (
                <UnmappedAccountRow key={accountNumber} accountNumber={accountNumber} resourceType={resourceType} sites={sites}
                  mapping={accountMappings[accountNumber] || {}} onChange={updateMapping} onSave={saveAccountMapping}
                  onAddSiteToggle={toggleAddSite} newSiteForm={{ siteName: accountMappings[accountNumber]?.newSiteName || "" }}
                  onNewSiteField={(acc, key) => (e) => updateMapping(acc, key, e.target.value)} onNewSiteSave={saveNewSiteForMapping} />
              ))}

              {records.length === 1 ? (
                <div className="card">
                  <div className="card-head">
                    <span className="pill pill-mint">{Math.round((records[0].confidence || 0) * 100)}% confident</span>
                    <span style={{ fontSize: 12, color: "var(--muted)" }}>{selectedFile?.name}</span>
                  </div>
                  <div className="field-grid">
                    <div className="field"><label>Resource type</label><div style={{ textTransform: "capitalize" }}>{records[0].resource_type}</div></div>
                    <div className="field"><label>Site</label><div>{records[0].site || "—"}</div></div>
                    <div className="field"><label>Consumption</label><div>{records[0].consumption?.toLocaleString()} {records[0].unit}</div></div>
                    <div className="field"><label>Billing period</label><div>{records[0].billing_period || "—"}</div></div>
                  </div>
                  {records[0].warnings?.filter((w) => !w.includes("no site mapping") && !/^(previous_reading|current_reading|amount_lkr)/.test(w)).length > 0 && (
                    <div className="alert-warn"><AlertTriangle size={15} style={{ flexShrink: 0 }} /><span>{records[0].warnings.filter((w) => !w.includes("no site mapping") && !/^(previous_reading|current_reading|amount_lkr)/.test(w)).join(" ")}</span></div>
                  )}
                </div>
              ) : (
                <>
                  <div className="card">
                    <div className="sum-row"><span>File</span><span>{selectedFile?.name}</span></div>
                    <div className="sum-row"><span>Records</span><span>{records.length}</span></div>
                    <div className="sum-row"><span>Flagged</span><span>{warningCount}</span></div>
                    {Object.entries(totals).map(([type, amount]) => (
                      <div className="sum-row" key={type}>
                        <span style={{ textTransform: "capitalize" }}>{type} total</span>
                        <span>{amount.toLocaleString(undefined, { maximumFractionDigits: 1 })} {UNIT_LABELS[type] || ""}</span>
                      </div>
                    ))}
                  </div>
                  <div className="card">
                    <div className="card-head"><span className="card-label">First 5 records</span></div>
                    {records.slice(0, 5).map((r, i) => (
                      <div className="mini-row" key={i}>
                        <span style={{ fontSize: 13 }}>{r.fuel_type || r.resource_type || "unknown"} · {r.site || "unknown site"}</span>
                        <span style={{ fontSize: 13, color: "var(--muted)" }}>
                          {r.consumption != null ? `${r.consumption} ${r.unit || ""}` : "—"}
                          {r.warnings?.length > 0 && <AlertTriangle size={12} style={{ marginLeft: 6, verticalAlign: -2, color: "var(--danger)" }} />}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              )}

              <div className="card">
                <div className="card-head"><span className="card-label">Optional details</span><span style={{ fontSize: 12, color: "var(--muted)" }}>Improves analysis</span></div>
                <div className="field-grid">
                  <div className="form-row" style={{ marginBottom: 0 }}><label className="form-label">Monthly budget (LKR)</label><input className="form-input" type="number" min="0" value={analysisInputs.monthlyBudgetLkr} onChange={onAnalField("monthlyBudgetLkr")} placeholder="e.g. 150000" /></div>
                  <div className="form-row" style={{ marginBottom: 0 }}><label className="form-label">Electricity rate (LKR/kWh)</label><input className="form-input" type="number" min="0" step="0.01" value={analysisInputs.effectiveTariffLkrPerKwh} onChange={onAnalField("effectiveTariffLkrPerKwh")} placeholder="Auto-estimated" /></div>
                  <div className="form-row" style={{ marginBottom: 0 }}><label className="form-label">Region</label><select className="form-input" value={analysisInputs.region} onChange={onAnalField("region")}>{REGION_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></div>
                  <div className="form-row" style={{ marginBottom: 0 }}><label className="form-label">Sector</label><select className="form-input" value={analysisInputs.sector} onChange={onAnalField("sector")}>{SECTOR_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></div>
                  {analysisInputs.sector && <div className="form-row" style={{ marginBottom: 0 }}><label className="form-label">Floor area (m²)</label><input className="form-input" type="number" min="0" value={analysisInputs.floorAreaM2} onChange={onAnalField("floorAreaM2")} /></div>}
                </div>
              </div>

              {analysisError && <div className="alert-error"><AlertTriangle size={15} style={{ flexShrink: 0 }} /><span>{analysisError}</span></div>}
              <div className="actions">
                <button className="btn btn-ghost" onClick={() => setStep(1)}>Back</button>
                <button className="btn" disabled={isAnalyzing || !allAccountsMapped} onClick={() => runAnalysis()}>
                  {isAnalyzing ? "Analyzing…" : "Calculate emissions"}{!isAnalyzing && <ChevronRight size={15} />}
                </button>
              </div>
            </div>
          )}

          {step === 3 && !analysis && solarpunkOnly && <SolarpunkOnlyView result={solarpunkOnly} onReset={resetRun} />}

          {step === 3 && analysis && (
            <div className="panel">
              <h1 className="panel-title">Your footprint</h1>
              <p className="panel-sub">{analysis.resource_type} — across {siteReports.length} site{siteReports.length === 1 ? "" : "s"}.</p>

              <div className="hero-num">
                <p className="hero-num-label">Total emissions (Scope 1 + 2)</p>
                <span className="hero-num-value">{totalCo2eKg.toLocaleString()}<span className="hero-num-unit">kg CO₂e</span></span>
              </div>

              <div className="card">
                {scopeRows.map((r) => (
                  <div className="bar-row" key={r.label}>
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>{r.label}</span>
                    <div className="bar-track"><div className="bar-fill" style={{ width: `${(r.kg / maxScopeKg) * 100}%`, background: r.color }} /></div>
                    <span className="bar-val">{r.kg.toLocaleString()} kg</span>
                  </div>
                ))}
                {excludedKg > 0 && (
                  <div className="bar-row">
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>Water (not in total)</span>
                    <div className="bar-track"><div className="bar-fill" style={{ width: `${(excludedKg / maxScopeKg) * 100}%`, background: "rgba(152,255,235,0.25)" }} /></div>
                    <span className="bar-val">{excludedKg.toLocaleString()} kg</span>
                  </div>
                )}
              </div>

              {suspiciousFlags.length > 0 && (
                <div className="card">
                  <div className="card-head"><span className="card-label">Unusual values flagged</span><span className="pill pill-warn">{suspiciousFlags.length}</span></div>
                  {suspiciousFlags.map((f, i) => <p key={i} className="note" style={{ marginBottom: 8 }}>{f}</p>)}
                </div>
              )}

              {failedRecords.length > 0 && (
                <div className="alert-warn">
                  <AlertTriangle size={15} style={{ flexShrink: 0 }} />
                  <div>
                    <span>{failedRecords.length} record{failedRecords.length === 1 ? "" : "s"} couldn't be included due to data issues.</span>
                    {failedRecords.map((fr, i) => <div key={i} style={{ marginTop: 6, fontSize: 12, color: "var(--muted)" }}>{fr.site || "unknown"} · {fr.resource_type} · {fr.billing_period}: {(fr.errors || []).join("; ")}</div>)}
                  </div>
                </div>
              )}

              {siteReports.map((report, i) => <SiteReportCard key={i} report={report} />)}

              {tier && tier !== "free_trial" && (
                <div className="card">
                  <div className="card-head"><span className="card-label">Action plan</span></div>
                  {isRecommending && <p className="note" style={{ marginTop: 0 }}>Generating your action plan…</p>}
                  {recommendationError && (
                    <div className="alert-error" style={{ marginTop: 0 }}>
                      <AlertTriangle size={15} style={{ flexShrink: 0 }} />
                      <div>
                        <span>{recommendationError}</span>
                        <div style={{ marginTop: 6 }}><button className="optional-toggle" disabled={isRecommending} onClick={() => runRecommendation(analysis)}>Try again</button></div>
                      </div>
                    </div>
                  )}
                  {!isRecommending && !recommendationError && recommendation && actionPlanItems.length === 0 && (
                    <p className="note" style={{ marginTop: 0 }}>No actions were returned for this report.</p>
                  )}
                  {actionPlanItems.map((item, i) => {
                    const impact = (item.estimated_impact || "").toLowerCase();
                    const showImpact = impact && !impact.includes("not quantified") && !impact.includes("not applicable");
                    return (
                      <div key={i} style={{ marginBottom: 16, paddingBottom: 16, borderBottom: i < actionPlanItems.length - 1 ? "1px solid var(--line)" : "none" }}>
                        <span className="pill pill-mint" style={{ marginBottom: 8, display: "inline-block", textTransform: "capitalize" }}>{(item.tier || "").replace("_", " ")}</span>
                        <p style={{ fontSize: 14, color: "var(--white)", margin: "0 0 6px", lineHeight: 1.5 }}>{item.action}</p>
                        <p style={{ fontSize: 13, color: "var(--muted)", margin: "0 0 6px", lineHeight: 1.5 }}>{item.reasoning}</p>
                        {showImpact && <p style={{ fontSize: 12, color: "var(--muted)", margin: 0 }}>Estimated impact: {item.estimated_impact}</p>}
                      </div>
                    );
                  })}
                </div>
              )}

              {tier === "premium" && !isRecommending && recommendation && (
                <>
                  {solarpunkPlan ? <SolarpunkCard plan={solarpunkPlan} /> : (
                    <div className="card">
                      <span className="card-label">Solarpunk plan</span>
                      <p className="note">Add a project proposal on the upload step to get a solarpunk plan built around your budget and goals.</p>
                    </div>
                  )}
                  {vendorMatches.length > 0 && <VendorCard vendors={vendorMatches} />}
                  {auditTrail && <AuditCard audit={auditTrail} />}
                </>
              )}

              <div className="actions">
                <button className="btn btn-ghost" onClick={resetRun}>Add another file</button>
                {analysis && <button className="btn" onClick={downloadPdfReport}><Download size={15} />Download PDF</button>}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}