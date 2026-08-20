import React, { useEffect, useRef, useState } from "react";
import {
  BookOpen, Check, ChevronDown, ChevronRight, Download, FileText, Play,
  Trash2, Upload,
} from "lucide-react";
import {
  addExample, addGlossary, deleteExample, deleteGlossary, executeSql,
  importExamplesCsv, importGlossaryCsv, listExamples, listGlossary,
  verifyExample,
} from "../../../services/dataAgentApi";
import DocumentsPanel from "./DocumentsPanel";
import { ink } from "../../dashboard/tokens";

/*
 * BusinessPanel — the knowledge the schema cannot carry, as three
 * collapsible sections:
 *
 *   1. Prompt → SQL pairs   the strongest signal (only VERIFIED pairs train)
 *   2. Business glossary     the vocabulary of the business
 *   3. Knowledge documents   the RAG pipeline (upload · load · parse ·
 *                            chunk · index), rendered by the RAG components
 *
 * The first two accept a CSV import; their templates are generated here so
 * the download is instant and always matches the parser's expectations.
 */

/* ── CSV templates (client-side: no request, no auth, always in sync) ── */
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

/* compact ghost button — the drop-box headers stay quiet */
const ghost = {
  display: "inline-flex", alignItems: "center", gap: 5,
  border: `1px solid ${ink.line}`, background: "#fff", borderRadius: 8,
  padding: "5px 10px", font: "500 11.5px system-ui", color: ink.muted,
  cursor: "pointer", whiteSpace: "nowrap",
};

function CsvImport({ kind, onFile, importing }) {
  const ref = useRef(null);
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          onClick={(e) => e.stopPropagation()}>
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

/* ── the drop-box (accordion) ──────────────────────────────────
 * Self-contained on purpose: `.rag-cfg-panel` is stretched by
 * `.rag-space-content > .rag-cfg-panel { flex: 1 0 auto }`, which turned
 * each collapsed section into a tall empty card. This one is exactly as
 * tall as its content.                                                   */
function Drop({ open, onToggle, icon, title, sub, count, right, children }) {
  const [hover, setHover] = useState(false);
  return (
    <section style={{
      background: "#fff", border: `1px solid ${open ? "#DBEAFE" : ink.line}`,
      borderRadius: 12, overflow: "hidden", flex: "0 0 auto",
      transition: "border-color .15s",
    }}>
      <header
        role="button" tabIndex={0}
        onClick={onToggle}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onToggle()}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        style={{ display: "flex", alignItems: "center", gap: 11,
                 padding: "13px 16px", cursor: "pointer", userSelect: "none",
                 background: hover && !open ? "#FAFBFC" : "#fff" }}
      >
        <span style={{ color: ink.faint, display: "inline-flex",
                       transition: "transform .15s",
                       transform: open ? "rotate(0deg)" : "rotate(0deg)" }}>
          {open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
        </span>
        <span style={{ width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                       background: open ? "#EFF6FF" : "#F1F5F9",
                       color: open ? ink.blue : ink.muted,
                       display: "grid", placeItems: "center" }}>
          {icon}
        </span>
        <span style={{ minWidth: 0, flex: 1 }}>
          <span style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{ fontWeight: 650, fontSize: 13.5, color: ink.primary,
                           letterSpacing: "-0.01em" }}>
              {title}
            </span>
            {count != null && (
              <span style={{ fontSize: 10, fontWeight: 700, padding: "1px 7px",
                             borderRadius: 20, background: "#F1F5F9",
                             color: ink.muted, whiteSpace: "nowrap" }}>
                {count}
              </span>
            )}
          </span>
          <span style={{ display: "block", fontSize: 11.5, color: ink.faint,
                         marginTop: 2, overflow: "hidden",
                         textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {sub}
          </span>
        </span>
        {right}
      </header>
      {open && (
        <div style={{ borderTop: `1px solid ${ink.line}`, padding: "16px" }}>
          {children}
        </div>
      )}
    </section>
  );
}

export default function BusinessPanel({ source, onChanged, setError }) {
  const [open, setOpen] = useState("examples");     // one drop-box at a time
  const toggle = (k) => setOpen((cur) => (cur === k ? "" : k));

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

  const refresh = () => {
    listExamples(source.id).then(setExamples).catch(() => {});
    listGlossary(source.id).then(setTerms).catch(() => {});
  };
  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source.id]);

  const wrap = (fn) => async (...args) => {
    try { await fn(...args); refresh(); onChanged(); }
    catch (e) { setError(e.message); }
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
      refresh();
      onChanged();
    } catch (e) {
      setError(e.message);
    } finally {
      setImporting("");
    }
  };

  const verifiedCount = examples.filter((e) => e.is_verified).length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
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

      {/* ═══ 1 · prompt → SQL pairs ═══ */}
      <Drop
        open={open === "examples"} onToggle={() => toggle("examples")}
        icon={<Play size={15} />} title="Prompt → SQL pairs"
        count={`${verifiedCount}/${examples.length} verified`}
        sub="The strongest signal — the model sees how queries are written here. Only verified pairs are trained."
        right={<CsvImport kind="examples" importing={importing === "examples"}
                          onFile={doImport("examples", importExamplesCsv)} />}
      >
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
        </div>

        <div style={{ display: "grid", gap: 7, marginTop: 14 }}>
          {examples.length === 0 && (
            <div className="rag-cfg-hint">
              No examples yet — add the three or four questions your users ask
              most, or import a CSV (question, sql, verified).
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
      </Drop>

      {/* ═══ 2 · business glossary ═══ */}
      <Drop
        open={open === "glossary"} onToggle={() => toggle("glossary")}
        icon={<BookOpen size={15} />} title="Business glossary"
        count={terms.length}
        sub="Terms the schema cannot express — “chiffre d'affaires”, “client actif”, “collaborateur RH”."
        right={<CsvImport kind="glossary" importing={importing === "glossary"}
                          onFile={doImport("glossary", importGlossaryCsv)} />}
      >
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
      </Drop>

      {/* ═══ 3 · knowledge documents (the RAG pipeline) ═══ */}
      <Drop
        open={open === "documents"} onToggle={() => toggle("documents")}
        icon={<FileText size={15} />} title="Knowledge documents"
        sub="Database documentation, data dictionary, KPI definitions — uploaded, parsed, chunked and indexed by the RAG pipeline."
      >
        <DocumentsPanel source={source} setError={setError} />
      </Drop>
    </div>
  );
}
