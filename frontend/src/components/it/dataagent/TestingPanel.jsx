import React, { useState } from "react";
import { Bot, FlaskConical, Shield } from "lucide-react";
import AutoEvalPanel from "./AutoEvalPanel";
import DataChat from "./DataChat";

/*
 * TestingPanel — the RAG-space Evaluation layout, for the Data Agent:
 *
 *   🧪 Manual           the test console (ask by hand — answer, SQL, results)
 *   🤖 Auto evaluation  dataset → run · scores          (placeholder for now)
 *   🛡  Security         attack corpus · robustness      (placeholder for now)
 *
 * Same mode cards as the RAG EvaluationPanel so both workspaces read the
 * same way. The two future tabs land here without touching the page again.
 */

const MODES = [
  { k: "manual", Icon: FlaskConical, title: "Manual", accent: "#2563eb",
    desc: "Ask by hand — answer, SQL, results" },
  { k: "auto", Icon: Bot, title: "Auto evaluation", accent: "#8b5cf6",
    desc: "Dataset → run · scores · experiments" },
  { k: "security", Icon: Shield, title: "Security", accent: "#059669",
    desc: "Attack corpus · robustness · fixes" },
];

function Placeholder({ icon, accent, title, children }) {
  const Icon = icon;
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column",
                  alignItems: "center", justifyContent: "center",
                  gap: 10, textAlign: "center", padding: 24 }}>
      <span style={{ width: 54, height: 54, borderRadius: 16,
                     display: "grid", placeItems: "center",
                     background: `${accent}1a` }}>
        <Icon size={26} color={accent} strokeWidth={2} />
      </span>
      <div style={{ font: "700 15px system-ui", color: "#0f172a" }}>{title}</div>
      <div style={{ fontSize: 13, color: "#64748b", maxWidth: 420,
                    lineHeight: 1.55 }}>
        {children}
      </div>
      <span style={{ font: "700 10.5px system-ui", letterSpacing: "0.05em",
                     color: "#92400e", background: "#fffbeb",
                     border: "1px solid #fde68a", borderRadius: 999,
                     padding: "3px 11px" }}>
        COMING SOON
      </span>
    </div>
  );
}

export default function TestingPanel({ source, setError, testable }) {
  const [mode, setMode] = useState("manual");

  return (
    /* flex column pinned to the page — the manual chat takes every
       remaining pixel and owns its own scrolling */
    <div className="rag-cfg-panel"
         style={{ flex: "1 1 auto", minHeight: 0,
                  display: "flex", flexDirection: "column" }}>
      <div className="rag-cfg-head">
        <div>
          <div className="rag-cfg-title">Testing</div>
          <div className="rag-cfg-sub">
            Evaluate this agent before deploying — by hand today; automated
            scoring and security testing join here next.
          </div>
        </div>
      </div>

      {/* ── mode cards (the RAG evaluation pattern) ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)",
                    gap: 10, marginBottom: 14, flexShrink: 0 }}>
        {MODES.map((m) => {
          const on = mode === m.k;
          return (
            <button key={m.k} type="button" onClick={() => setMode(m.k)}
              style={{
                display: "flex", alignItems: "center", gap: 12,
                textAlign: "left", padding: "13px 14px", borderRadius: 12,
                cursor: "pointer",
                border: on ? `2px solid ${m.accent}` : "1px solid #e2e8f0",
                background: on ? `${m.accent}0d` : "#fff",
                boxShadow: on ? `0 1px 6px ${m.accent}22` : "none",
                transition: "border-color .15s, background .15s",
              }}>
              <span style={{
                width: 38, height: 38, borderRadius: 10, flexShrink: 0,
                display: "flex", alignItems: "center", justifyContent: "center",
                background: `${m.accent}1a`,
              }}><m.Icon size={19} color={m.accent} strokeWidth={2.1} /></span>
              <span>
                <span style={{ display: "block", fontWeight: 700,
                               fontSize: 13.5,
                               color: on ? m.accent : "#0f172a" }}>
                  {m.title}
                </span>
                <span style={{ display: "block", fontSize: 11.5,
                               color: "#64748b", marginTop: 1 }}>
                  {m.desc}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      {/* ═══ MANUAL — the test console ═══ */}
      {mode === "manual" && (testable ? (
        <DataChat source={source} setError={setError} height="fill"
                  placeholder="e.g. How many orders were placed last month?" />
      ) : (
        <div className="rag-cfg-hint">
          Train the agent (Knowledge → Train) to unlock testing.
        </div>
      ))}

      {/* ═══ AUTO EVALUATION — gold-SQL dataset → execution accuracy ═══ */}
      {mode === "auto" && (
        <AutoEvalPanel source={source} setError={setError} testable={testable} />
      )}

      {/* ═══ SECURITY — placeholder ═══ */}
      {mode === "security" && (
        <Placeholder icon={Shield} accent="#059669" title="Security testing">
          Attack the agent with prompt-injection and SQL-injection corpora and
          verify every attempt is rejected by the validator chain — with a
          judge verdict per case, like the RAG security lab.
        </Placeholder>
      )}
    </div>
  );
}
