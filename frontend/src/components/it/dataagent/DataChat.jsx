import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Bot, Check, ChevronDown, ChevronRight, Copy, Download, Loader2,
  MessageSquare, Play, Plus, Send, Table2, Trash2,
  BarChart3, LineChart as LineChartIcon, PieChart as PieChartIcon,
} from "lucide-react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  askData, deleteDaSession, executeSql, getDaSession, listDaSessions,
} from "../../../services/dataAgentApi";
import AnswerBody from "../../rag/AnswerBody";
import { ink, PALETTE, TIP } from "../../dashboard/tokens";
import "../../../styles/it/datachat.css";

/*
 * DataChat — the NL→SQL conversation, shared by the workspace test console
 * and the deployed-agents page (which adds the conversations rail with
 * `withHistory`). Every answer shows: the NL answer, the SQL (collapsible,
 * EDITABLE, re-runnable through the full validator), and the results as a
 * table OR an auto-detected chart (bar / line / pie), with CSV export.
 */

/* ── result-shape analysis: what can we draw? ── */
const toNum = (v) => {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(String(v).replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
};
const looksNumeric = (rows, col) => {
  let seen = 0, ok = 0;
  for (const r of rows) {
    if (r[col] === null || r[col] === undefined || r[col] === "") continue;
    seen += 1;
    if (toNum(r[col]) !== null) ok += 1;
  }
  return seen > 0 && ok / seen >= 0.8;
};
const looksDateLike = (v) =>
  /^\d{4}-\d{2}(-\d{2})?/.test(String(v ?? "")) || /^\d{4}$/.test(String(v ?? ""));

function analyzeResults(columns, rows) {
  const cols = columns || [];
  const data = rows || [];
  const isStat = data.length === 1 && cols.length === 1;
  const numericIdx = cols.map((_, i) => i).filter((i) => looksNumeric(data, i));
  // First column is the label (SQL convention: group key first); the numeric
  // columns after it are the series. A first numeric column (year, month №)
  // still labels fine.
  const seriesIdx = numericIdx.filter((i) => i !== 0);
  const chartable =
    !isStat && cols.length >= 2 && data.length >= 2 && data.length <= 100 &&
    seriesIdx.length >= 1 && seriesIdx.length <= PALETTE.length;
  const dateLike = chartable && data.every((r) => looksDateLike(r[0]));
  const pieOk =
    chartable && seriesIdx.length === 1 && data.length <= PALETTE.length &&
    data.every((r) => (toNum(r[seriesIdx[0]]) ?? -1) >= 0);
  const chartData = chartable
    ? data.map((r) => {
        const o = { __label: String(r[0] ?? "—") };
        seriesIdx.forEach((i) => { o[cols[i]] = toNum(r[i]); });
        return o;
      })
    : [];
  return {
    isStat, chartable, pieOk, numericIdx,
    series: seriesIdx.map((i) => cols[i]),
    chartData,
    defaultView: chartable ? (dateLike ? "line" : "bar") : "table",
  };
}

const fmtAxis = (v) => {
  if (v == null) return "";
  const a = Math.abs(v);
  if (a >= 1e6) return `${(v / 1e6).toFixed(1).replace(/\.0$/, "")}M`;
  if (a >= 1e3) return `${(v / 1e3).toFixed(1).replace(/\.0$/, "")}k`;
  return String(v);
};
const fmtVal = (v) => (typeof v === "number" ? v.toLocaleString() : String(v ?? ""));
const clip = (s, n = 14) => (String(s).length > n ? `${String(s).slice(0, n - 1)}…` : String(s));

const AXIS_TICK = { fontSize: 11, fill: ink.muted };
const GRID = { stroke: "#EEF2F6", vertical: false };

function ResultChart({ view, shape }) {
  const { chartData, series } = shape;
  const many = series.length > 1;
  const common = (
    <>
      <CartesianGrid {...GRID} />
      <XAxis dataKey="__label" tick={AXIS_TICK} tickLine={false}
             axisLine={{ stroke: ink.line }} interval="preserveStartEnd"
             tickFormatter={(v) => clip(v)} />
      <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false}
             tickFormatter={fmtAxis} width={46} />
      <Tooltip {...TIP} formatter={(v, name) => [fmtVal(v), name]} />
      {many && <Legend iconSize={10} wrapperStyle={{ fontSize: 11 }} />}
    </>
  );
  if (view === "pie") {
    return (
      <div className="dc-chartbox" style={{ height: 250 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={chartData} dataKey={series[0]} nameKey="__label"
                 innerRadius="52%" outerRadius="85%" paddingAngle={2} stroke="#fff">
              {chartData.map((_, i) => (
                <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
              ))}
            </Pie>
            <Tooltip {...TIP} formatter={(v, name) => [fmtVal(v), name]} />
            <Legend iconSize={10} wrapperStyle={{ fontSize: 11 }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }
  if (view === "line") {
    return (
      <div className="dc-chartbox" style={{ height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 14, left: 0, bottom: 4 }}>
            {common}
            {series.map((s, i) => (
              <Line key={s} type="monotone" dataKey={s} stroke={PALETTE[i]}
                    strokeWidth={2} dot={{ r: 3, stroke: "#fff", strokeWidth: 2, fill: PALETTE[i] }}
                    activeDot={{ r: 5 }} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }
  return (
    <div className="dc-chartbox" style={{ height: 280 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 8, right: 14, left: 0, bottom: 4 }} barGap={2}>
          {common}
          {series.map((s, i) => (
            <Bar key={s} dataKey={s} fill={PALETTE[i]} maxBarSize={24}
                 radius={[4, 4, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ── results card: [Table | Bar | Line | Pie] + CSV export ── */
function ResultsCard({ columns, rows, truncated }) {
  const shape = useMemo(() => analyzeResults(columns, rows), [columns, rows]);
  const [pickedView, setView] = useState(null);
  const [showAll, setShowAll] = useState(false);
  if (!columns?.length) return null;
  // the user's pick survives re-runs only while it's still drawable
  const validViews = ["table",
                      ...(shape.chartable ? ["bar", "line"] : []),
                      ...(shape.pieOk ? ["pie"] : [])];
  const view = pickedView && validViews.includes(pickedView)
    ? pickedView : shape.defaultView;

  /* a single value is a stat tile, not a table */
  if (shape.isStat) {
    const v = rows[0][0];
    const n = toNum(v);
    return (
      <div className="dc-stat">
        <div className="dc-stat-label">{columns[0]}</div>
        <div className="dc-stat-value">{n !== null ? n.toLocaleString() : String(v ?? "—")}</div>
      </div>
    );
  }

  const exportCsv = () => {
    const esc = (x) => `"${String(x ?? "").replace(/"/g, '""')}"`;
    const csv = [columns.map(esc).join(","),
                 ...rows.map((r) => r.map(esc).join(","))].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url; a.download = "results.csv"; a.click();
    URL.revokeObjectURL(url);
  };

  const tabs = [
    { id: "table", label: "Table", icon: <Table2 size={12} />, show: true },
    { id: "bar", label: "Bar", icon: <BarChart3 size={12} />, show: shape.chartable },
    { id: "line", label: "Line", icon: <LineChartIcon size={12} />, show: shape.chartable },
    { id: "pie", label: "Pie", icon: <PieChartIcon size={12} />, show: shape.pieOk },
  ].filter((t) => t.show);
  const shown = showAll ? rows.slice(0, 500) : rows.slice(0, 50);

  return (
    <div className="dc-result">
      <div className="dc-result-bar">
        {tabs.length > 1 && (
          <div className="dc-tabs">
            {tabs.map((t) => (
              <button key={t.id} className={`dc-tab ${view === t.id ? "on" : ""}`}
                      onClick={() => setView(t.id)}>
                {t.icon} {t.label}
              </button>
            ))}
          </div>
        )}
        <span className="dc-result-count">
          {rows.length.toLocaleString()} row{rows.length === 1 ? "" : "s"}
        </span>
        <button className="dc-result-csv" onClick={exportCsv}>
          <Download size={11} /> CSV
        </button>
      </div>

      {view === "table" ? (
        <>
          <div className="dc-tablewrap">
            <table className="dc-table">
              <thead>
                <tr>{columns.map((c, i) => (
                  <th key={c} className={shape.numericIdx.includes(i) ? "num" : ""}>{c}</th>
                ))}</tr>
              </thead>
              <tbody>
                {shown.map((r, i) => (
                  <tr key={i}>{r.map((v, j) => (
                    <td key={j} className={shape.numericIdx.includes(j) ? "num" : ""}
                        title={String(v ?? "")}>
                      {shape.numericIdx.includes(j) && toNum(v) !== null
                        ? toNum(v).toLocaleString() : String(v ?? "")}
                    </td>
                  ))}</tr>
                ))}
              </tbody>
            </table>
          </div>
          {rows.length > shown.length && (
            <button className="dc-more" onClick={() => setShowAll(true)}>
              Show all {Math.min(rows.length, 500).toLocaleString()} rows
            </button>
          )}
        </>
      ) : (
        <ResultChart view={view} shape={shape} />
      )}
      {truncated && (
        <div className="dc-trunc" style={{ margin: "0 10px 10px" }}>
          Results truncated at the row limit — refine the question to narrow them.
        </div>
      )}
    </div>
  );
}

/* ── SQL block: view / copy / edit / re-run ── */
function SqlBlock({ msg, sourceId, setError }) {
  const [open, setOpen] = useState(false);
  const [sql, setSql] = useState(msg.sql || "");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);
  if (!msg.sql) return null;

  const run = async () => {
    setRunning(true);
    try { setResult(await executeSql(sourceId, sql)); }
    catch (e) { setError(e.message); }
    finally { setRunning(false); }
  };
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard unavailable — the textarea is selectable */ }
  };

  // Results from the original ask are rendered by the message itself — the
  // block only shows results of a re-run, so nothing appears twice.
  const fromHistoryNoRows = msg.fromHistory && !result && !msg.columns?.length;
  return (
    <div className="dc-sql">
      <div className="dc-sql-head">
        <button className="dc-sql-toggle" onClick={() => setOpen((v) => !v)}>
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />} SQL
        </button>
        <button className="dc-sql-copy" onClick={copy}>
          {copied ? <Check size={11} /> : <Copy size={11} />} {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {open && (
        <div className="dc-sql-editor">
          <textarea value={sql} onChange={(e) => setSql(e.target.value)}
                    rows={Math.min(10, sql.split("\n").length + 1)}
                    spellCheck={false} />
          <button className="dc-sql-run" onClick={run} disabled={running}>
            {running ? <Loader2 size={12} className="dc-spin" /> : <Play size={12} />}
            Run edited SQL
          </button>
        </div>
      )}
      {result?.columns?.length > 0 && (
        <ResultsCard columns={result.columns} rows={result.rows || []}
                     truncated={result.truncated} />
      )}
      {fromHistoryNoRows && (
        <div className="dc-note">
          Results aren&apos;t stored with the conversation — open the SQL and run it
          to reload them{msg.rowCount != null ? ` (${msg.rowCount} rows last time)` : ""}.
        </div>
      )}
    </div>
  );
}

const timeAgo = (iso) => {
  if (!iso) return "";
  const d = new Date(String(iso).replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return "";
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return "now";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
};

const meInitials = (() => {
  try {
    const u = JSON.parse(localStorage.getItem("user") || "{}");
    const n = (u.name || u.email || "U").trim();
    const p = n.split(/\s+/);
    return (p.length >= 2 ? p[0][0] + p[1][0] : n.slice(0, 2)).toUpperCase();
  } catch { return "U"; }
})();

export default function DataChat({
  source, setError, height = 460,
  placeholder = "Ask a question about this data…",
  withHistory = false,
}) {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [loadingChat, setLoadingChat] = useState(false);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    setSessionId(null); setMessages([]); setSessions([]);
    if (!withHistory) return;
    listDaSessions()
      .then((all) => setSessions(all.filter((s) => s.data_source_id === source.id)))
      .catch(() => { /* history optional — a fresh chat still works */ });
  }, [source.id, withHistory]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, asking]);

  const newChat = () => { setSessionId(null); setMessages([]); setQuestion(""); };

  const openSession = async (s) => {
    setSessionId(s.id);
    setMessages([]);
    setLoadingChat(true);
    try {
      const res = await getDaSession(s.id);
      setMessages((res.messages || []).map((m) => ({
        role: m.role, content: m.content, sql: m.sql,
        attempts: m.attempts, truncated: m.truncated,
        timings: m.timings_ms, rowCount: m.row_count, fromHistory: true,
      })));
    } catch { setMessages([]); }
    finally { setLoadingChat(false); }
  };

  const removeSession = async (e, s) => {
    e.stopPropagation();
    if (!window.confirm(`Delete the conversation “${s.title || "New chat"}”?`)) return;
    setSessions((l) => l.filter((x) => x.id !== s.id));
    if (sessionId === s.id) newChat();
    try { await deleteDaSession(s.id); } catch { /* optimistic */ }
  };

  const ask = async () => {
    const q = question.trim();
    if (!q || asking) return;
    setQuestion("");
    if (inputRef.current) inputRef.current.style.height = "auto";
    setMessages((m) => [...m, { role: "user", content: q }]);
    setAsking(true);
    try {
      const res = await askData(source.id, q, sessionId);
      setSessionId(res.session.id);
      if (withHistory) {
        setSessions((l) => [res.session, ...l.filter((x) => x.id !== res.session.id)]);
      }
      setMessages((m) => [...m, {
        role: "assistant", content: res.answer, sql: res.sql,
        columns: res.columns, rows: res.rows, truncated: res.truncated,
        attempts: res.attempts, timings: res.timings_ms,
      }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", content: e.message, error: true }]);
    } finally {
      setAsking(false);
    }
  };

  const onInput = (e) => {
    setQuestion(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
  };

  return (
    <div className="dc-wrap" style={{ height }}>
      {withHistory && (
        <aside className="dc-hist">
          <button className="dc-hist-new" onClick={newChat} disabled={asking}>
            <Plus size={14} /> New chat
          </button>
          <div className="dc-hist-list">
            {sessions.length === 0 && (
              <div className="dc-hist-empty">
                No conversations yet — your chats are saved automatically.
              </div>
            )}
            {sessions.map((s) => (
              <div key={s.id}
                   className={`dc-hist-item ${s.id === sessionId ? "active" : ""}`}
                   role="button" tabIndex={0}
                   onClick={() => openSession(s)}
                   onKeyDown={(e) => e.key === "Enter" && openSession(s)}>
                <MessageSquare size={13} className="dc-hist-ic" />
                <span className="dc-hist-title">{s.title || "New chat"}</span>
                <span className="dc-hist-time">{timeAgo(s.last_message_at)}</span>
                <button className="dc-hist-del" title="Delete"
                        onClick={(e) => removeSession(e, s)}>
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </aside>
      )}

      <div className="dc-chat">
        <div className="dc-stream">
          {loadingChat && <div className="dc-hist-empty">Loading conversation…</div>}
          {messages.length === 0 && !loadingChat && (
            <div className="dc-empty">
              <div className="dc-empty-ic"><Bot size={26} /></div>
              <div className="dc-empty-t">Ask {source.name || "your data"}</div>
              <div className="dc-empty-s">
                Plain-language questions become SQL — every answer shows the query
                it ran, the results, and a chart when the data suits one.
              </div>
            </div>
          )}

          {messages.map((m, i) => {
            const me = m.role === "user";
            return (
              <div key={i} className={`dc-row ${me ? "me" : ""}`}>
                <span className={`dc-av ${me ? "me" : "ai"}`}>
                  {me ? meInitials : <Bot size={15} />}
                </span>
                <div className={`dc-bubble ${me ? "me" : "ai"} ${m.error ? "error" : ""}`}>
                  {me || m.error ? m.content : (
                    <>
                      <AnswerBody text={m.content} />
                      {m.columns?.length > 0 ? (
                        <ResultsCard columns={m.columns} rows={m.rows || []}
                                     truncated={m.truncated} />
                      ) : null}
                      <SqlBlock msg={m} sourceId={source.id} setError={setError} />
                      {(m.attempts || m.timings) && (
                        <div className="dc-meta">
                          {m.attempts != null && (
                            <span className="dc-chip">
                              {m.attempts} attempt{m.attempts > 1 ? "s" : ""}
                            </span>
                          )}
                          {m.timings?.total != null && (
                            <span className="dc-chip">
                              {m.timings.total >= 1000
                                ? `${(m.timings.total / 1000).toFixed(1)}s`
                                : `${Math.round(m.timings.total)}ms`}
                            </span>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          })}

          {asking && (
            <div className="dc-row">
              <span className="dc-av ai"><Bot size={15} /></span>
              <div className="dc-typing">
                <span className="dc-typing-dots"><i /><i /><i /></span>
                writing &amp; running SQL…
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        <div className="dc-composer">
          <textarea ref={inputRef} className="dc-input" rows={1}
                    value={question} onChange={onInput}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); }
                    }}
                    placeholder={placeholder} disabled={asking} />
          <button className="dc-send" onClick={() => ask()}
                  disabled={asking || !question.trim()} aria-label="Send">
            <Send size={16} />
          </button>
        </div>
        <div className="dc-hint">Enter to send · Shift+Enter for a new line</div>
      </div>
    </div>
  );
}
