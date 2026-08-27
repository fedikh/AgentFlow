import React, { useEffect, useRef, useState } from "react";
import {
  Check, ChevronDown, ChevronRight, Download, FlaskConical, Play, Plus,
  Trash2, Upload, Users,
} from "lucide-react";
import {
  dataJobStatus, daEvalAddCase, daEvalClearCases, daEvalDeleteCase,
  daEvalGenerate, daEvalImportExamples, daEvalListCases, daEvalRunAsync,
  daEvalRunDelete, daEvalRunDetail, daEvalRuns, daEvalTemplate,
  daEvalUpdateCase, daEvalUploadFile, daEvalVerifyCase,
} from "../../../services/dataAgentApi";
import EvalRunResults from "./EvalRunResults";

/*
 * AutoEvalPanel — the RAG auto-evaluation tab, for NL→SQL:
 *
 *   dataset   question → GOLD SQL cases (import verified examples · upload ·
 *             LLM generation · manual). Generated/uploaded gold SQL starts
 *             UNVERIFIED — a dry-run through the validator chain proves it.
 *   run       every verified case through the real agent; gold and generated
 *             SQL both execute and their RESULT SETS are compared.
 *   results   execution accuracy + reliability + latency/cost + per-case
 *             gold-vs-generated trace. Runs are kept for comparison.
 */

const CATEGORIES = ["aggregation", "join", "filter", "date", "ranking",
                    "grouping", "subquery", "insufficient"];

const ghost = {
  display: "inline-flex", alignItems: "center", gap: 5,
  border: "1px solid #E5E9F0", background: "#fff", borderRadius: 8,
  padding: "5px 10px", font: "500 11.5px system-ui", color: "#64748B",
  cursor: "pointer", whiteSpace: "nowrap",
};

