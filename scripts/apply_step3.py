r"""
apply_step3.py -- adds the Premium result cards (solarpunk plan, vendor
matching, audit trail) and the PDF sections to SustainabilityApp.jsx.

Usage:
    python apply_step3.py path\to\SustainabilityApp.jsx

Makes a backup (SustainabilityApp.jsx.bak) first. Safe to run twice:
it does nothing if the changes are already there.
"""
import sys
import shutil
from pathlib import Path

HELPERS = r'''
  const solarpunkPlan = recommendation?.solarpunk_plan || null;
  const vendorMatches = Array.isArray(recommendation?.vendor_matching) ? recommendation.vendor_matching : [];
  const auditTrail = recommendation?.audit_trail || null;

  const downloadAuditTrail = () => {
    if (!auditTrail) return;
    const blob = new Blob([JSON.stringify(auditTrail, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit_trail_company_${auditTrail.company_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };
'''

CARDS = r'''                {tier === "premium" && !isRecommending && recommendation && (
                  <>
                    {solarpunkPlan ? (
                      <div className="ss-card">
                        <div className="ss-card-head">
                          <span style={{ fontSize: 15, fontWeight: 500, color: "var(--ink)" }}>Solarpunk plan</span>
                          {solarpunkPlan.timeline && <span className="ss-pill">{solarpunkPlan.timeline}</span>}
                        </div>
                        {solarpunkPlan.estimated_investment != null && (
                          <div className="ss-summary-row">
                            <span>Planned investment</span>
                            <span>LKR {Number(solarpunkPlan.estimated_investment).toLocaleString()}</span>
                          </div>
                        )}
                        {solarpunkPlan.projects.map((p, i) => (
                          <p key={i} style={{ fontSize: 14, color: "var(--ink)", margin: "16px 0 0", lineHeight: 1.5 }}>{p}</p>
                        ))}
                        {solarpunkPlan.sources?.length > 0 && (
                          <p className="ss-optional-note">
                            Based on: {solarpunkPlan.sources.map((s) => s.title).join(" · ")}
                          </p>
                        )}
                        <p className="ss-optional-note" style={{ marginTop: 8 }}>{solarpunkPlan.disclaimer}</p>
                      </div>
                    ) : (
                      <div className="ss-card">
                        <span style={{ fontSize: 15, fontWeight: 500, color: "var(--ink)" }}>Solarpunk plan</span>
                        <p className="ss-optional-note">
                          Add a project proposal on the upload step to get a solarpunk plan built around your budget and goals.
                        </p>
                      </div>
                    )}

                    {vendorMatches.length > 0 && (
                      <div className="ss-card">
                        <div className="ss-card-head">
                          <span style={{ fontSize: 15, fontWeight: 500, color: "var(--ink)" }}>Vendor matching</span>
                        </div>
                        {vendorMatches.map((m, i) => (
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

                    {auditTrail && (
                      <div className="ss-card">
                        <div className="ss-card-head">
                          <span style={{ fontSize: 15, fontWeight: 500, color: "var(--ink)" }}>Audit trail</span>
                          <span className="ss-pill">{auditTrail.run_ids.length} runs</span>
                        </div>
                        <p className="ss-optional-note" style={{ marginTop: 0 }}>
                          Every plan generated for your company is logged. Most recent run: #{auditTrail.run_ids[0]}.
                        </p>
                        <button className="ss-optional-toggle" style={{ marginTop: 8 }} onClick={downloadAuditTrail}>
                          Download audit trail (JSON)
                        </button>
                      </div>
                    )}
                  </>
                )}

'''

PDF = r'''    // --- Action plan (Standard and Premium) ---
    if (actionPlanItems.length > 0) {
      sectionTitle("Action Plan");
      actionPlanItems.forEach((item) => {
        bodyLine((item.tier || "").replace("_", " ").toUpperCase(), { bold: true, size: 9, color: COLOR.forest });
        bodyLine(item.action, { size: 9.5 });
        bodyLine(item.reasoning, { size: 9, color: COLOR.inkSoft });
        y += 3;
      });
      y += 2;
    }

    // --- Solarpunk plan (Premium) ---
    if (solarpunkPlan) {
      sectionTitle("Solarpunk Plan");
      if (solarpunkPlan.estimated_investment != null) {
        keyValueRow("Planned investment", `LKR ${Number(solarpunkPlan.estimated_investment).toLocaleString()}`);
      }
      if (solarpunkPlan.timeline) keyValueRow("Timeline", solarpunkPlan.timeline);
      y += 2;
      solarpunkPlan.projects.forEach((p) => bodyLine(`\u2022 ${p}`, { size: 9.5 }));
      bodyLine(solarpunkPlan.disclaimer, { size: 8.5, color: COLOR.inkSoft });
      y += 4;
    }

    // --- Vendor matching (Premium) ---
    if (vendorMatches.length > 0) {
      sectionTitle("Vendor Matching");
      vendorMatches.forEach((m) => {
        bodyLine(m.category, { bold: true, size: 9.5 });
        m.matches.forEach((text) => bodyLine(text, { size: 9, color: COLOR.inkSoft }));
        y += 2;
      });
      bodyLine("Provider names shown are fictional examples, not real businesses.", { size: 8.5, color: COLOR.inkSoft });
      y += 4;
    }

    if (auditTrail) {
      bodyLine(`Audit trail: ${auditTrail.run_ids.length} runs logged for this company.`, { size: 8.5, color: COLOR.inkSoft });
      y += 2;
    }

'''

A_ANCHOR = "const actionPlanItems = Array.isArray(recommendation?.action_plan) ? recommendation.action_plan : [];"
B_ANCHOR = 'onClick={resetRun}>'
C_ANCHOR = "// --- Footer ---"


def line_start(text, idx):
    return text.rfind("\n", 0, idx) + 1


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    path = Path(sys.argv[1])
    src = path.read_text(encoding="utf-8")

    if "solarpunkPlan" in src:
        print("Already applied: 'solarpunkPlan' is already in the file. Nothing changed.")
        return

    # A: helpers, right after the actionPlanItems line
    a = src.find(A_ANCHOR)
    if a == -1:
        sys.exit("Could not find the 'const actionPlanItems = ...' line. Nothing changed.")
    a_end = src.find("\n", a) + 1
    src = src[:a_end] + HELPERS + src[a_end:]

    # B: cards, above the <div className="ss-actions"> that holds "Add another file"
    b = src.find(B_ANCHOR)
    if b == -1:
        sys.exit("Could not find the 'Add another file' button. Nothing changed.")
    div = src.rfind('<div className="ss-actions">', 0, b)
    if div == -1:
        sys.exit("Could not find the ss-actions div above 'Add another file'. Nothing changed.")
    b_at = line_start(src, div)
    src = src[:b_at] + CARDS + src[b_at:]

    # C: PDF sections, above the footer
    c = src.find(C_ANCHOR)
    if c == -1:
        sys.exit("Could not find '// --- Footer ---' in the PDF function. Nothing changed.")
    c_at = line_start(src, c)
    src = src[:c_at] + PDF + src[c_at:]

    shutil.copyfile(path, str(path) + ".bak")
    path.write_text(src, encoding="utf-8")
    print(f"Done. Backup saved as {path}.bak")


if __name__ == "__main__":
    main()
