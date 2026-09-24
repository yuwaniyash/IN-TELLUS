r"""
apply_proposal_flow.py -- makes the Premium flow work WITHOUT a utility bill.

What it changes in SustainabilityApp.jsx:
  1. Premium: the project proposal is the main upload (moved to the top);
     the bill box becomes an optional add-on.
  2. Adds a "Build my solarpunk plan" button that works with a proposal alone
     (calls the new /agent3/solarpunk endpoint).
  3. Adds a results screen for the proposal-only plan (plan, vendors, audit).
  The bill flow (with or without a proposal) is left as it is.

Usage:
    python apply_proposal_flow.py path\to\SustainabilityApp.jsx

All-or-nothing: if any spot can't be found it changes NOTHING and says which.
A backup (.bak) is saved first. Safe to run twice.
"""
import re
import sys
import shutil
from pathlib import Path

STATES = r'''
  const [isBuildingSolarpunk, setIsBuildingSolarpunk] = useState(false);
  const [solarpunkOnly, setSolarpunkOnly] = useState(null); // proposal-only result (no bill)
  const [solarpunkError, setSolarpunkError] = useState(null);'''

RESET_LINES = r'''
    setSolarpunkOnly(null);
    setSolarpunkError(null);
    setIsBuildingSolarpunk(false);
  '''

RUN_FN = r'''const runSolarpunkOnly = async () => {
    if (!proposalDraft || !(Number(proposalDraft.budget) > 0)) return;
    setIsBuildingSolarpunk(true);
    setSolarpunkError(null);
    try {
      const body = {
        proposal: {
          budget: Number(proposalDraft.budget),
          site_id: proposalDraft.siteId || null,
          timeline_months: proposalDraft.timelineMonths ? Math.round(Number(proposalDraft.timelineMonths)) : null,
          goals_text: proposalDraft.goals || null,
        },
      };
      const res = await authFetch(
        "/agent3/solarpunk",
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
        AGENT3_API_BASE
      );
      const data = await res.json();
      if (!res.ok) {
        const d = data?.detail;
        const msg = Array.isArray(d)
          ? d.map((e) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`).join("; ")
          : d?.message || (typeof d === "string" ? d : `Could not build the plan (${res.status})`);
        throw new Error(msg);
      }
      setSolarpunkOnly(data);
      setStep(3);
    } catch (err) {
      setSolarpunkError(err.message === "Failed to fetch" ? "Couldn't reach the backend. Is Agent 3 running?" : err.message);
    } finally {
      setIsBuildingSolarpunk(false);
    }
  };

  '''

COMPONENT = r'''// Results screen for the proposal-only Premium flow (no utility bill).
function SolarpunkOnlyView({ result, onReset }) {
  const plan = result?.solarpunk_plan;
  const vendors = Array.isArray(result?.vendor_matching) ? result.vendor_matching : [];
  const audit = result?.audit_trail;

  const downloadAudit = () => {
    if (!audit) return;
    const blob = new Blob([JSON.stringify(audit, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit_trail_company_${audit.company_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="ss-panel">
      <h1 className="ss-h1">Your solarpunk plan</h1>
      <p className="ss-sub">Built from your project proposal.</p>

      {plan && (
        <div className="ss-card">
          <div className="ss-card-head">
            <span style={{ fontSize: 15, fontWeight: 500, color: "var(--ink)" }}>Solarpunk plan</span>
            {plan.timeline && <span className="ss-pill">{plan.timeline}</span>}
          </div>
          {plan.estimated_investment != null && (
            <div className="ss-summary-row">
              <span>Planned investment</span>
              <span>LKR {Number(plan.estimated_investment).toLocaleString()}</span>
            </div>
          )}
          {plan.projects.map((p, i) => (
            <p key={i} style={{ fontSize: 14, color: "var(--ink)", margin: "16px 0 0", lineHeight: 1.5 }}>{p}</p>
          ))}
          {plan.sources?.length > 0 && (
            <p className="ss-optional-note">Based on: {plan.sources.map((s) => s.title).join(" \u00b7 ")}</p>
          )}
          <p className="ss-optional-note" style={{ marginTop: 8 }}>{plan.disclaimer}</p>
        </div>
      )}

      {vendors.length > 0 && (
        <div className="ss-card">
          <div className="ss-card-head">
            <span style={{ fontSize: 15, fontWeight: 500, color: "var(--ink)" }}>Vendor matching</span>
          </div>
          {vendors.map((m, i) => (
            <div key={i} style={{ marginBottom: 16 }}>
              <p style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)", margin: "0 0 4px" }}>{m.category}</p>
              {m.matches.map((text, j) => (
                <p key={j} style={{ fontSize: 13, color: "var(--ink-soft)", margin: 0, lineHeight: 1.5 }}>{text}</p>
              ))}
            </div>
          ))}
          <p className="ss-optional-note" style={{ marginTop: 0 }}>
            Provider names shown are fictional examples, not real businesses.
          </p>
        </div>
      )}

      {audit && (
        <div className="ss-card">
          <div className="ss-card-head">
            <span style={{ fontSize: 15, fontWeight: 500, color: "var(--ink)" }}>Audit trail</span>
            <span className="ss-pill">{audit.run_ids.length} runs</span>
          </div>
          <p className="ss-optional-note" style={{ marginTop: 0 }}>
            Every plan generated for your company is logged. Most recent run: #{audit.run_ids[0]}.
          </p>
          <button className="ss-optional-toggle" style={{ marginTop: 8 }} onClick={downloadAudit}>
            Download audit trail (JSON)
          </button>
        </div>
      )}

      <div className="ss-actions">
        <button className="ss-btn ss-btn-ghost" onClick={onReset}>Start over</button>
      </div>
    </div>
  );
}

'''

