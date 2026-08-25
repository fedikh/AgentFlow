import React, { useEffect, useRef, useState } from "react";
import {
  BookOpen, Check, ChevronDown, ChevronRight, Database, Download, FileText,
  Play, RefreshCw, Sparkles, Trash2, Upload,
} from "lucide-react";
import {
  addExample, addGlossary, dataJobStatus, deleteExample, deleteGlossary,
  executeSql, getKnowledgeStats, getSourceSchema, importExamplesCsv,
  importGlossaryCsv, introspectSource, listExamples, listGlossary,
  trainSource, updateSourceTable, verifyExample,
} from "../../../services/dataAgentApi";
import DocumentsPanel from "./DocumentsPanel";
import { card, ink, mono } from "../../dashboard/tokens";
import { btn, inputStyle } from "./ui";

/*
 * KnowledgePanel — ONE page for everything the agent learns, replacing the
 * separate "Schema & Training" and "Business knowledge" steps:
 *
 *   header   Introspect · Train (they act on the WHOLE knowledge base) +
 *            a quiet stats line + the job progress bar
 *   tabs     Schema · SQL pairs · Glossary · Documents — flat segmented
 *            control, contextual actions (CSV import) appear per tab
 *
 * All indexes are trained together, so splitting them across pages only
 * hid the Train button from half of its inputs.
 */

/* ── CSV templates (client-side: no request, always in sync with parser) ── */
const TEMPLATES = {
  examples: {
    file: "prompt-sql-pairs-template.csv",
    body:
      "question,sql,verified\n" +
      '"How many users are there?","SELECT COUNT(*) FROM users",true\n' +
      '"Top 5 customers by revenue","SELECT c.name, SUM(o.total) AS revenue ' +
      "FROM customers c JOIN orders o ON o.customer_id = c.id " +
      'GROUP BY c.name ORDER BY revenue DESC LIMIT 5",true\n' +
      '"Orders created last month","SELECT * FROM orders WHERE created_at >= ' +
      "date_trunc('month', now() - interval '1 month')\",false\n",
    hint: "Columns: question, sql, verified (true/false). Only verified rows are trained.",
  },
  glossary: {
    file: "glossary-template.csv",
    body:
      "term,definition\n" +
      '"chiffre d\'affaires","Somme des montants factures aux clients sur la ' +
      'periode : SUM(orders.total)"\n' +
      '"client actif","Un client ayant passe au moins une commande dans les ' +
      '90 derniers jours"\n' +
      '"collaborateur RH","Un utilisateur rattache au departement Rh via ' +
      'la table user_departments"\n',
    hint: "Columns: term, definition. Name the tables/columns the term maps to.",
  },
};

function downloadTemplate(kind) {
  const t = TEMPLATES[kind];
  const blob = new Blob(["﻿" + t.body], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = t.file;
  a.click();
  URL.revokeObjectURL(url);
}

/* compact ghost button — contextual actions stay quiet */
const ghost = {
  display: "inline-flex", alignItems: "center", gap: 5,
  border: `1px solid ${ink.line}`, background: "#fff", borderRadius: 8,
  padding: "5px 10px", font: "500 11.5px system-ui", color: ink.muted,
  cursor: "pointer", whiteSpace: "nowrap",
};

function CsvImport({ kind, onFile, importing }) {
  const ref = useRef(null);
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <input ref={ref} type="file" hidden accept=".csv,text/csv"
             onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} />
      <button style={ghost} disabled={importing} onClick={() => ref.current?.click()}>
        <Upload size={11} /> {importing ? "Importing…" : "Import CSV"}
      </button>
      <button style={ghost} onClick={() => downloadTemplate(kind)}
              title={TEMPLATES[kind].hint}>
        <Download size={11} /> Template
      </button>
    </span>
  );
}