export default function AutoEvalPanel({ source, setError, testable }) {
  const [cases, setCases] = useState([]);
  const [runs, setRuns] = useState([]);
  const [openRun, setOpenRun] = useState(null);
  const [openCase, setOpenCase] = useState(null);   // id → SQL editor open
  const [sqlDraft, setSqlDraft] = useState("");
  const [busy, setBusy] = useState("");
  const [genN, setGenN] = useState(8);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ question: "", gold_sql: "", category: "filter" });
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(null);
  const fileRef = useRef(null);
  const pollRef = useRef(null);

  const load = () => {
    daEvalListCases(source.id).then((r) => setCases(r.cases || [])).catch(() => {});
    daEvalRuns(source.id).then((r) => setRuns(r.runs || [])).catch(() => {});
  };
  useEffect(() => {
    load();
    return () => clearInterval(pollRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source.id]);

  const act = (key, fn, reload = true) => async (...args) => {
    setBusy(key);
    try {
      const out = await fn(...args);
      if (reload) load();
      return out;
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  const importExamples = act("import", async () => {
    const r = await daEvalImportExamples(source.id);
    if (r && !r.imported) setError("No new verified examples to import");
  });
  const generate = act("generate", async () => {
    const r = await daEvalGenerate(source.id, genN);
    if (r?.error) setError(r.error);
  });
  const onFile = act("upload", async (file) => {
    if (file) await daEvalUploadFile(source.id, file);
  });
  const addCase = act("add", async () => {
    await daEvalAddCase(source.id, {
      question: form.question, gold_sql: form.gold_sql || undefined,
      category: form.category,
    });
    setForm({ question: "", gold_sql: "", category: "filter" });
    setShowAdd(false);
  });
  const verifyCase = (id) => act(`verify-${id}`, () => daEvalVerifyCase(source.id, id))();
  const saveSql = (id) => act(`save-${id}`, async () => {
    await daEvalUpdateCase(source.id, id, { gold_sql: sqlDraft });
    await daEvalVerifyCase(source.id, id);      // prove the new gold immediately
    setOpenCase(null);
  })();
  const removeCase = (id) => act("del", () => daEvalDeleteCase(source.id, id))();
  const clearAll = () => {
    if (!window.confirm("Delete ALL test cases?")) return;
    act("clear", () => daEvalClearCases(source.id))();
  };
  const downloadTemplate = async () => {
    try {
      const t = await daEvalTemplate(source.id);
      const url = URL.createObjectURL(new Blob([JSON.stringify(t, null, 2)],
                                               { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = "data-agent-eval-template.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message);
    }
  };

  const runExperiment = async () => {
    setRunning(true);
    setProgress({ done: 0, total: 0, step: "Starting…" });
    setOpenRun(null);
    try {
      const { job_id: jobId } = await daEvalRunAsync(source.id);
      pollRef.current = setInterval(async () => {
        try {
          const st = await dataJobStatus(jobId);
          setProgress(st);
          if (st.status !== "running") {
            clearInterval(pollRef.current);
            setRunning(false);
            setProgress(null);
            if (st.status === "error") setError(st.error || "Evaluation failed");
            else {
              setOpenRun(st.result);
              load();
            }
          }
        } catch {
          clearInterval(pollRef.current);
          setRunning(false);
          setProgress(null);
        }
      }, 1500);
    } catch (e) {
      setError(e.message);
      setRunning(false);
      setProgress(null);
    }
  };

  const viewRun = async (r) => {
    try { setOpenRun(await daEvalRunDetail(source.id, r.id)); }
    catch (e) { setError(e.message); }
  };
  const deleteRun = async (r) => {
    if (!window.confirm("Delete this run?")) return;
    setRuns((l) => l.filter((x) => x.id !== r.id));
    if (openRun?.id === r.id) setOpenRun(null);
    try { await daEvalRunDelete(source.id, r.id); } catch { /* optimistic */ }
  };

  const verified = cases.filter((c) => c.verified);
  const pctAcc = (r) => {
    const v = r.metrics?.accuracy?.execution_accuracy;
    return v == null ? "—" : `${Math.round(v * 100)}%`;
  };

  return (
    <div style={{ display: "grid", gap: 12, alignContent: "start",
                  overflowY: "auto", minHeight: 0 }}>
      {/* ═══ dataset card ═══ */}
      <div style={{ border: "1px solid #E5E9F0", borderRadius: 12,
                    background: "#fff", padding: "13px 16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8,
                      flexWrap: "wrap" }}>
          <span style={{ font: "700 13px system-ui", color: "#0F172A" }}>
            Test dataset
          </span>
          <span style={{ fontSize: 10.5, fontWeight: 700, padding: "1px 8px",
                         borderRadius: 20, background: "#F1F5F9",
                         color: "#64748B" }}>
            {verified.length}/{cases.length} verified
          </span>
          <span style={{ marginLeft: "auto", display: "inline-flex", gap: 6,
                         flexWrap: "wrap" }}>
            <button style={ghost} disabled={!!busy} onClick={importExamples}
                    title="Copy the agent's verified question→SQL pairs">
              <Users size={11} /> {busy === "import" ? "Importing…" : "Import examples"}
            </button>
            <input ref={fileRef} type="file" hidden accept=".csv,.xlsx,.xlsm,.json"
                   onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} />
            <button style={ghost} disabled={!!busy}
                    onClick={() => fileRef.current?.click()}>
              <Upload size={11} /> {busy === "upload" ? "Uploading…" : "Upload file"}
            </button>
            <span style={{ display: "inline-flex", gap: 4, alignItems: "center" }}>
              <button style={ghost} disabled={!!busy || !testable} onClick={generate}
                      title={testable ? "The agent's LLM proposes cases from the schema"
                                      : "Train the agent first"}>
                <FlaskConical size={11} /> {busy === "generate" ? "Generating…" : "Generate"}
              </button>
              <input type="number" min={3} max={15} value={genN}
                     onChange={(e) => setGenN(Number(e.target.value) || 8)}
                     style={{ width: 46, border: "1px solid #E5E9F0", borderRadius: 8,
                              padding: "4px 6px", font: "500 11.5px system-ui" }} />
            </span>
            <button style={ghost} onClick={downloadTemplate}>
              <Download size={11} /> Template
            </button>
            <button style={ghost} onClick={() => setShowAdd((v) => !v)}>
              <Plus size={11} /> Add
            </button>
            {cases.length > 0 && (
              <button style={{ ...ghost, color: "#B91C1C" }} onClick={clearAll}>
                <Trash2 size={11} />
              </button>
            )}
          </span>
        </div>

        {showAdd && (
          <div style={{ display: "grid", gap: 7, marginTop: 10 }}>
            <input className="rag-cfg-select" value={form.question}
                   placeholder="Question — e.g. How many orders were placed last month?"
                   onChange={(e) => setForm((f) => ({ ...f, question: e.target.value }))} />
            <textarea className="rag-cfg-select" rows={3} value={form.gold_sql}
                      placeholder="Gold SQL — the CORRECT SELECT (empty only for category=insufficient)"
                      style={{ fontFamily: "ui-monospace, Consolas, monospace", fontSize: 12 }}
                      onChange={(e) => setForm((f) => ({ ...f, gold_sql: e.target.value }))} />
            <div style={{ display: "flex", gap: 8 }}>
              <select className="rag-cfg-select" style={{ width: 180 }}
                      value={form.category}
                      onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}>
                {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
              </select>
              <button className="rag-btn rag-btn-sm rag-btn-blue" onClick={addCase}
                      disabled={!form.question.trim() ||
                                (!form.gold_sql.trim() && form.category !== "insufficient")}>
                Add case
              </button>
            </div>
          </div>
        )}

        {cases.length === 0 ? (
          <div className="rag-cfg-hint" style={{ marginTop: 10 }}>
            No test cases yet — import the agent&apos;s verified examples, generate
            proposals from the schema, or upload a file (question + gold SQL).
            Aim for at least 10.
          </div>
        ) : (
          <table className="ev-table" style={{ marginTop: 10 }}>
            <thead>
              <tr><th style={{ width: 20 }} /><th>Question</th><th>Type</th>
                  <th>Status</th><th style={{ width: 90 }} /></tr>
            </thead>
            <tbody>
              {cases.map((c) => {
                const open = openCase === c.id;
                return (
                  <React.Fragment key={c.id}>
                    <tr>
                      <td style={{ color: "#94A3B8", cursor: "pointer" }}
                          onClick={() => {
                            setOpenCase(open ? null : c.id);
                            setSqlDraft(c.gold_sql || "");
                          }}>
                        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                      </td>
                      <td style={{ maxWidth: 360, overflow: "hidden",
                                   textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                          title={c.gold_sql || ""}>
                        {c.question}
                      </td>
                      <td>
                        <span style={{ fontSize: 10, fontWeight: 700, padding: "1px 7px",
                                       borderRadius: 20, background: "#F1F5F9",
                                       color: "#475569" }}>
                          {c.category}
                        </span>
                      </td>
                      <td>
                        <span title={c.gold_note || ""}
                              style={{ fontSize: 10, fontWeight: 800, padding: "2px 7px",
                                       borderRadius: 20,
                                       background: c.verified ? "#F0FDF4" : "#FFFBEB",
                                       color: c.verified ? "#166534" : "#92400E" }}>
                          {c.verified ? "VERIFIED" : "UNVERIFIED"}
                        </span>
                      </td>
                      <td style={{ whiteSpace: "nowrap", textAlign: "right" }}>
                        {!c.verified && (
                          <button className="ev-suggest" title="Dry-run the gold SQL"
                                  disabled={!!busy} onClick={() => verifyCase(c.id)}>
                            <Check size={12} />
                          </button>
                        )}
                        <button className="ev-suggest" title="Delete"
                                onClick={() => removeCase(c.id)}>
                          <Trash2 size={12} />
                        </button>
                      </td>
                    </tr>
                    {open && (
                      <tr>
                        <td colSpan={5} style={{ background: "#FAFBFC" }}>
                          {c.gold_note && (
                            <div style={{ fontSize: 11.5, color: "#92400E",
                                          marginBottom: 6 }}>
                              {c.gold_note}
                            </div>
                          )}
                          <textarea className="rag-cfg-select" rows={3} value={sqlDraft}
                                    style={{ fontFamily: "ui-monospace, Consolas, monospace",
                                             fontSize: 12 }}
                                    onChange={(e) => setSqlDraft(e.target.value)} />
                          <button className="rag-btn rag-btn-sm rag-btn-blue"
                                  style={{ marginTop: 6 }}
                                  disabled={!!busy || !sqlDraft.trim()}
                                  onClick={() => saveSql(c.id)}>
                            Save &amp; verify gold SQL
                          </button>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* ═══ run ═══ */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <button className="rag-btn rag-btn-blue"
                disabled={running || !testable || !verified.length}
                title={!testable ? "Train the agent first"
                  : !verified.length ? "Verify at least one case" : ""}
                onClick={runExperiment}>
          <Play size={13} /> {running ? "Running…"
            : `Run experiment (${verified.length} case${verified.length === 1 ? "" : "s"})`}
        </button>
        <span style={{ fontSize: 11.5, color: "#94A3B8" }}>
          Gold and generated SQL both execute (read-only) — their result sets
          are compared.
        </span>
      </div>

      {progress && (
        <div style={{ display: "grid", gap: 6 }}>
          <div style={{ font: "600 12.5px system-ui", color: "#0F172A" }}>
            Evaluating case {Math.min((progress.done || 0) + 1, progress.total || 1)} of{" "}
            {progress.total || "…"}
            {progress.step ? ` · ${progress.step}` : ""}
          </div>
          <div style={{ height: 7, background: "#EEF2F5", borderRadius: 4 }}>
            <div style={{
              width: progress.total
                ? `${Math.round(((progress.done || 0) / progress.total) * 100)}%` : "20%",
              height: "100%", background: "#2563EB", borderRadius: 4,
              transition: "width .4s",
            }} />
          </div>
        </div>
      )}

      {/* ═══ latest / selected run ═══ */}
      {openRun && <EvalRunResults run={openRun} />}

      {/* ═══ run history ═══ */}
      {runs.length > 0 && (
        <div>
          <div style={{ font: "700 11px system-ui", color: "#64748B",
                        textTransform: "uppercase", letterSpacing: "0.05em",
                        margin: "2px 0 6px" }}>
            Previous runs
          </div>
          <table className="ev-table">
            <thead>
              <tr><th>Date</th><th>Cases</th><th>Duration</th>
                  <th>Exec accuracy</th><th style={{ width: 110 }} /></tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}
                    style={openRun?.id === r.id ? { background: "#EFF6FF" } : undefined}>
                  <td>{new Date(String(r.created_at).replace(" ", "T")).toLocaleString()}</td>
                  <td>{r.num_cases}</td>
                  <td>{Math.round((r.duration_ms || 0) / 1000)}s</td>
                  <td style={{ fontWeight: 700 }}>{pctAcc(r)}</td>
                  <td style={{ whiteSpace: "nowrap", textAlign: "right" }}>
                    <button className="ev-suggest" onClick={() => viewRun(r)}>view</button>
                    <button className="ev-suggest" onClick={() => deleteRun(r)}>
                      <Trash2 size={12} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