RENDER_VIEW = r'''{step === 3 && !analysis && solarpunkOnly && (
              <SolarpunkOnlyView result={solarpunkOnly} onReset={resetRun} />
            )}

            '''

H1_NEW = r'''<h1 className="ss-h1">{tier === "premium" ? "Plan your project" : "Add a utility bill or usage log"}</h1>'''

SUB_NEW = r'''<p className="ss-sub">
                  {tier === "premium"
                    ? "Upload your project proposal and we'll build a solarpunk plan around it. You can also add a utility bill if you want your emissions report and action plan too."
                    : "Upload an electricity bill, water bill, or fuel transaction log. We'll pull out the consumption data and build your report automatically."}
                </p>'''

DROPZONE_TITLE_NEW = r'''<p className="ss-dropzone-title">{tier === "premium" ? "Optional: add a utility bill for your emissions report and action plan" : "Drag a file here, or click to browse"}</p>'''

BUTTON_NEW = r'''{solarpunkError && (
                    <span style={{ fontSize: 13, color: "var(--tan)", alignSelf: "center" }}>{solarpunkError}</span>
                  )}
                  {(() => {
                    const proposalReady = tier === "premium" && proposalDraft && Number(proposalDraft.budget) > 0;
                    const proposalOnly = !selectedFile && proposalReady;
                    const busy = isProcessing || isExtractingProposal || isBuildingSolarpunk;
                    return (
                      <button
                        className="ss-btn"
                        disabled={(!selectedFile && !proposalReady) || busy}
                        onClick={selectedFile ? runExtraction : runSolarpunkOnly}
                      >
                        {isBuildingSolarpunk
                          ? "Building your solarpunk plan\u2026"
                          : isProcessing
                            ? (isAnalyzing ? "Calculating emissions\u2026" : "Reading file\u2026")
                            : proposalOnly ? "Build my solarpunk plan" : "Continue"}
                        {!busy && <ChevronRight size={15} />}
                      </button>
                    );
                  })()}'''


def find_one(pattern, src, name, flags=0):
    ms = list(re.finditer(pattern, src, flags))
    if len(ms) != 1:
        sys.exit(f"Could not apply '{name}': expected 1 match, found {len(ms)}. NOTHING was changed.")
    return ms[0]


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    path = Path(sys.argv[1])
    src = path.read_text(encoding="utf-8")

    if "runSolarpunkOnly" in src:
        print("Already applied. Nothing changed.")
        return

    # 1. state
    m = find_one(r"const \[proposalError, setProposalError\] = useState\(null\);", src, "proposal state")
    src = src[:m.end()] + STATES + src[m.end():]

    # 2. resetRun
    m = find_one(r"setProposalWarnings\(\[\]\);\s*setProposalError\(null\);\s*\};", src, "resetRun")
    text = m.group(0)
    idx = text.rfind("};")
    new = text[:idx].rstrip() + RESET_LINES + "};"
    src = src[:m.start()] + new + src[m.end():]

    # 3. runSolarpunkOnly, right before runExtraction
    m = find_one(r"const runExtraction = async \(\) => \{", src, "runExtraction")
    src = src[:m.start()] + RUN_FN + src[m.start():]

    # 4. results component, right before the main component
    m = find_one(r"export default function SustainabilityApp\(\) \{", src, "main component")
    src = src[:m.start()] + COMPONENT + src[m.start():]

    # 5. render the proposal-only results before the normal Step 3
    m = find_one(r"\{step === 3 && analysis && \(", src, "Step 3 block")
    src = src[:m.start()] + RENDER_VIEW + src[m.start():]

    # 6. Premium headings and dropzone label
    m = find_one(r'<h1 className="ss-h1">Add a utility bill or usage log</h1>', src, "Step 1 heading")
    src = src[:m.start()] + H1_NEW + src[m.end():]

    m = find_one(r'<p className="ss-sub">Upload an electricity bill[^<]*</p>', src, "Step 1 subtitle")
    src = src[:m.start()] + SUB_NEW + src[m.end():]

    m = find_one(r'<p className="ss-dropzone-title">Drag a file here, or click to browse</p>', src, "dropzone title")
    src = src[:m.start()] + DROPZONE_TITLE_NEW + src[m.end():]

    # 7. move the proposal card above the bill dropzone, drop its "Optional" tag
    block_re = (
        r'\{tier === "premium" && \(\s*<div className="ss-card" style=\{\{ marginTop: 16 \}\}>\s*'
        r'<div className="ss-card-head">\s*<span[^>]*>Project proposal</span>[\s\S]*?\)\}\s*'
        r'(?=\{error && <div className="ss-error">)'
    )
    m = find_one(block_re, src, "proposal card")
    block = m.group(0).strip()
    src = src[:m.start()] + src[m.end():]
    block = block.replace("marginTop: 16", "marginBottom: 24", 1)
    block = re.sub(r'\s*<span style=\{\{ fontSize: 12, color: "var\(--ink-soft\)" \}\}>Optional</span>', "", block, count=1)
    m = find_one(r'<div\s+className=\{"ss-dropzone"', src, "bill dropzone")
    src = src[:m.start()] + block + "\n\n                " + src[m.start():]

    # 8. the Continue button
    m = find_one(
        r'<button\s+className="ss-btn"\s+disabled=\{!selectedFile \|\| isProcessing[^}]*\}\s+onClick=\{runExtraction\}>[\s\S]*?</button>',
        src, "Continue button",
    )
    src = src[:m.start()] + BUTTON_NEW + src[m.end():]

    shutil.copyfile(path, str(path) + ".proposalflow.bak")
    path.write_text(src, encoding="utf-8")
    print(f"Done. Backup saved as {path}.proposalflow.bak")


if __name__ == "__main__":
    main()