/* ── segmented tabs (the results-card pattern, page-level) ── */
const segWrap = {
  display: "inline-flex", gap: 2, padding: 3,
  background: "#EEF2F7", borderRadius: 10,
};
const segBtn = (on) => ({
  display: "inline-flex", alignItems: "center", gap: 6, border: "none",
  background: on ? "#fff" : "transparent", borderRadius: 8, padding: "6px 13px",
  font: "600 12.5px system-ui", color: on ? ink.primary : ink.muted,
  cursor: "pointer", boxShadow: on ? "0 1px 2px rgba(15,23,42,0.10)" : "none",
  transition: "background .12s, color .12s",
});
const segCount = (on) => ({
  font: "700 10px system-ui", padding: "1px 6px", borderRadius: 999,
  background: on ? "#EFF6FF" : "#E2E8F0", color: on ? ink.blue : ink.muted,
  fontVariantNumeric: "tabular-nums",
});

export default function KnowledgePanel({ source, onChanged, setError }) {
  const [tab, setTab] = useState("schema");

  /* ── schema + jobs (introspect / train act on the whole knowledge base) ── */
  const [schema, setSchema] = useState([]);
  const [openTables, setOpenTables] = useState({});
  const [tableFilter, setTableFilter] = useState("");
  const [job, setJob] = useState(null);
  const [indexed, setIndexed] = useState(null);     // {ddl, sql, business}
  const pollRef = useRef(null);

  /* ── examples & glossary ── */
  const [examples, setExamples] = useState([]);
  const [exQ, setExQ] = useState("");
  const [exSql, setExSql] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [terms, setTerms] = useState([]);
  const [term, setTerm] = useState("");
  const [definition, setDefinition] = useState("");
  const [importing, setImporting] = useState("");
  const [importReport, setImportReport] = useState(null);

  const refreshAll = () => {
    getSourceSchema(source.id).then(setSchema).catch(() => setSchema([]));
    getKnowledgeStats(source.id).then(setIndexed).catch(() => {});
    listExamples(source.id).then(setExamples).catch(() => {});
    listGlossary(source.id).then(setTerms).catch(() => {});
  };
  useEffect(() => {
    refreshAll();
    return () => clearInterval(pollRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source.id]);

  const runJob = async (kind, starter) => {
    try {
      const { job_id: jobId } = await starter(source.id);
      setJob({ kind, status: "running", done: 0, total: 0 });
      pollRef.current = setInterval(async () => {
        try {
          const st = await dataJobStatus(jobId);
          setJob({ kind, ...st });
          if (st.status !== "running") {
            clearInterval(pollRef.current);
            onChanged();
            refreshAll();
          }
        } catch {
          clearInterval(pollRef.current);
        }
      }, 1200);
    } catch (e) {
      setError(e.message);
    }
  };

  const patchTable = async (t, d) => {
    setSchema((l) => l.map((x) => (x.id === t.id ? { ...x, ...d } : x)));
    try {
      await updateSourceTable(source.id, t.id, d);
      onChanged();
    } catch (e) {
      setError(e.message);
    }
  };

  const wrap = (fn) => async (...args) => {
    try {
      await fn(...args);
      refreshAll();
      onChanged();
    } catch (e) {
      setError(e.message);
    }
  };

  const runExample = async () => {
    if (!exSql.trim()) return;
    setTesting(true);
    setTestResult(null);
    try {
      const r = await executeSql(source.id, exSql);
      setTestResult({ ok: true, rows: r.row_count });
    } catch (e) {
      setTestResult({ ok: false, error: e.message });
    } finally {
      setTesting(false);
    }
  };

  const saveExample = wrap(async (verified) => {
    if (!exQ.trim() || !exSql.trim()) return;
    await addExample(source.id, exQ, exSql, verified);
    setExQ(""); setExSql(""); setTestResult(null);
  });

  const saveTerm = wrap(async () => {
    if (!term.trim() || !definition.trim()) return;
    await addGlossary(source.id, term, definition);
    setTerm(""); setDefinition("");
  });

  const doImport = (kind, fn) => async (file) => {
    if (!file) return;
    setImporting(kind);
    setImportReport(null);
    try {
      const r = await fn(source.id, file);
      setImportReport({ kind, ...r });
      refreshAll();
      onChanged();
    } catch (e) {
      setError(e.message);
    } finally {
      setImporting("");
    }
  };

  const verifiedCount = examples.filter((e) => e.is_verified).length;
  const running = job?.status === "running";
  const filteredSchema = tableFilter.trim()
    ? schema.filter((t) =>
        `${t.schema}.${t.table}`.toLowerCase().includes(tableFilter.trim().toLowerCase()))
    : schema;

  const statsLine = source.table_count
    ? `${source.table_count} tables · ${source.mode} mode` +
      (indexed
        ? ` · indexed: ${indexed.ddl} DDL · ${indexed.sql} SQL · ${indexed.business} business`
        : "")
    : "Introspect the database, curate the tables, add business knowledge — one Train indexes it all.";

  const TABS = [
    { key: "schema", label: "Schema", icon: <Database size={13} />,
      count: schema.length || null },
    { key: "examples", label: "SQL pairs", icon: <Play size={13} />,
      count: examples.length ? `${verifiedCount}/${examples.length}` : null },
    { key: "glossary", label: "Glossary", icon: <BookOpen size={13} />,
      count: terms.length || null },
    { key: "documents", label: "Documents", icon: <FileText size={13} />,
      count: null },
  ];

  return (
    <div style={{ ...card, display: "grid", gap: 14 }}>
      {/* ── header: the two whole-base actions + the stats line ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 13.5, color: ink.primary }}>
            Knowledge
          </div>
          <div style={{ fontSize: 11.5, color: ink.muted, marginTop: 2 }}>
            {statsLine}
          </div>
        </div>
        <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button style={btn(false)} disabled={running}
                  onClick={() => runJob("introspect", introspectSource)}>
            <RefreshCw size={14} /> Introspect
          </button>
          <button style={btn(true)} disabled={running || !schema.length}
                  title={!schema.length ? "Introspect first" : "Index schema + SQL pairs + glossary into the agent"}
                  onClick={() => runJob("train", trainSource)}>
            <Sparkles size={14} /> Train
          </button>
        </span>
      </div>

      {job && (
        <div style={{ display: "grid", gap: 6 }}>
          <div style={{ fontSize: 12.5, color: ink.primary, fontWeight: 600 }}>
            {job.kind === "introspect" ? "Introspecting" : "Training"} — {job.status}
            {job.step ? ` · ${job.step}` : ""}{job.total ? ` · ${job.done}/${job.total}` : ""}
            {job.error ? ` · ${job.error}` : ""}
          </div>
          {running && (
            <div style={{ height: 7, background: "#EEF2F5", borderRadius: 4 }}>
              <div style={{
                width: job.total ? `${Math.round((job.done / job.total) * 100)}%` : "30%",
                height: "100%", background: ink.blue, borderRadius: 4,
                transition: "width .4s",
              }} />
            </div>
          )}
        </div>
      )}

      {/* ── tabs + contextual actions ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap",
                    borderTop: `1px solid ${ink.line}`, paddingTop: 14 }}>
        <div style={segWrap}>
          {TABS.map((t) => (
            <button key={t.key} style={segBtn(tab === t.key)}
                    onClick={() => setTab(t.key)}>
              {t.icon} {t.label}
              {t.count != null && (
                <span style={segCount(tab === t.key)}>{t.count}</span>
              )}
            </button>
          ))}
        </div>
        <span style={{ marginLeft: "auto" }}>
          {tab === "examples" && (
            <CsvImport kind="examples" importing={importing === "examples"}
                       onFile={doImport("examples", importExamplesCsv)} />
          )}
          {tab === "glossary" && (
            <CsvImport kind="glossary" importing={importing === "glossary"}
                       onFile={doImport("glossary", importGlossaryCsv)} />
          )}
        </span>
      </div>

      {importReport && (
        <div className="rag-cfg-hint" style={{ margin: 0 }}>
          <strong>{importReport.imported} row(s) imported</strong>
          {importReport.verified != null && ` · ${importReport.verified} verified`}
          {(importReport.errors || []).length > 0 && (
            <div style={{ marginTop: 4, color: "#92400E" }}>
              Skipped: {importReport.errors.join(" · ")}
            </div>
          )}
        </div>
      )}

      {/* ═══ SCHEMA — curate the table tree the agent is trained on ═══ */}
      {tab === "schema" && (
        <div style={{ display: "grid", gap: 8 }}>
          {schema.length > 6 && (
            <input style={{ ...inputStyle, maxWidth: 280, fontSize: 12.5 }}
                   value={tableFilter}
                   onChange={(e) => setTableFilter(e.target.value)}
                   placeholder="Filter tables…" />
          )}
          {filteredSchema.map((t) => (
            <div key={t.id} style={{
              border: `1px solid ${ink.line}`, borderRadius: 10,
              padding: "10px 12px", opacity: t.is_enabled ? 1 : 0.55,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                <button onClick={() => setOpenTables((o) => ({ ...o, [t.id]: !o[t.id] }))}
                        style={{ border: "none", background: "none", cursor: "pointer",
                                 color: ink.muted, display: "inline-flex" }}>
                  {openTables[t.id] ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                </button>
                <span style={{ fontWeight: 700, fontSize: 13, color: ink.primary }}>
                  {t.schema}.{t.table}
                </span>
                <span style={{ fontSize: 11, color: ink.faint }}>
                  {t.columns.length} cols{t.row_estimate != null ? ` · ~${t.row_estimate} rows` : ""}
                </span>
                <label style={{ marginLeft: "auto", fontSize: 11.5, color: ink.muted,
                                display: "inline-flex", gap: 6, alignItems: "center",
                                cursor: "pointer" }}>
                  <input type="checkbox" checked={t.is_enabled}
                         onChange={(e) => patchTable(t, { is_enabled: e.target.checked })} />
                  enabled
                </label>
              </div>
              <input
                style={{ ...inputStyle, marginTop: 8, fontSize: 12.5 }}
                defaultValue={t.description || ""}
                placeholder="Describe this table (business meaning) — trained into the agent"
                onBlur={(e) => e.target.value !== (t.description || "") &&
                               patchTable(t, { description: e.target.value })}
              />
              {openTables[t.id] && (
                <div style={{ marginTop: 10, display: "grid", gap: 4 }}>
                  {t.columns.map((c) => (
                    <div key={c.name} style={{ display: "flex", gap: 8, fontSize: 12, ...mono }}>
                      <span style={{ color: ink.primary, fontWeight: 600, minWidth: 180 }}>{c.name}</span>
                      <span style={{ color: ink.muted }}>{c.data_type}</span>
                      {c.pk && <span style={{ color: "#1D4ED8", fontWeight: 700 }}>PK</span>}
                      {c.fk_ref && <span style={{ color: ink.faint }}>→ {c.fk_ref}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {!schema.length && (
            <div style={{ fontSize: 12.5, color: ink.muted }}>
              No schema yet — run <strong>Introspect</strong> after the connection
              test passes.
            </div>
          )}
          {schema.length > 0 && !filteredSchema.length && (
            <div style={{ fontSize: 12.5, color: ink.muted }}>
              No table matches “{tableFilter}”.
            </div>
          )}
        </div>
      )}

      {/* ═══ SQL PAIRS — the strongest signal, only verified pairs train ═══ */}
      {tab === "examples" && (
        <div style={{ display: "grid", gap: 8 }}>
          <input className="rag-cfg-select" value={exQ}
                 onChange={(e) => setExQ(e.target.value)}
                 placeholder="Question — e.g. How many active customers this month?" />
          <textarea className="rag-cfg-select" rows={3} value={exSql}
                    onChange={(e) => setExSql(e.target.value)}
                    style={{ fontFamily: "ui-monospace, Consolas, monospace", fontSize: 12 }}
                    placeholder="SELECT …" />
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <button className="rag-btn rag-btn-sm" onClick={runExample}
                    disabled={testing || !exSql.trim()}>
              {testing ? "Running…" : "Run this SQL"}
            </button>
            <button className="rag-btn rag-btn-sm" onClick={() => saveExample(false)}
                    disabled={!exQ.trim() || !exSql.trim()}>
              Save as draft
            </button>
            <button className="rag-btn rag-btn-sm rag-btn-blue"
                    onClick={() => saveExample(true)}
                    disabled={!exQ.trim() || !exSql.trim()}>
              Save &amp; verify
            </button>
            {testResult && (
              <span style={{ fontSize: 12, color: testResult.ok ? "#166534" : "#B91C1C" }}>
                {testResult.ok ? `✓ ${testResult.rows} row(s)` : `✗ ${testResult.error}`}
              </span>
            )}
          </div>

          <div style={{ display: "grid", gap: 7, marginTop: 6 }}>
            {examples.length === 0 && (
              <div className="rag-cfg-hint">
                No examples yet — add the three or four questions your users ask
                most, or import a CSV (question, sql, verified). Only verified
                pairs are trained.
              </div>
            )}
            {examples.map((e) => (
              <div key={e.id} style={{ border: `1px solid ${ink.line}`,
                                       borderRadius: 10, padding: "9px 12px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{
                    fontSize: 9.5, fontWeight: 800, padding: "2px 7px",
                    borderRadius: 20,
                    background: e.is_verified ? "#F0FDF4" : "#F1F5F9",
                    color: e.is_verified ? "#166534" : "#64748B",
                  }}>
                    {e.is_verified ? "VERIFIED" : "DRAFT"}
                  </span>
                  <span style={{ fontWeight: 600, fontSize: 12.5, flex: 1, minWidth: 0,
                                 overflow: "hidden", textOverflow: "ellipsis",
                                 whiteSpace: "nowrap" }}>
                    {e.question}
                  </span>
                  <button className="ev-suggest" title="Toggle verified"
                          onClick={wrap(() => verifyExample(source.id, e.id))}>
                    <Check size={12} />
                  </button>
                  <button className="ev-suggest" title="Delete"
                          onClick={wrap(() => deleteExample(source.id, e.id))}>
                    <Trash2 size={12} />
                  </button>
                </div>
                <div style={{ fontFamily: "ui-monospace, Consolas, monospace",
                              fontSize: 11.5, color: ink.muted, marginTop: 5,
                              whiteSpace: "pre-wrap" }}>
                  {e.sql}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ═══ GLOSSARY — the vocabulary the schema cannot express ═══ */}
      {tab === "glossary" && (
        <div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <input className="rag-cfg-select" style={{ flex: "0 0 220px" }} value={term}
                   onChange={(e) => setTerm(e.target.value)} placeholder="Term" />
            <input className="rag-cfg-select" style={{ flex: 1, minWidth: 220 }}
                   value={definition}
                   onChange={(e) => setDefinition(e.target.value)}
                   placeholder="Definition — name the tables/columns it maps to" />
            <button className="rag-btn rag-btn-blue rag-btn-sm" onClick={saveTerm}
                    disabled={!term.trim() || !definition.trim()}>
              Add term
            </button>
          </div>
          <div style={{ display: "grid", gap: 6, marginTop: 12 }}>
            {terms.length === 0 && (
              <div className="rag-cfg-hint">
                No terms yet. Example — <em>workers of a department</em> → “the
                users linked through user_departments to that department”.
              </div>
            )}
            {terms.map((g) => (
              <div key={g.id} style={{ display: "flex", gap: 10, alignItems: "baseline",
                                       fontSize: 12.5, borderBottom: "1px dashed #EDF1F5",
                                       paddingBottom: 6 }}>
                <span style={{ fontWeight: 700, minWidth: 150 }}>{g.term}</span>
                <span style={{ color: ink.muted, flex: 1 }}>{g.definition}</span>
                <button className="ev-suggest"
                        onClick={wrap(() => deleteGlossary(source.id, g.id))}>
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ═══ DOCUMENTS — the RAG pipeline over the hidden knowledge space ═══ */}
      {tab === "documents" && (
        <DocumentsPanel source={source} setError={setError} />
      )}
    </div>
  );
}
