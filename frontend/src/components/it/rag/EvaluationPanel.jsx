import React, { useEffect, useRef, useState } from "react";
import {
  evalListCases, evalAddCase, evalDeleteCase, evalClearCases,
  evalUploadDatasetFile, evalTemplateExcel, evalExpertForm,
  evalGenerateCases, evalRun, evalRuns, evalRunDetail, updateSpace,
} from "../../../services/ragApi";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

// Lightweight markdown (bold + line breaks) for the generated answer.
const fmt = (t) =>
  t
    ? t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>")
    : "";

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

// Independent judge presets (must mirror backend JUDGE_PRESETS)
const JUDGES = [
  ["gpt", "GPT-5", "OpenAI — strong default judge"],
  ["claude", "Claude Sonnet", "Anthropic — strong default judge"],
  ["gemini", "Gemini", "Google — Gemini 2.5 Pro"],
  ["same", "Same as RAG", "Reuse the space's own LLM"],
];

const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const ms = (v) => (v == null ? "—" : v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${Math.round(v)}ms`);
const money = (v) => (v == null ? "—" : v < 0.001 ? "<$0.001" : `$${v.toFixed(3)}`);
const scoreClass = (v) => (v == null ? "" : v >= 0.8 ? "good" : v >= 0.6 ? "mid" : "bad");

/**
 * EvaluationPanel — two modes chosen with big cards:
 *   🧪 Manual : ad-hoc test console (question → answer + sources)
 *   🤖 Auto   : labeled dataset (JSON upload — e.g. written by a domain
 *               expert from the downloadable template — or Ragas generation)
 *               → run every case → trust-first scoring:
 *               retrieval = pure math (Recall/Precision/MRR/NDCG),
 *               context+answer = Ragas, correctness = independent judge LLM
 *               with a human-readable reason, performance = latency/cost.
 *               Overall score shown WITH its 40/40/20 breakdown.
 */
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
  const [mode, setMode] = useState("manual");   // manual | auto
  const fileRef = useRef(null);

  // ── dataset state ──
  const [cases, setCases] = useState([]);
  const [loadingCases, setLoadingCases] = useState(false);
  const [genBusy, setGenBusy] = useState(false);
  const [genN, setGenN] = useState(8);
  const [genEngine, setGenEngine] = useState("");
  const [uploadInfo, setUploadInfo] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({
    question: "", expected_answer: "", expected_document: "",
    expected_page: "", category: "semantic",
  });
  const [evalError, setEvalError] = useState("");

  // ── runs state ──
  const [runs, setRuns] = useState([]);
  const [running, setRunning] = useState(false);
  const [openRun, setOpenRun] = useState(null);

  // ── judge (persisted in space.eval_params) ──
  const ep = space?.eval_params || {};
  const [judge, setJudge] = useState(ep.judge || "gpt");
  const [judgeModel, setJudgeModel] = useState(ep.judge_model || "");
  const [judgeSaved, setJudgeSaved] = useState(true);
  const pickJudge = (j) => { setJudge(j); setJudgeSaved(false); };
  const saveJudge = async () => {
    try {
      await updateSpace(spaceId, { eval_params: { judge, judge_model: judgeModel || undefined } });
      setJudgeSaved(true);
    } catch (e) { setEvalError(e.message); }
  };

  const loadCases = () => {
    if (!spaceId) return;
    setLoadingCases(true);
    evalListCases(spaceId)
      .then((r) => setCases(r.cases || []))
      .catch((e) => setEvalError(e.message))
      .finally(() => setLoadingCases(false));
  };
  const loadRuns = () => {
    if (!spaceId) return;
    evalRuns(spaceId)
      .then((r) => {
        setRuns(r.runs || []);
        if (!openRun && r.runs?.length) setOpenRun(r.runs[0]);
      })
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
      // .xlsx / .csv / .json all handled server-side (flexible EN/FR headers)
      const r = await evalUploadDatasetFile(spaceId, file);
      setCases((p) => [...p, ...(r.cases || [])]);
      setUploadInfo(`✓ Imported ${r.imported} case${r.imported === 1 ? "" : "s"}${r.skipped ? ` · ${r.skipped} skipped (no question)` : ""}`);
    } catch (e) {
      setEvalError(e.message);
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
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
    try {
      await evalClearCases(spaceId);
      setCases([]);
    } catch (e) { setEvalError(e.message); }
  };
  const runExperiment = async () => {
    setRunning(true); setEvalError("");
    try {
      const r = await evalRun(spaceId);
      setOpenRun(r);
      loadRuns();
    } catch (e) { setEvalError(e.message); }
    finally { setRunning(false); }
  };
  const viewRun = async (r) => {
    setOpenRun(r);
    try { setOpenRun(await evalRunDetail(spaceId, r.id)); } catch { /* keep summary */ }
  };

  // manual-tab pairing
  const mruns = [];
  for (const m of chatHistory) {
    if (m.role === "user") mruns.push({ q: m.content, a: null });
    else if (mruns.length && mruns[mruns.length - 1].a === null) mruns[mruns.length - 1].a = m;
    else mruns.push({ q: "", a: m });
  }
  mruns.reverse();
  const inFlight = querying && mruns.length && mruns[0].a === null ? mruns[0] : null;
  const doneRuns = inFlight ? mruns.slice(1) : mruns;

  const best = runs.length
    ? runs.reduce((a, b) =>
        ((b.metrics?.overall_score ?? -1) > (a.metrics?.overall_score ?? -1) ? b : a), runs[0])
    : null;

  const bd = openRun?.metrics?.breakdown;
  const powered = openRun?.metrics?.powered_by;

  return (
    <div className="rag-cfg-panel">
      <div className="rag-cfg-head">
        <div>
          <div className="rag-cfg-title">Evaluation</div>
          <div className="rag-cfg-sub">
            Test by hand, or measure everything with a labeled dataset —
            mathematical retrieval metrics, Ragas, and an independent judge LLM.
          </div>
        </div>
      </div>

      {/* ── mode cards ── */}
      <div className="ev4-modes">
        <button className={`ev4-mode ${mode === "manual" ? "on" : ""}`} onClick={() => setMode("manual")}>
          <span className="ev4-mode-i">🧪</span>
          <span className="ev4-mode-t">Manual evaluation</span>
          <span className="ev4-mode-s">Ask questions by hand and inspect the answer and its retrieved sources.</span>
        </button>
        <button className={`ev4-mode ${mode === "auto" ? "on" : ""}`} onClick={() => setMode("auto")}>
          <span className="ev4-mode-i">🤖</span>
          <span className="ev4-mode-t">Auto evaluation{cases.length ? ` · ${cases.length} cases` : ""}</span>
          <span className="ev4-mode-s">Upload or generate a test dataset, then score retrieval, answers and cost.</span>
        </button>
      </div>

      {evalError && <div className="rag-cfg-warn" style={{ marginBottom: 10 }}>{evalError}</div>}

      {/* ═══════════════ MANUAL ═══════════════ */}
      {mode === "manual" && (
        <>
          <div className="ev-bar">
            <input className="ev-input" value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !querying && question.trim() && handleQuery()}
              placeholder="Type a test question…" disabled={querying} />
            <button className="rag-btn rag-btn-dark" onClick={() => handleQuery()}
              disabled={querying || !question.trim()}>
              {querying ? "Running…" : "▶ Run test"}
            </button>
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
              <div className="ev-q"><span className="ev-q-badge">Q</span><span>{inFlight?.q || "…"}</span>
                <span className="ev-q-meta">running…</span></div>
              <div className="ev-answer ev-running">Retrieving context and generating the answer…</div>
            </div>
          )}
          {doneRuns.map((run, idx) => {
            const sources = run.a?.sources || [];
            const images = sources.filter((s) => s.type === "image" && s.image_url);
            const body = (
              <>
                <div className="ev-answer">
                  {run.a ? <div dangerouslySetInnerHTML={{ __html: fmt(run.a.content) }} /> : <em>No answer.</em>}
                </div>
                {sources.length > 0 && (
                  <div className="ev-src">
                    <div className="ev-src-t">Retrieved sources · {sources.length}</div>
                    <table className="ev-table">
                      <thead><tr><th>#</th><th>Document</th><th>Page</th><th>Score</th><th>Found by</th></tr></thead>
                      <tbody>
                        {sources.map((s, j) => (
                          <tr key={j}>
                            <td>{j + 1}</td>
                            <td className="ev-doc" title={s.content || s.document}>{s.type === "image" ? "🖼️ " : ""}{s.document}</td>
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
              </>
            );
            if (idx === 0) {
              return (
                <div key={idx} className="ev-run">
                  <div className="ev-q"><span className="ev-q-badge">Q</span><span>{run.q}</span>
                    <span className="ev-q-meta">latest run</span></div>
                  {body}
                </div>
              );
            }
            return (
              <details key={idx} className="ev-run ev-run-old">
                <summary className="ev-q"><span className="ev-q-badge">Q</span><span>{run.q}</span>
                  <span className="ev-q-meta">run #{doneRuns.length - idx}</span></summary>
                {body}
              </details>
            );
          })}
        </>
      )}

      {/* ═══════════════ AUTO ═══════════════ */}
      {mode === "auto" && (
        <>
          {/* ── dataset ── */}
          <div className="ev4-card">
            <div className="ev4-card-h">
              <div>
                <div className="ev4-card-t">📚 Test dataset</div>
                <div className="ev4-card-s">
                  Labeled questions with the correct answer and source document —
                  written by a domain expert or generated automatically.
                </div>
              </div>
              {editable && cases.length > 0 && (
                <button className="rag-btn rag-btn-xs rag-btn-red" onClick={clearAll}>Clear all</button>
              )}
            </div>

            {editable && (
              <div className="ev4-actions">
                <div className="ev4-action">
                  <div className="ev4-action-i">🧑‍💼</div>
                  <div className="ev4-action-b">
                    <div className="ev4-action-t">Ask a domain expert — no technical skills needed</div>
                    <div className="ev4-action-s">
                      <b>1.</b> Send the expert the <b>interactive form</b> (opens in any browser —
                      guided questions, auto-saves, one button to export) or the <b>Excel
                      template</b> (dropdowns with your real documents).{" "}
                      <b>2.</b> The expert fills it with real questions + correct answers.{" "}
                      <b>3.</b> Upload the file they send back — .html-exported .json, .xlsx
                      and .csv all work, English or French columns.
                    </div>
                    <div className="ev4-action-r">
                      <button className="rag-btn rag-btn-sm" onClick={downloadExpertForm}>
                        🌐 Interactive form ★
                      </button>
                      <button className="rag-btn rag-btn-sm" onClick={downloadExcel}>
                        📊 Excel template
                      </button>
                      <input ref={fileRef} type="file" accept=".json,.csv,.xlsx,.xlsm" style={{ display: "none" }}
                        onChange={(e) => onUploadFile(e.target.files?.[0])} />
                      <button className="rag-btn rag-btn-sm rag-btn-dark" onClick={() => fileRef.current?.click()}>
                        📤 Upload filled file
                      </button>
                    </div>
                    {uploadInfo && <div className="ev4-ok">{uploadInfo}</div>}
                  </div>
                </div>
                <div className="ev4-action">
                  <div className="ev4-action-i">✨</div>
                  <div className="ev4-action-b">
                    <div className="ev4-action-t">Generate with Ragas</div>
                    <div className="ev4-action-s">
                      Builds test questions automatically from your real indexed documents
                      (Ragas testset generator, LLM fallback).
                    </div>
                    <div className="ev4-action-r">
                      <input className="ev-input" style={{ maxWidth: 64 }} type="number" min={3} max={15}
                        value={genN} onChange={(e) => setGenN(Math.max(3, Math.min(15, +e.target.value || 8)))} />
                      <button className="rag-btn rag-btn-sm rag-btn-dark" onClick={generate} disabled={genBusy}>
                        {genBusy ? "Generating…" : "✨ Generate"}
                      </button>
                    </div>
                    {genEngine && <div className="ev4-ok">✓ {genEngine}</div>}
                  </div>
                </div>
              </div>
            )}

            {loadingCases ? (
              <div className="rag-cfg-hint">Loading…</div>
            ) : cases.length === 0 ? (
              <div className="ev-empty">
                <div className="ev-empty-t">No test cases yet</div>
                <div className="ev-empty-s">Upload an expert dataset or generate one to start measuring.</div>
              </div>
            ) : (
              <table className="ev-table">
                <thead><tr><th>Question</th><th>Category</th><th>Expected source</th><th>Ground truth</th><th>From</th>{editable && <th />}</tr></thead>
                <tbody>
                  {cases.map((c) => (
                    <tr key={c.id}>
                      <td className="ev-doc" style={{ maxWidth: 300 }} title={c.question}>{c.question}</td>
                      <td><span className="ev-method">{c.category}</span></td>
                      <td className="ev-doc" style={{ maxWidth: 170 }}>
                        {c.expected_document ? `${c.expected_document}${c.expected_page ? ` · p.${c.expected_page}` : ""}` : "—"}
                      </td>
                      <td className="ev-doc" style={{ maxWidth: 200 }} title={c.expected_answer}>{c.expected_answer || "—"}</td>
                      <td>{c.source === "upload" ? "📤" : c.source === "generated" ? "✨" : "✍️"}</td>
                      {editable && (
                        <td><button className="rag-btn rag-btn-xs rag-btn-red" onClick={() => removeCase(c.id)}>×</button></td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {editable && (
              <div style={{ marginTop: 8 }}>
                {!showAdd ? (
                  <button className="rag-btn rag-btn-xs" onClick={() => setShowAdd(true)}>+ Add one case manually</button>
                ) : (
                  <div className="ev2-form">
                    <input className="ev-input" placeholder="Question *" value={form.question}
                      onChange={(e) => setForm({ ...form, question: e.target.value })} />
                    <div className="ev2-form-row">
                      <input className="ev-input" placeholder="Ground-truth answer" value={form.expected_answer}
                        onChange={(e) => setForm({ ...form, expected_answer: e.target.value })} />
                      <input className="ev-input" style={{ maxWidth: 200 }} placeholder="Expected document" value={form.expected_document}
                        onChange={(e) => setForm({ ...form, expected_document: e.target.value })} />
                      <input className="ev-input" style={{ maxWidth: 90 }} type="number" placeholder="Page"
                        value={form.expected_page}
                        onChange={(e) => setForm({ ...form, expected_page: e.target.value })} />
                      <select className="ev-input" style={{ maxWidth: 160 }} value={form.category}
                        onChange={(e) => setForm({ ...form, category: e.target.value })}>
                        {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                      <button className="rag-btn rag-btn-dark" onClick={addCase} disabled={!form.question.trim()}>Add</button>
                      <button className="rag-btn" onClick={() => setShowAdd(false)}>Cancel</button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ── judge ── */}
          <div className="ev4-card">
            <div className="ev4-card-h">
              <div>
                <div className="ev4-card-t">⚖️ Independent judge</div>
                <div className="ev4-card-s">
                  The LLM that scores correctness against the ground truth and explains each
                  score. A different model than your RAG avoids self-grading bias.
                </div>
              </div>
              {editable && (
                <button className={`rag-btn rag-btn-sm ${judgeSaved ? "" : "rag-btn-dark"}`}
                  onClick={saveJudge} disabled={judgeSaved}>
                  {judgeSaved ? "✓ Saved" : "Save judge"}
                </button>
              )}
            </div>
            <div className="ev4-judges">
              {JUDGES.map(([v, t, s]) => (
                <button key={v} className={`ev4-judge ${judge === v ? "on" : ""}`}
                  disabled={!editable} onClick={() => pickJudge(v)}>
                  <span className="ev4-judge-t">{t}{v === "gpt" ? " ★" : ""}</span>
                  <span className="ev4-judge-s">{s}</span>
                </button>
              ))}
              {judge !== "same" && (
                <input className="ev-input" style={{ maxWidth: 190 }} disabled={!editable}
                  placeholder="Model override (optional)" value={judgeModel}
                  onChange={(e) => { setJudgeModel(e.target.value); setJudgeSaved(false); }} />
              )}
            </div>
          </div>

          {/* ── run & results ── */}
          <div className="ev4-card">
            <div className="ev4-card-h">
              <div>
                <div className="ev4-card-t">📊 Experiment</div>
                <div className="ev4-card-s">
                  Runs every case against the CURRENT config. Change the config, run again, compare.
                </div>
              </div>
              <button className="rag-btn rag-btn-dark" onClick={runExperiment}
                disabled={running || cases.length === 0}>
                {running ? "Evaluating…" : "▶ Run evaluation"}
              </button>
            </div>
            {running && (
              <div className="ev-answer ev-running" style={{ padding: "10px 0" }}>
                Running every case (retrieve → answer → Ragas → judge)… this can take a minute per few cases.
              </div>
            )}

            {openRun && (
              <>
                {/* ── overall score hero + transparent breakdown ── */}
                {openRun.metrics.overall_score != null && (
                  <div className="ev4-hero">
                    <div className="ev4-hero-score">
                      <div className={`ev4-hero-n ${scoreClass(openRun.metrics.overall_score / 100)}`}>
                        {openRun.metrics.overall_score}
                      </div>
                      <div className="ev4-hero-cap">Overall score / 100</div>
                    </div>
                    <div className="ev4-hero-bd">
                      <div className="ev4-hero-bd-t">How this score was calculated</div>
                      <div className="ev4-hero-cols">
                        <div className="ev4-hero-col">
                          <div className="ev4-hero-col-t">Retrieval <span>{bd?.retrieval?.weight}%</span></div>
                          <div className="ev4-hero-row"><span>Recall@K</span><b className={scoreClass(bd?.retrieval?.parts?.recall_at_k)}>{pct(bd?.retrieval?.parts?.recall_at_k)}</b></div>
                          <div className="ev4-hero-row"><span>Context recall</span><b className={scoreClass(bd?.retrieval?.parts?.context_recall)}>{pct(bd?.retrieval?.parts?.context_recall)}</b></div>
                        </div>
                        <div className="ev4-hero-col">
                          <div className="ev4-hero-col-t">Generation <span>{bd?.generation?.weight}%</span></div>
                          <div className="ev4-hero-row"><span>Faithfulness</span><b className={scoreClass(bd?.generation?.parts?.faithfulness)}>{pct(bd?.generation?.parts?.faithfulness)}</b></div>
                          <div className="ev4-hero-row"><span>Correctness</span><b className={scoreClass(bd?.generation?.parts?.correctness)}>{pct(bd?.generation?.parts?.correctness)}</b></div>
                        </div>
                        <div className="ev4-hero-col">
                          <div className="ev4-hero-col-t">Performance <span>{bd?.performance?.weight}%</span></div>
                          <div className="ev4-hero-row"><span>Latency</span><b>{ms(bd?.performance?.parts?.latency_ms)}</b></div>
                          <div className="ev4-hero-row"><span>Cost/query</span><b>{money(bd?.performance?.parts?.cost_per_query)}</b></div>
                        </div>
                      </div>
                      {powered && (
                        <div className="ev4-powered">
                          Evaluation powered by:
                          <span className="ev3-chip">✓ Mathematical retrieval metrics</span>
                          {powered.context_answer === "ragas" && <span className="ev3-chip">✓ Ragas</span>}
                          {powered.correctness && powered.correctness !== "none" && (
                            <span className="ev3-chip">✓ Independent judge · {powered.correctness}</span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* ── metric tiles by family ── */}
                <div className="ev-src-t">Retrieval — pure math, no AI</div>
                <div className="ev2-tiles">
                  {[
                    ["Recall@K", openRun.metrics.recall_at_k],
                    ["Precision@K", openRun.metrics.precision_at_k],
                    ["MRR", openRun.metrics.mrr],
                    ["NDCG", openRun.metrics.ndcg],
                  ].map(([l, v]) => (
                    <div key={l} className={`ev2-tile ${scoreClass(v)}`}>
                      <div className="ev2-tile-v">{pct(v)}</div>
                      <div className="ev2-tile-l">{l}</div>
                    </div>
                  ))}
                </div>
                <div className="ev-src-t" style={{ marginTop: 10 }}>Context &amp; answer — Ragas</div>
                <div className="ev2-tiles">
                  {[
                    ["Ctx recall", openRun.metrics.context_recall],
                    ["Ctx precision", openRun.metrics.context_precision],
                    ["Faithfulness", openRun.metrics.faithfulness],
                    ["Relevancy", openRun.metrics.answer_relevancy],
                    ["Correctness ⚖️", openRun.metrics.correctness],
                  ].map(([l, v]) => (
                    <div key={l} className={`ev2-tile ${scoreClass(v)}`}>
                      <div className="ev2-tile-v">{pct(v)}</div>
                      <div className="ev2-tile-l">{l}</div>
                    </div>
                  ))}
                </div>
                <div className="ev-src-t" style={{ marginTop: 10 }}>Performance — measured</div>
                <div className="ev2-tiles">
                  <div className="ev2-tile"><div className="ev2-tile-v">{ms(openRun.metrics.avg_retrieval_ms)}</div><div className="ev2-tile-l">Retrieval</div></div>
                  <div className="ev2-tile"><div className="ev2-tile-v">{ms(openRun.metrics.avg_answer_ms)}</div><div className="ev2-tile-l">Answer</div></div>
                  <div className="ev2-tile"><div className="ev2-tile-v">{openRun.metrics.est_tokens_per_query != null ? Math.round(openRun.metrics.est_tokens_per_query) : "—"}</div><div className="ev2-tile-l">Tokens/query (est.)</div></div>
                  <div className="ev2-tile"><div className="ev2-tile-v">{money(openRun.metrics.est_cost_per_query)}</div><div className="ev2-tile-l">Cost/query (est.)</div></div>
                </div>

                {/* per-category */}
                {openRun.metrics.by_category && Object.keys(openRun.metrics.by_category).length > 0 && (
                  <>
                    <div className="ev-src-t" style={{ marginTop: 14 }}>By category</div>
                    <table className="ev-table">
                      <thead><tr><th>Category</th><th>Cases</th><th>Recall@K</th><th>MRR</th><th>Faithfulness</th><th>Correctness</th></tr></thead>
                      <tbody>
                        {Object.entries(openRun.metrics.by_category).map(([cat, m]) => (
                          <tr key={cat}>
                            <td><span className="ev-method">{cat}</span></td>
                            <td>{m.cases}</td>
                            <td className={scoreClass(m.recall_at_k)}>{pct(m.recall_at_k)}</td>
                            <td>{pct(m.mrr)}</td>
                            <td className={scoreClass(m.faithfulness)}>{pct(m.faithfulness)}</td>
                            <td className={scoreClass(m.correctness)}>{pct(m.correctness)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                )}

                {/* health report */}
                {openRun.metrics.recommendations?.length > 0 && (
                  <div className="ev2-recs">
                    <div className="ev-src-t">RAG health report</div>
                    {openRun.metrics.recommendations.map((r, i) => (
                      <div key={i} className="ev2-rec">💡 {r}</div>
                    ))}
                  </div>
                )}

                {/* per-case debugging */}
                {openRun.results?.length > 0 && (
                  <>
                    <div className="ev-src-t" style={{ marginTop: 16 }}>
                      Case debugging · {openRun.results.length}
                    </div>
                    {openRun.results.map((c, i) => (
                      <details key={c.case_id || i} className="ev-run ev-run-old">
                        <summary className="ev-q">
                          <span className="ev-q-badge">{c.hit === false ? "✗" : c.hit ? "✓" : "•"}</span>
                          <span className="ev-doc" style={{ maxWidth: 420 }}>{c.question}</span>
                          <span className="ev-q-meta">{c.category}{c.correctness != null ? ` · correct ${pct(c.correctness)}` : ""}</span>
                        </summary>
                        <div className="ev2-rec" style={{ marginTop: 6 }}>{c.analysis}</div>
                        {c.reason && (
                          <div className="ev4-reason">⚖️ Judge: {c.reason}</div>
                        )}
                        {c.expected?.document && (
                          <div className="rag-cfg-hint" style={{ margin: "4px 0" }}>
                            Expected: {c.expected.document}{c.expected.page != null ? ` · p.${c.expected.page}` : ""}
                          </div>
                        )}
                        {c.timings && (
                          <div className="rag-cfg-hint" style={{ margin: "4px 0" }}>
                            ⏱ analyze {ms(c.timings.analyze)} · embed {ms(c.timings.embed)} ·
                            retrieve {ms(c.timings.retrieve)} · fuse {ms(c.timings.fuse)}
                            {c.answer_ms != null ? ` · LLM ${ms(c.answer_ms)}` : ""}
                          </div>
                        )}
                        {c.top_sources?.length > 0 && (
                          <table className="ev-table">
                            <thead><tr><th>#</th><th>Retrieved</th><th>Page</th><th>Score</th><th>Found by</th><th /></tr></thead>
                            <tbody>
                              {c.top_sources.map((s, j) => (
                                <tr key={j}>
                                  <td>{j + 1}</td>
                                  <td className="ev-doc" style={{ maxWidth: 260 }}>{s.document}</td>
                                  <td>{s.page}</td>
                                  <td>{s.score}</td>
                                  <td><span className="ev-method">{s.method}</span></td>
                                  <td>{s.relevant === true ? "✅" : s.relevant === false ? "—" : ""}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </details>
                    ))}
                  </>
                )}
              </>
            )}

            {/* experiments comparison */}
            {runs.length > 0 && (
              <>
                <div className="ev-src-t" style={{ marginTop: 16 }}>Experiments</div>
                <table className="ev-table">
                  <thead><tr><th>Date</th><th>Config</th><th>Recall</th><th>Correctness</th><th>Cost</th><th>Score</th><th>Δ prev</th><th /></tr></thead>
                  <tbody>
                    {runs.map((r, i) => {
                      const h = r.metrics?.overall_score;
                      const hPrev = i + 1 < runs.length ? runs[i + 1].metrics?.overall_score : null;
                      const delta = h != null && hPrev != null ? h - hPrev : null;
                      return (
                        <tr key={r.id} className={openRun?.id === r.id ? "ev2-row-active" : ""}>
                          <td>{(r.created_at || "").slice(0, 16).replace("T", " ")}</td>
                          <td className="ev-doc" style={{ maxWidth: 300 }}>
                            {r.config?.embedding} · {r.config?.chunk_strategy} · {r.config?.retrieval_profile}
                            {r.config?.rerank ? " · rerank" : ""} · {r.config?.llm}
                          </td>
                          <td>{pct(r.metrics?.recall_at_k)}</td>
                          <td>{pct(r.metrics?.correctness)}</td>
                          <td>{money(r.metrics?.est_cost_per_query)}</td>
                          <td className={scoreClass((h ?? 0) / 100)}>
                            {h != null ? `${h}/100` : "—"}
                            {best?.id === r.id && runs.length > 1 ? " ⭐" : ""}
                          </td>
                          <td className={delta == null ? "" : delta >= 0 ? "good" : "bad"}>
                            {delta == null ? "—" : `${delta > 0 ? "↑" : delta < 0 ? "↓" : "="} ${Math.abs(delta)}`}
                          </td>
                          <td><button className="rag-btn rag-btn-xs" onClick={() => viewRun(r)}>View</button></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </>
            )}
            {!openRun && runs.length === 0 && !running && (
              <div className="ev-empty">
                <div className="ev-empty-t">No experiments yet</div>
                <div className="ev-empty-s">Build a dataset above, then run your first evaluation.</div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default EvaluationPanel;
