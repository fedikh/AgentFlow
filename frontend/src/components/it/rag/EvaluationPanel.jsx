import React, { useEffect, useRef, useState } from "react";
import {
  evalListCases, evalAddCase, evalDeleteCase, evalClearCases,
  evalUploadDatasetFile, evalTemplateExcel, evalExpertForm,
  evalGenerateCases, evalRunAsync, evalRunStatus, evalRuns, evalRunDetail,
  evalRunDelete, evalRunDiagnose,
} from "../../../services/ragApi";
import {
  Bar, BarChart, CartesianGrid, LabelList, Legend, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import JudgeSelector from "./JudgeSelector";
import SecurityPanel from "./SecurityPanel";
import {
  FlaskConical, Bot, BarChart3, BookOpen, Scale, Upload, Sparkles,
  FileSpreadsheet, FileText, Plus, Trash2, Play, Timer, Info, Shield,
  ChevronDown, ChevronRight,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

/*
 * EvaluationPanel — three tabs:
 *   🧪 Manual      ad-hoc test console (answer + sources + latency)
 *   🤖 Auto        labeled dataset → one experiment run → the three metric
 *                  families side by side (NO composite overall score — any
 *                  weighting would be arbitrary):
 *                    retrieval   ranx (Hit rate@K, Precision@K, MRR, NDCG)
 *                    generation  Ragas + independent judge (faithfulness,
 *                                relevancy, context precision/recall,
 *                                correctness with a reason)
 *                    performance latency + litellm cost estimates
 *   📊 Experiments every stored run: full RAG config snapshot + scores
 */

const fmt = (t) =>
  t ? t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>") : "";

const SUGGESTS = [
  "Summarize the documents",
  "What are the key points?",
  "Give an example from the data",
];

const CATEGORIES = [
  "semantic", "exact_id", "entity_lookup", "table", "structured_data",
  "aggregation", "multi_doc", "multi_hop", "summarization", "reasoning",
  "multilingual",
];

const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const ms = (v) => (v == null ? "—" : v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${Math.round(v)}ms`);
const money = (v) => (v == null ? "—" : v < 0.001 ? "<$0.001" : `$${v.toFixed(3)}`);

/* Metrics arrive nested ({retrieval:{...}}) from new runs; legacy runs were
 * flat and reported "recall_at_k" (renamed hit_rate — with a single
 * document-level gold label it always equaled the hit rate). One accessor
 * serves every generation of stored run. */
const families = (m = {}) => {
  const r = m.retrieval || {
    recall_at_k: m.recall_at_k, precision_at_k: m.precision_at_k,
    mrr: m.mrr, ndcg: m.ndcg,
  };
  return {
  retrieval: { ...r, hit_rate: r.hit_rate ?? r.recall_at_k },
  generation: m.generation || {
    faithfulness: m.faithfulness, answer_relevancy: m.answer_relevancy,
    context_precision: m.context_precision, context_recall: m.context_recall,
    correctness: m.correctness,
  },
  performance: m.performance || {
    avg_retrieval_ms: m.avg_retrieval_ms, avg_answer_ms: m.avg_answer_ms,
    est_tokens_per_query: m.est_tokens_per_query,
    est_cost_per_query: m.est_cost_per_query,
  },
  };
};

/* ── experiment comparison (pick 2 in the Experiments tab) ── */

/* what we compare: [label, family, key, higherIsBetter, formatter] */
const COMPARE_METRICS = [
  ["Hit rate@K", "retrieval", "hit_rate", true, pct],
  ["Precision@K", "retrieval", "precision_at_k", true, pct],
  ["MRR", "retrieval", "mrr", true, pct],
  ["NDCG", "retrieval", "ndcg", true, pct],
  ["Faithfulness", "generation", "faithfulness", true, pct],
  ["Answer relevancy", "generation", "answer_relevancy", true, pct],
  ["Context precision", "generation", "context_precision", true, pct],
  ["Context recall", "generation", "context_recall", true, pct],
  ["Correctness (judge)", "generation", "correctness", true, pct],
  ["Retrieval latency", "performance", "avg_retrieval_ms", false, ms],
  ["Answer latency", "performance", "avg_answer_ms", false, ms],
  ["Cost / query", "performance", "est_cost_per_query", false, money],
];

/* flatten a run's config snapshot into label → display string */
const flatCfg = (c = {}) => {
  const emb = c.embedding || {}, llm = c.llm || {},
    ret = c.retrieval || {}, ch = c.chunking || {};
  const chunkDetail = ch.files
    ? Object.entries(ch.files).map(([f, s]) => `${f}: ${s}`).join(" · ")
    : typeof ch.strategies === "object"
      ? Object.entries(ch.strategies || {}).map(([t, s]) => `${t}: ${s}`).join(" · ")
      : String(ch.strategies || "");
  return {
    "Embedding model": `${emb.model || "—"}${emb.company_provider ? " (company)" : ""}`,
    "LLM model": `${llm.model || "—"}${llm.company_provider ? " (company)" : ""}`,
    "Temperature": String(llm.temperature ?? "—"),
    "Max tokens": String(llm.max_tokens ?? "—"),
    // short label only — the full texts get their own collapsible block
    // (PromptCollapse) under the What-changed table
    "System prompt": llm.system_prompt || "—",
    "Chunking": `${ch.mode || "—"}${chunkDetail ? ` — ${chunkDetail}` : ""}`,
    "Search mode": String(ret.search_mode || "—"),
    "Top K": String(ret.top_k ?? "—"),
    "Query enhancement": ret.query_enhancement ? "on" : "off",
    "Re-ranker": `${ret.reranker || "—"} (top ${ret.rerank_top_n ?? "—"})`,
    "RRF k / fetch / keyword": `${ret.rrf_k ?? "—"} / ${ret.fetch_k ?? "—"} / ${ret.keyword_k ?? "—"}`,
    "Judge": String(c.judge || "—"),
  };
};

/* collapsible prompt text — the SecurityPanel comparison pattern */
function PromptCollapse({ label, text, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  if (!text)
    return <div style={{ fontSize: 12, color: "#94a3b8" }}>{label}: (default prompt)</div>;
  return (
    <div>
      <button type="button" onClick={() => setOpen((v) => !v)}
        style={{ display: "inline-flex", alignItems: "center", gap: 5, border: "none",
                 background: "none", padding: 0, cursor: "pointer", color: "#334155",
                 font: "600 12px system-ui" }}>
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />} {label}
      </button>
      {open && (
        <pre style={{ whiteSpace: "pre-wrap", background: "#f8fafc", border: "1px solid #e2e8f0",
                      borderRadius: 9, padding: "10px 12px", fontSize: 11.5, color: "#334155",
                      marginTop: 6, maxHeight: 260, overflow: "auto",
                      fontFamily: "ui-monospace, monospace" }}>{text}</pre>
      )}
    </div>
  );
}

function DeltaPill({ a, b, higherBetter }) {
  if (a == null || b == null || a === b)
    return <span style={{ color: "#94a3b8", fontSize: 11 }}>{a === b && a != null ? "=" : "—"}</span>;
  const improved = higherBetter ? b > a : b < a;
  return (
    <span style={{
      fontSize: 11, fontWeight: 700,
      color: improved ? "#16a34a" : "#dc2626",
    }}>
      {b > a ? "▲" : "▼"} {improved ? "better" : "worse"}
    </span>
  );
}

function CompareView({ a, b }) {
  const fa = families(a.metrics), fb = families(b.metrics);
  const rows = COMPARE_METRICS
    .map(([label, fam, key, higher, fmtV]) => ({
      label, higher, fmt: fmtV, va: fa[fam]?.[key], vb: fb[fam]?.[key],
    }))
    .filter((r) => r.va != null || r.vb != null);
  const wins = rows.filter((r) => r.va != null && r.vb != null && r.va !== r.vb &&
    (r.higher ? r.vb > r.va : r.vb < r.va)).length;
  const losses = rows.filter((r) => r.va != null && r.vb != null && r.va !== r.vb &&
    (r.higher ? r.vb < r.va : r.vb > r.va)).length;

  const ca = flatCfg(a.config), cb = flatCfg(b.config);
  const cfgDiff = Object.keys(ca).filter((k) => ca[k] !== cb[k]);
  const promptA = a.config?.llm?.system_prompt_text || "";
  const promptB = b.config?.llm?.system_prompt_text || "";
  const promptChanged = promptA.trim() !== promptB.trim();

  const d = (r) => new Date(r.created_at).toLocaleString();
  const verdict = wins > losses
    ? { text: `B is the better experiment — ahead on ${wins} metric${wins > 1 ? "s" : ""}, behind on ${losses}.`, color: "#166534", bg: "#f0fdf4" }
    : losses > wins
      ? { text: `A is the better experiment — B regressed on ${losses} metric${losses > 1 ? "s" : ""}, improved on ${wins}.`, color: "#991b1b", bg: "#fef2f2" }
      : { text: "Tied — the change made no measurable difference.", color: "#475569", bg: "#f1f5f9" };

  return (
    <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12, padding: "14px 16px", display: "grid", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <div style={{ fontWeight: 700, fontSize: 13.5, color: ink.primary }}>Comparison</div>
        <div style={{ fontSize: 11.5, color: ink.muted }}>
          <strong>A</strong> = {d(a)} ({a.num_cases} cases) · <strong>B</strong> = {d(b)} ({b.num_cases} cases)
        </div>
      </div>

      <div style={{ fontSize: 12.5, fontWeight: 600, color: verdict.color, background: verdict.bg, borderRadius: 9, padding: "8px 12px" }}>
        {verdict.text}
      </div>

      {/* what changed between the two configs — the "why" */}
      <div>
        <div style={{ fontSize: 11.5, fontWeight: 700, color: ink.muted, textTransform: "uppercase", letterSpacing: ".03em", marginBottom: 6 }}>
          What changed
        </div>
        {cfgDiff.length === 0 ? (
          <div style={{ fontSize: 12, color: ink.muted }}>
            Configurations are identical — differences come from LLM/judge variance only.
          </div>
        ) : (
          <table className="ev-table">
            <thead><tr><th>Setting</th><th>A</th><th>B</th></tr></thead>
            <tbody>
              {cfgDiff.map((k) => (
                <tr key={k}>
                  <td style={{ fontWeight: 600 }}>{k}</td>
                  <td>{ca[k]}</td>
                  <td style={{ fontWeight: 600, color: "#1d4ed8" }}>{cb[k]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* the full prompt texts, collapsed — the security-comparison pattern */}
      <div>
        <div style={{ fontSize: 11.5, fontWeight: 700, color: ink.muted, textTransform: "uppercase", letterSpacing: ".03em", marginBottom: 6 }}>
          System prompt{promptChanged ? " — changed" : " — unchanged"}
        </div>
        <div style={{ display: "grid", gap: 8 }}>
          <PromptCollapse label="Experiment A prompt" text={promptA} />
          <PromptCollapse label="Experiment B prompt" text={promptB} />
        </div>
      </div>

      {/* visual comparison: A vs B across the percentage metrics */}
      <CompareChart rows={rows} />

      {/* metric-by-metric result */}
      <table className="ev-table">
        <thead><tr><th>Metric</th><th>A</th><th>B</th><th>Result</th></tr></thead>
        <tbody>
          {rows.map((r) => {
            const improved = r.va != null && r.vb != null && r.va !== r.vb &&
              (r.higher ? r.vb > r.va : r.vb < r.va);
            return (
              <tr key={r.label}>
                <td>{r.label}</td>
                <td>{r.va != null ? r.fmt(r.va) : "—"}</td>
                <td style={improved ? { fontWeight: 700, color: "#166534" } : undefined}>
                  {r.vb != null ? r.fmt(r.vb) : "—"}
                </td>
                <td><DeltaPill a={r.va} b={r.vb} higherBetter={r.higher} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ── A-vs-B comparison chart (grouped VERTICAL columns, percentage metrics) ──
   Two categorical series in the app's CVD-validated palette, value labels on
   top of every column so no reading back to an axis is needed. Only metrics
   that share a 0–100% scale go here; latency/cost (different scale) stay in
   the table — never a dual-axis chart. */
const CMP_A = "#2563EB", CMP_B = "#0D9488";
const SHORT_METRIC = {
  "Hit rate@K": "Hit rate", "Precision@K": "Precision",
  "Answer relevancy": "Relevancy", "Context precision": "Ctx precision",
  "Context recall": "Ctx recall", "Correctness (judge)": "Correctness",
};
function CompareChart({ rows }) {
  const data = rows
    .filter((r) => r.fmt === pct)
    .map((r) => ({
      metric: SHORT_METRIC[r.label] || r.label,
      A: r.va != null ? Math.round(r.va * 100) : null,
      B: r.vb != null ? Math.round(r.vb * 100) : null,
    }));
  if (!data.length) return null;
  return (
    <div>
      <div style={{ fontSize: 11.5, fontWeight: 700, color: "#64748b", textTransform: "uppercase",
                    letterSpacing: ".03em", marginBottom: 6 }}>
        Metric comparison — A vs B
      </div>
      <div style={{ width: "100%", height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barGap={3} barCategoryGap="28%"
                    margin={{ top: 18, right: 10, left: -14, bottom: 4 }}>
            <CartesianGrid vertical={false} stroke="#eef2f6" />
            <XAxis dataKey="metric" interval={0}
                   tick={{ fontSize: 11, fill: "#0f172a" }}
                   tickLine={false} axisLine={{ stroke: "#e5e9f0" }} />
            <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`}
                   ticks={[0, 25, 50, 75, 100]}
                   tick={{ fontSize: 11, fill: "#64748b" }}
                   tickLine={false} axisLine={false} />
            <Tooltip cursor={{ fill: "#f1f5f9" }}
                     formatter={(v, name) => [v == null ? "—" : `${v}%`, name]}
                     contentStyle={{ fontSize: 12, borderRadius: 10, border: "1px solid #e5e9f0" }} />
            <Legend iconSize={10} wrapperStyle={{ fontSize: 11.5 }} />
            <Bar name="A" dataKey="A" fill={CMP_A} radius={[4, 4, 0, 0]} maxBarSize={26}>
              <LabelList dataKey="A" position="top"
                         formatter={(v) => (v == null ? "" : `${v}`)}
                         style={{ fontSize: 10, fill: CMP_A, fontWeight: 700 }} />
            </Bar>
            <Bar name="B" dataKey="B" fill={CMP_B} radius={[4, 4, 0, 0]} maxBarSize={26}>
              <LabelList dataKey="B" position="top"
                         formatter={(v) => (v == null ? "" : `${v}`)}
                         style={{ fontSize: 10, fill: CMP_B, fontWeight: 700 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/* ── chart pieces (single-series horizontal bars; value = direct label) ── */
const ink = { primary: "#0f172a", muted: "#64748b", track: "#eef2f5" };
const btnIcon = { display: "inline-flex", alignItems: "center", gap: 6 };

function MetricBars({ title, hue, rows, poweredBy }) {
  const data = rows.filter(([, v]) => v != null);
  if (!data.length) return null;
  return (
    <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12,
                  padding: "14px 16px", flex: 1, minWidth: 260 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div style={{ fontWeight: 700, fontSize: 13.5, color: ink.primary }}>{title}</div>
        {poweredBy && <div style={{ fontSize: 10.5, color: ink.muted }}>{poweredBy}</div>}
      </div>
      <div style={{ marginTop: 10, display: "grid", gap: 9 }}>
        {data.map(([label, v]) => (
          <div key={label}>
            <div style={{ display: "flex", justifyContent: "space-between",
                          fontSize: 12, marginBottom: 3 }}>
              <span style={{ color: ink.muted }}>{label}</span>
              <span style={{ color: ink.primary, fontWeight: 600,
                             fontVariantNumeric: "tabular-nums" }}>{pct(v)}</span>
            </div>
            <div style={{ height: 8, background: ink.track, borderRadius: 4 }}>
              <div style={{ width: `${Math.round(v * 100)}%`, height: "100%",
                            background: hue, borderRadius: 4, minWidth: 2 }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatTile({ label, value, sub }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12,
                  padding: "12px 16px", flex: 1, minWidth: 120 }}>
      <div style={{ fontSize: 11.5, color: ink.muted }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: ink.primary,
                    fontVariantNumeric: "tabular-nums", marginTop: 2 }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: ink.muted, marginTop: 1 }}>{sub}</div>}
    </div>
  );
}

/* ── one experiment's results: 2 bar charts + performance tiles + details ── */
function Diagnosis({ spaceId, run }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const famHue = { retrieval: "#2563eb", generation: "#8b5cf6", performance: "#0d9488" };

  const runDiagnose = async () => {
    setBusy(true); setError("");
    try { setData(await evalRunDiagnose(spaceId, run.id)); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };

  const ruleRecs = run.metrics?.recommendations || [];
  return (
    <div className="ev-src" style={{ margin: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <div className="ev-src-t" style={{ margin: 0 }}>Feedback &amp; recommendations</div>
        <button type="button" onClick={runDiagnose} disabled={busy || !spaceId}
          style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 6,
                   border: "1px solid #2563eb", background: "#fff", color: "#2563eb",
                   borderRadius: 9, padding: "7px 13px", cursor: "pointer",
                   font: "600 12.5px system-ui" }}>
          {busy ? "Analyzing…" : data ? "Re-run diagnosis" : "Diagnose & recommend (AI)"}
        </button>
      </div>
      {error && <div style={{ color: "#b91c1c", fontSize: 12.5, marginTop: 8 }}>{error}</div>}

      {/* deterministic rule hints show until the AI diagnosis is requested */}
      {!data && ruleRecs.length > 0 && (
        <div className="rag-cfg-hint" style={{ margin: "8px 0 0" }}>
          {ruleRecs.map((r, i) => <div key={i}>• {r}</div>)}
        </div>
      )}
      {!data && ruleRecs.length === 0 && (
        <div style={{ fontSize: 12, color: "#64748b", marginTop: 8 }}>
          Rules detect the weak metrics; the judge LLM explains why and suggests what to try.
        </div>
      )}

      {data && (
        <div style={{ marginTop: 10, display: "grid", gap: 10 }}>
          {data.summary && (
            <div style={{ fontSize: 13, color: "#0f172a", fontWeight: 600 }}>{data.summary}</div>
          )}
          {data.status === "healthy" && (
            <div style={{ fontSize: 12.5, color: "#15803d" }}>✓ No problem crossed a threshold.</div>
          )}
          {data.fallback_same_as_rag && (
            <div style={{ fontSize: 11.5, color: "#a16207" }}>
              No independent judge — explained with the RAG&apos;s own LLM.
            </div>
          )}
          {(data.problems || []).map((p) => (
            <div key={p.code} style={{ border: "1px solid #e2e8f0", borderRadius: 10,
                                       padding: "11px 13px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%",
                               background: famHue[p.family] || "#64748b", flexShrink: 0 }} />
                <span style={{ fontWeight: 700, fontSize: 13, color: "#0f172a" }}>{p.label}</span>
                <span style={{ marginLeft: "auto", fontSize: 11.5, color: "#64748b" }}>{p.evidence}</span>
              </div>
              {p.why && (
                <div style={{ fontSize: 12.5, color: "#475569", marginTop: 6 }}>{p.why}</div>
              )}
              <div style={{ marginTop: 8, display: "grid", gap: 5 }}>
                {(p.recommendations || []).map((rec, i) => (
                  <div key={i} style={{ display: "flex", gap: 8, fontSize: 12.5 }}>
                    <span style={{ color: "#2563eb", fontWeight: 700 }}>→</span>
                    <span style={{ color: "#0f172a" }}>
                      <b>{rec.label}</b>
                      {rec.detail ? <span style={{ color: "#64748b" }}> — {rec.detail}</span> : null}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {(data.do_not_change || []).length > 0 && (
            <div style={{ fontSize: 12, color: "#64748b" }}>
              {data.do_not_change.map((d, i) => <div key={i}>· {d}</div>)}
            </div>
          )}
          <div style={{ fontSize: 10.5, color: "#94a3b8" }}>
            {data.engine === "rules"
              ? "Rule-based (no LLM judge available)"
              : `Rules detected the problems · explained by ${data.judge || "the judge LLM"}`}
          </div>
        </div>
      )}
    </div>
  );
}

function RunResults({ run, spaceId }) {
  const [showCases, setShowCases] = useState(false);
  if (!run?.metrics) return null;
  const m = run.metrics;
  const f = families(m);
  const powered = m.powered_by || {};
  const byCat = m.by_category || {};
  const cats = Object.keys(byCat);

  const retrievalUnscored = Object.values(f.retrieval).every((v) => v == null);

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {retrievalUnscored ? (
          <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12,
                        padding: "14px 16px", flex: 1, minWidth: 260,
                        display: "flex", gap: 10 }}>
            <Info size={16} color="#64748b" style={{ flexShrink: 0, marginTop: 1 }} />
            <div>
              <div style={{ fontWeight: 700, fontSize: 13.5, color: ink.primary }}>
                Retrieval — not scored
              </div>
              <div style={{ fontSize: 12, color: ink.muted, marginTop: 4, lineHeight: 1.5 }}>
                {m.labeled_cases ?? 0} of {m.cases} cases have an{" "}
                <strong>expected document</strong> label. Hit rate@K, Precision@K,
                MRR and NDCG need it — add the document (and page) each answer
                comes from in the Test dataset, then re-run.
              </div>
            </div>
          </div>
        ) : (
          <MetricBars title="Retrieval" hue="#2563eb" poweredBy={powered.retrieval}
            rows={[["Hit rate@K", f.retrieval.hit_rate],
                   ["Precision@K", f.retrieval.precision_at_k],
                   ["MRR", f.retrieval.mrr],
                   ["NDCG", f.retrieval.ndcg]]} />
        )}
        <MetricBars title="Generation" hue="#8b5cf6" poweredBy={powered.generation}
          rows={[["Faithfulness", f.generation.faithfulness],
                 ["Answer relevancy", f.generation.answer_relevancy],
                 ["Context precision", f.generation.context_precision],
                 ["Context recall", f.generation.context_recall],
                 ["Correctness (judge)", f.generation.correctness]]} />
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <StatTile label="Retrieval latency" value={ms(f.performance.avg_retrieval_ms)} sub="avg / query" />
        <StatTile label="Answer latency" value={ms(f.performance.avg_answer_ms)} sub="avg / query" />
        <StatTile label="Tokens" value={f.performance.est_tokens_per_query != null
          ? Math.round(f.performance.est_tokens_per_query) : "—"} sub="est. / query" />
        <StatTile label="Cost" value={money(f.performance.est_cost_per_query)}
          sub={`est. / query · ${powered.performance || "litellm"}`} />
      </div>

      {cats.length > 1 && (
        <div className="ev-src">
          <div className="ev-src-t">By question type</div>
          <table className="ev-table">
            <thead><tr><th>Type</th><th>Cases</th><th>Hit rate@K</th><th>MRR</th><th>Faithfulness</th><th>Correctness</th></tr></thead>
            <tbody>
              {cats.map((c) => (
                <tr key={c}>
                  <td>{c}</td><td>{byCat[c].cases}</td>
                  <td>{pct(byCat[c].hit_rate ?? byCat[c].recall_at_k)}</td><td>{pct(byCat[c].mrr)}</td>
                  <td>{pct(byCat[c].faithfulness)}</td><td>{pct(byCat[c].correctness)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Diagnosis spaceId={spaceId} run={run} />

      {(run.results || []).length > 0 && (
        <div>
          <button type="button" className="rp2-expander" onClick={() => setShowCases(!showCases)}>
            {showCases ? "▾" : "▸"} Per-case details ({run.results.length})
          </button>
          {showCases && (
            <table className="ev-table" style={{ marginTop: 8 }}>
              <thead><tr><th>Question</th><th>Hit</th><th>MRR</th><th>Correct</th><th>Analysis</th></tr></thead>
              <tbody>
                {run.results.map((r, i) => (
                  <tr key={i}>
                    <td className="ev-doc" title={r.answer || ""}>{r.question}</td>
                    <td>{r.hit == null ? "—" : r.hit ? "✅" : "❌"}</td>
                    <td>{pct(r.mrr)}</td>
                    <td title={r.reason || ""}>{pct(r.correctness)}</td>
                    <td style={{ fontSize: 11.5 }}>{r.analysis}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

/* ── the experiment's full RAG configuration ── */
function ConfigCard({ config = {} }) {
  const c = config;
  const [showPrompt, setShowPrompt] = useState(false);
  const promptText = c.llm?.system_prompt_text;
  const promptIsDefault = c.llm?.system_prompt_is_default;

  // Chunking cell: mode + the per-format (or per-file) processor breakdown
  const chunkEntries =
    c.chunking?.files ||
    (typeof c.chunking?.strategies === "object" ? c.chunking.strategies : null);
  const chunking = c.chunking ? (
    <div>
      <div>{c.chunking.mode}</div>
      {chunkEntries ? (
        <div style={{ marginTop: 5 }}>
          <div style={{ fontSize: 10.5, fontWeight: 700, color: "#94a3b8",
                        textTransform: "uppercase", letterSpacing: 0.4 }}>
            {c.chunking.files ? "Processeurs par fichier" : "Processeurs par format"}
          </div>
          {Object.entries(chunkEntries).map(([name, s]) => (
            <div key={name} style={{ display: "flex", justifyContent: "space-between",
                                     gap: 12, fontSize: 12, padding: "2px 0" }}>
              <span style={{ color: "#64748b", overflow: "hidden",
                             textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{name}</span>
              <span className="ev-method" style={{ flexShrink: 0 }}>{s}</span>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ color: "#64748b", fontSize: 12 }}>{String(c.chunking.strategies)}</div>
      )}
    </div>
  ) : (c.chunk_strategy || "—");                     // legacy runs
  const sections = [
    ["Embedding", c.embedding
      ? `${c.embedding.model}${c.embedding.dimensions ? ` · ${c.embedding.dimensions}d` : ""}${c.embedding.company_provider ? " · company" : ""}`
      : c.embedding || "—"],
    ["LLM", c.llm && c.llm.model !== undefined
      ? `${c.llm.model} · temp ${c.llm.temperature} · max ${c.llm.max_tokens} tok · prompt ${c.llm.system_prompt}`
      : c.llm || "—"],
    ["Chunking", chunking],
    ["Retrieval", c.retrieval
      ? `${c.retrieval.search_mode} · top-${c.retrieval.top_k} · rrf ${c.retrieval.rrf_k} · fetch ${c.retrieval.fetch_k}/${c.retrieval.keyword_k} · rerank ${c.retrieval.reranker} (top ${c.retrieval.rerank_top_n}) · enhance ${c.retrieval.query_enhancement ? "on" : "off"}`
      : `${c.search_mode || "—"} · top-${c.top_k ?? "—"}`],
    ["Judge", c.judge || "—"],
  ];
  return (
    <div className="ev-src" style={{ marginBottom: 0 }}>
      <div className="ev-src-t">Experiment configuration</div>
      <table className="ev-table">
        <tbody>
          {sections.map(([k, v]) => (
            <tr key={k}>
              <td style={{ fontWeight: 600, width: 110, verticalAlign: "top" }}>{k}</td>
              <td>{React.isValidElement(v) ? v : String(v)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {promptText && (
        <div style={{ marginTop: 8 }}>
          <button type="button" onClick={() => setShowPrompt((v) => !v)}
            style={{ display: "inline-flex", alignItems: "center", gap: 5, border: "none",
                     background: "none", padding: 0, cursor: "pointer", fontSize: 12,
                     fontWeight: 600, color: "#2563eb" }}>
            {showPrompt ? "▾" : "▸"} System prompt {promptIsDefault ? "(default)" : "(custom)"}
          </button>
          {showPrompt && (
            <pre style={{ whiteSpace: "pre-wrap", background: "#f8fafc",
                          border: "1px solid #e2e8f0", borderRadius: 9, padding: "11px 13px",
                          fontSize: 11.5, color: "#475569", marginTop: 6, maxHeight: 260,
                          overflow: "auto", fontFamily: "ui-monospace, monospace" }}>
              {promptText}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

const EvaluationPanel = ({
  chatHistory = [],
  chatEndRef,
  question,
  setQuestion,
  querying,
  handleQuery,
  spaceId,
  space,
  editable = true,
}) => {
  const [mode, setMode] = useState("manual");   // manual | auto | experiments
  const fileRef = useRef(null);

  // ── dataset state ──
  const [cases, setCases] = useState([]);
  const [genBusy, setGenBusy] = useState(false);
  const [genN, setGenN] = useState(8);
  const [genEngine, setGenEngine] = useState("");
  const [uploadInfo, setUploadInfo] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [showDataset, setShowDataset] = useState(false);
  const [form, setForm] = useState({
    question: "", expected_answer: "", expected_document: "",
    expected_page: "", category: "semantic",
  });
  const [evalError, setEvalError] = useState("");

  // ── runs state ──
  const [runs, setRuns] = useState([]);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(null);   // {done, total, last} while running
  const pollRef = useRef(null);
  const [openRun, setOpenRun] = useState(null);     // latest run (auto tab)
  const [openExp, setOpenExp] = useState(null);     // selected experiment
  const [compareIds, setCompareIds] = useState([]); // up to 2 runs to compare
  const [showExperiments, setShowExperiments] = useState(false); // reveal run history

  const toggleCompare = (id) =>
    setCompareIds((l) =>
      l.includes(id) ? l.filter((x) => x !== id)
        : l.length < 2 ? [...l, id]
        : [l[1], id]);                              // 3rd pick replaces the oldest

  const loadCases = () => {
    if (!spaceId) return;
    evalListCases(spaceId)
      .then((r) => setCases(r.cases || []))
      .catch((e) => setEvalError(e.message));
  };
  const loadRuns = () => {
    if (!spaceId) return;
    evalRuns(spaceId)
      .then((r) => setRuns(r.runs || []))
      .catch((e) => setEvalError(e.message));
  };
  useEffect(() => {
    if (mode === "auto") { loadCases(); loadRuns(); }
    setEvalError("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, spaceId]);

  // ── dataset actions ──
  const onUploadFile = async (file) => {
    if (!file) return;
    setEvalError(""); setUploadInfo("");
    try {
      const r = await evalUploadDatasetFile(spaceId, file);
      setCases((p) => [...p, ...(r.cases || [])]);
      setUploadInfo(`✓ Imported ${r.imported}${r.skipped ? ` · ${r.skipped} skipped` : ""}`);
    } catch (e) { setEvalError(e.message); }
    finally { if (fileRef.current) fileRef.current.value = ""; }
  };
  const _saveBlob = (blob, filename) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  const downloadExpertForm = async () => {
    try {
      const r = await evalExpertForm(spaceId);
      _saveBlob(new Blob([r.content], { type: "text/html" }), r.filename);
    } catch (e) { setEvalError(e.message); }
  };
  const downloadExcel = async () => {
    try {
      const r = await evalTemplateExcel(spaceId);
      const bytes = Uint8Array.from(atob(r.b64), (c) => c.charCodeAt(0));
      _saveBlob(new Blob([bytes], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      }), r.filename);
    } catch (e) { setEvalError(e.message); }
  };
  const generate = async () => {
    setGenBusy(true); setEvalError(""); setGenEngine("");
    try {
      const r = await evalGenerateCases(spaceId, genN);
      setCases((p) => [...p, ...(r.cases || [])]);
      setGenEngine(r.engine === "ragas" ? "Generated by Ragas" : "Generated by the space LLM");
    } catch (e) { setEvalError(e.message); }
    finally { setGenBusy(false); }
  };
  const addCase = async () => {
    if (!form.question.trim()) return;
    try {
      const c = await evalAddCase(spaceId, {
        ...form,
        expected_page: form.expected_page ? parseInt(form.expected_page, 10) : null,
      });
      setCases((p) => [...p, c]);
      setForm({ question: "", expected_answer: "", expected_document: "", expected_page: "", category: "semantic" });
    } catch (e) { setEvalError(e.message); }
  };
  const removeCase = async (id) => {
    try {
      await evalDeleteCase(spaceId, id);
      setCases((p) => p.filter((c) => c.id !== id));
    } catch (e) { setEvalError(e.message); }
  };
  const clearAll = async () => {
    if (!window.confirm(`Delete all ${cases.length} test cases?`)) return;
    try { await evalClearCases(spaceId); setCases([]); }
    catch (e) { setEvalError(e.message); }
  };
  // Async experiment: start a backend job, then poll it for case-by-case
  // progress (done / total / last finished question) until it completes.
  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };
  useEffect(() => stopPolling, []);          // never poll after unmount

  const runExperiment = async () => {
    setRunning(true); setEvalError(""); setOpenRun(null);
    try {
      const { job_id, total } = await evalRunAsync(spaceId);
      setProgress({ done: 0, total, last: "" });
      pollRef.current = setInterval(async () => {
        try {
          const st = await evalRunStatus(spaceId, job_id);
          setProgress({ done: st.done, total: st.total, last: st.last });
          if (st.status === "done") {
            stopPolling(); setProgress(null); setRunning(false);
            setOpenRun(st.run); loadRuns();
          } else if (st.status === "error") {
            stopPolling(); setProgress(null); setRunning(false);
            setEvalError(st.error || "Experiment failed");
          }
        } catch (e) {
          stopPolling(); setProgress(null); setRunning(false);
          setEvalError(e.message);
        }
      }, 1500);
    } catch (e) {
      setRunning(false); setEvalError(e.message);
    }
  };
  const viewExperiment = async (r) => {
    setOpenExp(r);
    try { setOpenExp(await evalRunDetail(spaceId, r.id)); } catch { /* keep summary */ }
  };

  const deleteExperiment = async (id) => {
    if (!window.confirm("Delete this experiment? This cannot be undone.")) return;
    setRuns((l) => l.filter((r) => r.id !== id));
    setCompareIds((l) => l.filter((x) => x !== id));
    if (openExp?.id === id) setOpenExp(null);
    if (openRun?.id === id) setOpenRun(null);
    try { await evalRunDelete(spaceId, id); } catch (e) { setEvalError(e.message); loadRuns(); }
  };

  // ── manual-tab pairing ──
  const mruns = [];
  for (const m of chatHistory) {
    if (m.role === "user") mruns.push({ q: m.content, a: null });
    else if (mruns.length && mruns[mruns.length - 1].a === null) mruns[mruns.length - 1].a = m;
    else mruns.push({ q: "", a: m });
  }
  mruns.reverse();
  const inFlight = querying && mruns.length && mruns[0].a === null ? mruns[0] : null;
  const doneRuns = inFlight ? mruns.slice(1) : mruns;

  return (
    <div className="rag-cfg-panel">
      <div className="rag-cfg-head">
        <div>
          <div className="rag-cfg-title">Evaluation</div>
          <div className="rag-cfg-sub">
            Test by hand, or measure everything with a labeled dataset —
            ranx retrieval math, Ragas generation scoring, an independent
            judge, and litellm cost estimates.
          </div>
        </div>
      </div>

      {/* ── mode cards ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 16 }}>
        {[
          { k: "manual", Icon: FlaskConical, title: "Manual", accent: "#2563eb",
            desc: "Ask by hand — answer, sources, latency" },
          { k: "auto", Icon: Bot, title: "Auto evaluation", accent: "#8b5cf6",
            desc: "Dataset → run · scores · experiments" },
          { k: "security", Icon: Shield, accent: "#059669", title: "Security",
            desc: "Attack corpus · robustness · fixes" },
        ].map((m) => {
          const on = mode === m.k;
          return (
            <button key={m.k} type="button" onClick={() => setMode(m.k)}
              style={{
                display: "flex", alignItems: "center", gap: 12, textAlign: "left",
                padding: "13px 14px", borderRadius: 12, cursor: "pointer",
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
                <span style={{ display: "block", fontWeight: 700, fontSize: 13.5,
                               color: on ? m.accent : "#0f172a" }}>{m.title}</span>
                <span style={{ display: "block", fontSize: 11.5, color: "#64748b",
                               marginTop: 1 }}>{m.desc}</span>
              </span>
            </button>
          );
        })}
      </div>

      {evalError && <div className="rag-cfg-warn" style={{ marginBottom: 10 }}>{evalError}</div>}

      {/* ═══════════════ MANUAL ═══════════════ */}
      {mode === "manual" && (
        <>
          {/* sticky: the question bar stays visible while results scroll */}
          <div style={{ position: "sticky", top: 0, zIndex: 5, background: "#fff",
                        padding: "8px 10px", margin: "0 -10px 8px",
                        borderBottom: "1px solid #eef2f5" }}>
            <div className="ev-bar" style={{ margin: 0 }}>
              <input className="ev-input" value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !querying && question.trim() && handleQuery()}
                placeholder="Type a test question…" disabled={querying} />
              <button className="rag-btn rag-btn-dark"
                style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                onClick={() => handleQuery()}
                disabled={querying || !question.trim()}>
                <Play size={14} /> {querying ? "Running…" : "Run test"}
              </button>
            </div>
          </div>
          {doneRuns.length === 0 && !querying && (
            <div className="ev-suggests">
              {SUGGESTS.map((s) => (
                <button key={s} className="ev-suggest" onClick={() => handleQuery(s)}>{s}</button>
              ))}
            </div>
          )}
          <div ref={chatEndRef} />
          {querying && (
            <div className="ev-run">
              <div className="ev-q"><span className="ev-q-badge">Q</span><span>{inFlight?.q || "…"}</span></div>
              <div className="ev-answer ev-running">Retrieving context and generating the answer…</div>
            </div>
          )}
          {doneRuns.map((run, idx) => {
            const sources = run.a?.sources || [];
            const t = run.a?.timings;
            const images = sources.filter((s) => s.type === "image" && s.image_url);
            return (
              <div className="ev-run" key={idx}>
                <div className="ev-q">
                  <span className="ev-q-badge">Q</span><span>{run.q}</span>
                  {t && (
                    <span className="ev-q-meta"
                      style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
                      title={`retrieval ${ms(t.retrieval_ms)} · answer ${ms(t.answer_ms)}`}>
                      <Timer size={12} /> {ms(t.total_ms)} · retrieval {ms(t.retrieval_ms)} · LLM {ms(t.answer_ms)}
                    </span>
                  )}
                </div>
                <div className="ev-answer">
                  {run.a ? <div dangerouslySetInnerHTML={{ __html: fmt(run.a.content) }} /> : <em>No answer.</em>}
                </div>
                {sources.length > 0 && (
                  <div className="ev-src">
                    <div className="ev-src-t">
                      Retrieved sources · {sources.length}
                      {sources.some((s) => (s.chunks || 1) > 1) && (
                        <span style={{ fontWeight: 400, color: "#64748b" }}>
                          {" "}({sources.reduce((n, s) => n + (s.chunks || 1), 0)} chunks — adjacent chunks merged)
                        </span>
                      )}
                    </div>
                    <table className="ev-table">
                      <thead><tr><th>#</th><th>Document</th><th>Page</th><th>Score</th><th>Found by</th></tr></thead>
                      <tbody>
                        {sources.map((s, j) => (
                          <tr key={j}>
                            <td>{j + 1}</td>
                            <td className="ev-doc" title={s.content || s.document}>
                              {s.type === "image" ? "🖼️ " : ""}{s.document}
                              {(s.chunks || 1) > 1 && (
                                <span className="ev-method" style={{ marginLeft: 6 }}>{s.chunks} chunks</span>
                              )}
                            </td>
                            <td>{s.page}</td>
                            <td>{s.score != null ? s.score : "—"}</td>
                            <td>{s.method ? <span className="ev-method">{s.method}</span> : "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {images.length > 0 && (
                      <div className="ev-imgs">
                        {images.map((s, j) => (
                          <img key={j} src={`${API_BASE}${s.image_url}`} alt={`Source p.${s.page}`}
                            onError={(e) => { e.target.style.display = "none"; }} />
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </>
      )}

      {/* ═══════════════ AUTO ═══════════════ */}
      {mode === "auto" && !showExperiments && (
        <div style={{ display: "grid", gap: 12 }}>
          {/* ── Test dataset card ── */}
          <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12,
                        padding: "14px 16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
              onClick={() => setShowDataset(!showDataset)}>
              <span style={{ width: 34, height: 34, borderRadius: 9, background: "#8b5cf61a",
                             display: "flex", alignItems: "center", justifyContent: "center",
                             flexShrink: 0 }}><BookOpen size={17} color="#7c3aed" /></span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, fontSize: 13.5, color: "#0f172a" }}>
                  Test dataset
                  <span style={{ marginLeft: 8, fontSize: 11, fontWeight: 600, color: "#7c3aed",
                                 background: "#8b5cf61a", borderRadius: 999, padding: "2px 9px" }}>
                    {cases.length} case{cases.length === 1 ? "" : "s"}
                  </span>
                  {genEngine && <span style={{ fontWeight: 400, fontSize: 11.5, color: "#64748b", marginLeft: 8 }}>{genEngine}</span>}
                  {uploadInfo && <span style={{ fontWeight: 400, fontSize: 11.5, color: "#16a34a", marginLeft: 8 }}>{uploadInfo}</span>}
                </div>
                <div style={{ fontSize: 11.5, color: "#64748b", marginTop: 1 }}>
                  Labeled questions with ground truth — written by an expert, uploaded, or generated.
                </div>
              </div>
              <span style={{ color: "#94a3b8", fontSize: 12 }}>{showDataset ? "▾" : "▸"}</span>
            </div>

            {showDataset && (
              <div style={{ marginTop: 12 }}>
                {editable && (
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center",
                                paddingBottom: 10, borderBottom: "1px solid #f1f5f9", marginBottom: 10 }}>
                    <button className="rag-btn rag-btn-dark" style={btnIcon} onClick={() => fileRef.current?.click()}>
                      <Upload size={14} /> Upload file</button>
                    <input ref={fileRef} type="file" accept=".xlsx,.xlsm,.csv,.json" hidden
                      onChange={(e) => onUploadFile(e.target.files?.[0])} />
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                      <button className="rag-btn" style={btnIcon} disabled={genBusy} onClick={generate}>
                        <Sparkles size={14} /> {genBusy ? "Generating…" : "Generate"}
                      </button>
                      <input type="number" min="3" max="15" value={genN}
                        style={{ width: 52, padding: "7px 8px" }} className="rag-cfg-select"
                        onChange={(e) => setGenN(parseInt(e.target.value, 10) || 8)} />
                    </span>
                    <span style={{ flex: 1 }} />
                    <button className="rag-btn" style={btnIcon} onClick={downloadExcel}
                      title="Excel template with dropdowns for a domain expert">
                      <FileSpreadsheet size={14} /> Excel</button>
                    <button className="rag-btn" style={btnIcon} onClick={downloadExpertForm}
                      title="Self-contained HTML form to send to a domain expert">
                      <FileText size={14} /> Form</button>
                    <button className="rag-btn" style={btnIcon} onClick={() => setShowAdd(!showAdd)}>
                      <Plus size={14} /> Add</button>
                    {cases.length > 0 && (
                      <button className="rag-btn" style={{ ...btnIcon, color: "#b91c1c" }}
                        onClick={clearAll} title="Delete all cases"><Trash2 size={14} /></button>
                    )}
                  </div>
                )}
                {showAdd && (
                  <div style={{ display: "grid", gap: 6, marginBottom: 12, padding: 12,
                                background: "#f8fafc", borderRadius: 10 }}>
                    <input className="rag-cfg-select" placeholder="Question *"
                      value={form.question} onChange={(e) => setForm({ ...form, question: e.target.value })} />
                    <input className="rag-cfg-select" placeholder="Expected answer (ground truth)"
                      value={form.expected_answer} onChange={(e) => setForm({ ...form, expected_answer: e.target.value })} />
                    <div style={{ display: "flex", gap: 6 }}>
                      <input className="rag-cfg-select" placeholder="Expected document" style={{ flex: 2 }}
                        value={form.expected_document} onChange={(e) => setForm({ ...form, expected_document: e.target.value })} />
                      <input className="rag-cfg-select" placeholder="Page" style={{ flex: 1 }}
                        value={form.expected_page} onChange={(e) => setForm({ ...form, expected_page: e.target.value })} />
                      <select className="rag-cfg-select" style={{ flex: 1 }} value={form.category}
                        onChange={(e) => setForm({ ...form, category: e.target.value })}>
                        {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                      </select>
                      <button className="rag-btn rag-btn-dark" onClick={addCase}>Add</button>
                    </div>
                  </div>
                )}
                {cases.length > 0 ? (
                  <table className="ev-table">
                    <thead><tr><th>Question</th><th>Expected doc</th><th>Type</th><th></th></tr></thead>
                    <tbody>
                      {cases.map((c) => (
                        <tr key={c.id}>
                          <td className="ev-doc" title={c.expected_answer || ""}>{c.question}</td>
                          <td>{c.expected_document || "—"}{c.expected_page ? ` p.${c.expected_page}` : ""}</td>
                          <td><span className="ev-method">{c.category}</span></td>
                          <td>{editable && <button className="ev-suggest" onClick={() => removeCase(c.id)}>✕</button>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div style={{ textAlign: "center", padding: "18px 0", color: "#64748b", fontSize: 12.5 }}>
                    No test cases yet — upload an expert file, generate some, or add one by hand.
                    <br />Aim for at least 10, with the expected document labeled.
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ── Judge LLM — same selector pattern as the LLM config ── */}
          <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12,
                        padding: "14px 16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
              <span style={{ width: 34, height: 34, borderRadius: 9, background: "#f59e0b1a",
                             display: "flex", alignItems: "center", justifyContent: "center",
                             flexShrink: 0 }}><Scale size={17} color="#d97706" /></span>
              <div>
                <div style={{ fontWeight: 700, fontSize: 13.5, color: "#0f172a" }}>Judge LLM</div>
                <div style={{ fontSize: 11.5, color: "#64748b", marginTop: 1 }}>
                  Grades the answers — keep it different from the RAG's own LLM.
                </div>
              </div>
            </div>
            <JudgeSelector spaceId={spaceId} space={space} onError={setEvalError} />
          </div>

          {/* run + live progress */}
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <button className="rag-btn rag-btn-dark"
              style={{ ...btnIcon, fontSize: 14, padding: "10px 20px" }}
              disabled={running || !cases.length || !editable} onClick={runExperiment}>
              <Play size={15} />
              {running ? "Running…" : `Run experiment (${cases.length} cases)`}
            </button>
            {running && !progress && <span style={{ color: "#64748b", fontSize: 12.5 }}>
              Starting…</span>}
          </div>

          {progress && (
            <div style={{ background: "#fff", border: "1px solid #e2e8f0",
                          borderRadius: 12, padding: "14px 16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between",
                            alignItems: "baseline", marginBottom: 8 }}>
                <span style={{ fontWeight: 700, fontSize: 13, color: "#0f172a" }}>
                  Evaluating case {Math.min(progress.done + 1, progress.total)} of {progress.total}
                </span>
                <span style={{ fontWeight: 700, fontSize: 15, color: "#8b5cf6",
                               fontVariantNumeric: "tabular-nums" }}>
                  {Math.round((progress.done / progress.total) * 100)}%
                </span>
              </div>
              <div style={{ height: 8, background: "#eef2f5", borderRadius: 4, overflow: "hidden" }}>
                <div style={{ width: `${Math.max(3, Math.round((progress.done / progress.total) * 100))}%`,
                              height: "100%", background: "#8b5cf6", borderRadius: 4,
                              transition: "width .6s ease" }} />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10,
                            marginTop: 7, fontSize: 11.5, color: "#64748b" }}>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis",
                               whiteSpace: "nowrap" }}>
                  {progress.last ? `✓ ${progress.last}` : "Retrieving, generating and scoring each case…"}
                </span>
                <span style={{ flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
                  {progress.done}/{progress.total} done
                </span>
              </div>
            </div>
          )}

          {openRun && <RunResults run={openRun} spaceId={spaceId} />}
          {!openRun && runs.length > 0 && (
            <button className="rp2-expander" onClick={() => setOpenRun(runs[0]) || viewExperiment(runs[0])}>
              ▸ Show latest experiment ({new Date(runs[0].created_at).toLocaleString()})
            </button>
          )}

          {/* ── Experiments — a button that opens the experiments page ── */}
          {runs.length > 0 && (
            <button type="button" onClick={() => setShowExperiments(true)}
              style={{ display: "flex", alignItems: "center", gap: 9, width: "100%",
                       textAlign: "left", cursor: "pointer", padding: "12px 14px",
                       borderRadius: 12, background: "#fff", border: "1px solid #e2e8f0" }}>
              <span style={{ width: 30, height: 30, borderRadius: 8, flexShrink: 0,
                             display: "flex", alignItems: "center", justifyContent: "center",
                             background: "#f59e0b1a" }}>
                <BarChart3 size={16} color="#f59e0b" />
              </span>
              <span style={{ flex: 1 }}>
                <span style={{ display: "block", fontWeight: 700, fontSize: 13, color: "#0f172a" }}>
                  Experiments
                  <span style={{ marginLeft: 8, fontSize: 11, fontWeight: 600, color: "#b45309",
                                 background: "#f59e0b1a", borderRadius: 999, padding: "2px 9px" }}>
                    {runs.length}
                  </span>
                </span>
                <span style={{ display: "block", fontSize: 11.5, color: "#64748b", marginTop: 1 }}>
                  Every run keeps its full config + scores — open to browse and compare.
                </span>
              </span>
              <span style={{ color: "#94a3b8", fontSize: 14 }}>→</span>
            </button>
          )}
        </div>
      )}

      {/* ═══════════════ EXPERIMENTS PAGE (opened from Auto) ═══════════════ */}
      {mode === "auto" && showExperiments && (
        <div style={{ display: "grid", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button type="button" onClick={() => { setShowExperiments(false); setOpenExp(null); }}
              style={{ display: "inline-flex", alignItems: "center", gap: 6, border: "1px solid #e2e8f0",
                       background: "#fff", borderRadius: 9, padding: "7px 12px", cursor: "pointer",
                       font: "600 12.5px system-ui", color: "#0f172a" }}>
              ← Back to evaluation
            </button>
            <BarChart3 size={16} color="#f59e0b" />
            <span style={{ fontWeight: 800, fontSize: 15, color: "#0f172a" }}>Experiments</span>
            <span style={{ fontSize: 11.5, color: "#64748b" }}>
              {runs.length} run{runs.length === 1 ? "" : "s"}
            </span>
          </div>
          {runs.length === 0 && (
            <div className="rag-cfg-hint">No experiments yet — run one from the Auto evaluation tab.</div>
          )}
          {runs.length > 0 && (
            <>
              <div className="rag-cfg-hint" style={{ margin: 0 }}>
                Tick <strong>two</strong> experiments to compare them — the comparison
                shows what changed in the config and which run wins, metric by metric.
              </div>
              <table className="ev-table">
                <thead><tr><th>Compare</th><th>Date</th><th>Cases</th><th>Duration</th><th>Hit rate@K</th><th>Faithfulness</th><th>Correctness</th><th></th><th></th></tr></thead>
                <tbody>
                  {runs.map((r) => {
                    const f = families(r.metrics);
                    const active = openExp?.id === r.id;
                    const ticked = compareIds.includes(r.id);
                    return (
                      <tr key={r.id} style={active || ticked ? { background: "#eff6ff" } : undefined}>
                        <td>
                          <input type="checkbox" checked={ticked}
                                 onChange={() => toggleCompare(r.id)} />
                          {ticked && (
                            <strong style={{ marginLeft: 6, color: "#1d4ed8" }}>
                              {compareIds[0] === r.id ? "A" : "B"}
                            </strong>
                          )}
                        </td>
                        <td>{new Date(r.created_at).toLocaleString()}</td>
                        <td>{r.num_cases}</td>
                        <td>{ms(r.duration_ms)}</td>
                        <td>{pct(f.retrieval.hit_rate)}</td>
                        <td>{pct(f.generation.faithfulness)}</td>
                        <td>{pct(f.generation.correctness)}</td>
                        <td><button className="ev-suggest" onClick={() => viewExperiment(r)}>
                          {active ? "viewing" : "view"}</button></td>
                        <td><button title="Delete experiment" onClick={() => deleteExperiment(r.id)}
                          style={{ display: "inline-flex", border: "1px solid #e2e8f0",
                                   background: "#fff", borderRadius: 7, padding: "5px",
                                   cursor: "pointer", color: "#94a3b8" }}>
                          <Trash2 size={13} /></button></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </>
          )}
          {compareIds.length === 2 && (() => {
            const ra = runs.find((r) => r.id === compareIds[0]);
            const rb = runs.find((r) => r.id === compareIds[1]);
            return ra && rb ? <CompareView a={ra} b={rb} /> : null;
          })()}
          {openExp && (
            <>
              <ConfigCard config={openExp.config} />
              <RunResults run={openExp} spaceId={spaceId} />
            </>
          )}
        </div>
      )}

      {/* ═══════════════ SÉCURITÉ ═══════════════ */}
      {mode === "security" && (
        <SecurityPanel spaceId={spaceId} editable={editable} onError={setEvalError} />
      )}
    </div>
  );
};

export default EvaluationPanel;
