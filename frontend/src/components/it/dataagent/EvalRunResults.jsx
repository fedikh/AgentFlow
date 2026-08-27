import React, { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

/*
 * EvalRunResults — one experiment, rendered: stat tiles for the three metric
 * families, the honest counters, by-category table, rule-based
 * recommendations, and the per-case table with gold vs generated SQL side by
 * side. Execution accuracy is the headline number.
 */

const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const ms = (v) => (v == null ? "—"
  : v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${Math.round(v)}ms`);
const money = (v) => (v == null ? "—"
  : v < 0.0005 ? "<$0.001" : `$${Number(v).toFixed(3)}`);

const MATCH_BADGE = {
  exact: ["exact", "#F0FDF4", "#166534"],
  scalar: ["exact", "#F0FDF4", "#166534"],
  "both-empty": ["exact", "#F0FDF4", "#166534"],
  aligned: ["aligned", "#EFF6FF", "#1D4ED8"],
  "with-extras": ["extra cols", "#EFF6FF", "#1D4ED8"],
  indeterminate: ["row cap", "#FFFBEB", "#92400E"],
};

function matchBadge(r) {
  if (r.error) return ["crashed", "#FEF2F2", "#991B1B"];
  if (r.gold_error) return ["gold failed", "#FFFBEB", "#92400E"];
  if (r.category === "insufficient")
    return r.honest ? ["honest", "#F0FDF4", "#166534"]
                    : ["invented", "#FEF2F2", "#991B1B"];
  if (r.answered_from === "documents") return ["documents", "#F1F5F9", "#475569"];
  if (r.match === 1) return MATCH_BADGE[r.mode] || ["match", "#F0FDF4", "#166534"];
  if (r.match === null || r.match === undefined)
    return MATCH_BADGE[r.mode] || ["n/a", "#F1F5F9", "#475569"];
  return ["mismatch", "#FEF2F2", "#991B1B"];
}

function Tile({ label, value, sub }) {
  return (
    <div style={{ border: "1px solid #E5E9F0", borderRadius: 11,
                  padding: "11px 14px", background: "#fff" }}>
      <div style={{ font: "600 10.5px system-ui", color: "#64748B",
                    textTransform: "uppercase", letterSpacing: "0.04em" }}>
        {label}
      </div>
      <div style={{ font: "700 21px system-ui", color: "#0F172A",
                    marginTop: 3, fontVariantNumeric: "tabular-nums" }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 1 }}>{sub}</div>}
    </div>
  );
}

function SqlPair({ r }) {
  const pre = {
    flex: 1, minWidth: 0, margin: 0, padding: "9px 11px", borderRadius: 9,
    background: "#0F172A", color: "#E2E8F0", fontSize: 11.5, lineHeight: 1.55,
    fontFamily: "ui-monospace, Consolas, monospace",
    whiteSpace: "pre-wrap", wordBreak: "break-word",
  };
  const lab = { font: "700 10px system-ui", color: "#94A3B8",
                textTransform: "uppercase", letterSpacing: "0.05em",
                marginBottom: 4 };
  return (
    <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 8 }}>
      <div style={{ flex: 1, minWidth: 260 }}>
        <div style={lab}>Gold SQL {r.gold_rows != null ? `· ${r.gold_rows} row(s)` : ""}</div>
        <pre style={pre}>{r.gold_sql || "—"}</pre>
      </div>
      <div style={{ flex: 1, minWidth: 260 }}>
        <div style={lab}>Generated {r.gen_rows != null ? `· ${r.gen_rows} row(s)` : ""}
          {r.attempts > 1 ? ` · ${r.attempts} attempts` : ""}</div>
        <pre style={pre}>{r.sql || "—"}</pre>
      </div>
    </div>
  );
}

export default function EvalRunResults({ run }) {
  const [openCase, setOpenCase] = useState(null);
  if (!run) return null;
  const m = run.metrics || {};
  const acc = m.accuracy || {}, rel = m.reliability || {}, perf = m.performance || {};
  const byCat = Object.entries(m.by_category || {});
  const results = run.results || [];

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {/* headline tiles */}
      <div style={{ display: "grid", gap: 8,
                    gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}>
        <Tile label="Execution accuracy" value={pct(acc.execution_accuracy)}
              sub={`${m.comparable_cases ?? 0}/${m.cases ?? 0} comparable`} />
        <Tile label="Exact match" value={pct(acc.exact_match_rate)} />
        <Tile label="Valid SQL" value={pct(rel.validity_rate)} />
        <Tile label="First-try valid" value={pct(rel.first_try_valid_rate)}
              sub={rel.avg_attempts != null ? `avg ${rel.avg_attempts} attempts` : null} />
        <Tile label="Refused (insufficient)" value={pct(rel.insufficient_rate)}
              sub={acc.honesty_rate != null ? `honesty ${pct(acc.honesty_rate)}` : null} />
        <Tile label="Avg latency" value={ms(perf.avg_total_ms)}
              sub={perf.avg_execute_ms != null ? `exec ${ms(perf.avg_execute_ms)}` : null} />
        <Tile label="Cost / question" value={money(perf.est_cost_per_query)}
              sub={perf.est_tokens_per_query != null
                ? `~${Math.round(perf.est_tokens_per_query)} tok` : null} />
        {acc.answer_correctness != null && (
          <Tile label="Answer correctness" value={pct(acc.answer_correctness)}
                sub={`judge: ${(m.powered_by || {}).judge || "—"}`} />
        )}
      </div>

      {/* honest counters */}
      <div style={{ fontSize: 11.5, color: "#64748B" }}>
        {m.cases} case(s) · {m.gold_errors || 0} gold error(s) ·{" "}
        {m.indeterminate || 0} indeterminate · {m.document_fallbacks || 0} answered
        from documents · {m.crashed || 0} crashed —{" "}
        scored by {(m.powered_by || {}).accuracy || "execution accuracy"}
      </div>

      {/* recommendations */}
      {(m.recommendations || []).length > 0 && (
        <div style={{ border: "1px solid #FDE68A", background: "#FFFBEB",
                      borderRadius: 11, padding: "11px 14px" }}>
          <div style={{ font: "700 11px system-ui", color: "#92400E",
                        textTransform: "uppercase", letterSpacing: "0.05em",
                        marginBottom: 6 }}>
            Recommendations
          </div>
          {m.recommendations.map((r, i) => (
            <div key={i} style={{ fontSize: 12.5, color: "#78350F",
                                  lineHeight: 1.55, marginTop: i ? 4 : 0 }}>
              • {r}
            </div>
          ))}
        </div>
      )}

      {/* by category */}
      {byCat.length > 1 && (
        <div>
          <div style={{ font: "700 11px system-ui", color: "#64748B",
                        textTransform: "uppercase", letterSpacing: "0.05em",
                        margin: "2px 0 6px" }}>
            By question type
          </div>
          <table className="ev-table">
            <thead>
              <tr><th>Type</th><th>Cases</th><th>Exec accuracy</th>
                  <th>Valid SQL</th><th>Avg attempts</th></tr>
            </thead>
            <tbody>
              {byCat.map(([cat, v]) => (
                <tr key={cat}>
                  <td style={{ fontWeight: 600 }}>{cat}</td>
                  <td>{v.cases}</td>
                  <td>{pct(v.execution_accuracy)}</td>
                  <td>{pct(v.validity_rate)}</td>
                  <td>{v.avg_attempts ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* per-case table */}
      <div>
        <div style={{ font: "700 11px system-ui", color: "#64748B",
                      textTransform: "uppercase", letterSpacing: "0.05em",
                      margin: "2px 0 6px" }}>
          Per-case details
        </div>
        <table className="ev-table">
          <thead>
            <tr><th style={{ width: 20 }} /><th>Question</th><th>Result</th>
                <th>Attempts</th><th>Time</th></tr>
          </thead>
          <tbody>
            {results.map((r, i) => {
              const [label, bg, color] = matchBadge(r);
              const open = openCase === i;
              return (
                <React.Fragment key={i}>
                  <tr onClick={() => setOpenCase(open ? null : i)}
                      style={{ cursor: "pointer" }}>
                    <td style={{ color: "#94A3B8" }}>
                      {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                    </td>
                    <td style={{ maxWidth: 380, overflow: "hidden",
                                 textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                        title={r.question}>
                      {r.question}
                    </td>
                    <td>
                      <span style={{ fontSize: 10, fontWeight: 800, padding: "2px 8px",
                                     borderRadius: 20, background: bg, color,
                                     whiteSpace: "nowrap" }}>
                        {label}
                      </span>
                    </td>
                    <td>{r.attempts ?? "—"}</td>
                    <td style={{ fontVariantNumeric: "tabular-nums" }}>{ms(r.total_ms)}</td>
                  </tr>
                  {open && (
                    <tr>
                      <td colSpan={5} style={{ background: "#FAFBFC" }}>
                        <div style={{ fontSize: 12, color: "#334155" }}>
                          {r.analysis}
                          {r.detail ? ` — ${r.detail}` : ""}
                          {r.gold_error ? ` — gold: ${r.gold_error}` : ""}
                          {r.error ? ` — ${r.error}` : ""}
                        </div>
                        <SqlPair r={r} />
                        {r.answer && (
                          <div style={{ fontSize: 12, color: "#64748B", marginTop: 8 }}>
                            <b style={{ color: "#334155" }}>Answer:</b> {r.answer}
                          </div>
                        )}
                        {r.judge_reason && (
                          <div style={{ fontSize: 11.5, color: "#94A3B8", marginTop: 3 }}>
                            Judge ({pct(r.correctness)}): {r.judge_reason}
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
