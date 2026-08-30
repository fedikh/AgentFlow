import React, { useEffect, useState } from "react";
import {
  Activity, AlertTriangle, ChevronDown, ChevronRight, Coins, ExternalLink,
  Hash, RefreshCw, Timer,
} from "lucide-react";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { obsOverview, obsStatus, obsTraces } from "../../../services/ragApi";

/*
 * ObservabilityPanel — production monitoring of a DEPLOYED space (Langfuse).
 * Deliberately minimal, same view for IT and Admin:
 *
 *   KPIs      Requests · Errors · Avg latency · Tokens · Cost
 *   charts    Requests per day · Avg latency per day · Cost per day
 *   traces    Time · Question · Latency · Tokens · Cost · Chunks,
 *             each row expandable to the ANSWER (+ Langfuse deep link)
 *
 * Every user question answered by the deployed agent produces one trace
 * (chat/service.py → observability.record_query). Nothing shows until
 * LANGFUSE_* keys are configured in the backend.
 */

const RANGES = [[1, "24h"], [7, "7 days"], [30, "30 days"]];
const ms = (v) => (v == null ? "—"
  : v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${Math.round(v)}ms`);
const money = (v) => (v == null ? "—"
  : v === 0 ? "$0" : v < 0.001 ? "<$0.001" : `$${Number(v).toFixed(3)}`);
const num = (v) => (v == null ? "—" : Number(v).toLocaleString());
const when = (iso) => {
  try { return new Date(String(iso).replace(" ", "T")).toLocaleString(); }
  catch { return iso || "—"; }
};

function Tile({ icon, label, value, sub, warn }) {
  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: 13,
                  padding: "13px 15px", background: "#fff",
                  display: "flex", gap: 12, alignItems: "flex-start",
                  boxShadow: "0 1px 3px rgba(15,23,42,.04)" }}>
      {icon && (
        <span style={{ width: 34, height: 34, borderRadius: 10, flexShrink: 0,
                       display: "grid", placeItems: "center",
                       background: warn ? "#fee2e2" : "#f2f6ff",
                       color: warn ? "#dc2626" : "#2563eb" }}>
          {icon}
        </span>
      )}
      <span style={{ minWidth: 0 }}>
        <span style={{ display: "block", font: "600 10.5px system-ui",
                       color: "#64748b", textTransform: "uppercase",
                       letterSpacing: "0.04em" }}>
          {label}
        </span>
        <span style={{ display: "block", font: "700 20px system-ui",
                       color: warn ? "#b91c1c" : "#0f172a", marginTop: 2,
                       fontVariantNumeric: "tabular-nums" }}>
          {value}
        </span>
        {sub && (
          <span style={{ display: "block", fontSize: 11, color: "#94a3b8",
                         marginTop: 1 }}>
            {sub}
          </span>
        )}
      </span>
    </div>
  );
}

function ChartCard({ icon, title, children }) {
  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: 12,
                  background: "#fff", padding: "13px 15px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 7,
                    marginBottom: 9 }}>
        {icon}
        <span style={{ font: "700 12.5px system-ui", color: "#0f172a" }}>
          {title}
        </span>
      </div>
      <div style={{ height: 150 }}>{children}</div>
    </div>
  );
}

const TIP = { contentStyle: { fontSize: 12, borderRadius: 10,
                              border: "1px solid #e5e9f0" } };
const TICK = { fontSize: 10.5, fill: "#64748b" };

export default function ObservabilityPanel({ space }) {
  const [cfg, setCfg] = useState(null);           // null = loading status
  const [days, setDays] = useState(7);
  const [data, setData] = useState(null);
  const [traces, setTraces] = useState([]);
  const [openTrace, setOpenTrace] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    obsStatus(space.id).then(setCfg).catch(() => setCfg({ configured: false }));
  }, [space.id]);

  const load = (d = days) => {
    setBusy(true);
    setError("");
    Promise.all([obsOverview(space.id, d), obsTraces(space.id, d, 50)])
      .then(([ov, tr]) => {
        setData(ov);
        setTraces(tr.traces || []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setBusy(false));
  };
  useEffect(() => {
    if (cfg?.configured) load(days);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfg?.configured, days, space.id]);

  /* ── not configured yet ── */
  if (cfg && !cfg.configured) {
    return (
      <div className="rag-cfg-panel">
        <div className="rag-cfg-head">
          <div>
            <div className="rag-cfg-title">RAG Observability</div>
            <div className="rag-cfg-sub">
              Production monitoring of this agent — requests, latency, tokens,
              cost and traces — powered by Langfuse.
            </div>
          </div>
        </div>
        <div className="rag-cfg-warn" style={{ marginBottom: 12 }}>
          Langfuse is not configured yet. Add the keys to the backend
          environment and restart:
        </div>
        <pre style={{ background: "#0f172a", color: "#e2e8f0", borderRadius: 10,
                      padding: "12px 14px", fontSize: 12,
                      fontFamily: "ui-monospace, monospace" }}>
{`LANGFUSE_PUBLIC_KEY=pk-lf-…
LANGFUSE_SECRET_KEY=sk-lf-…
LANGFUSE_HOST=https://cloud.langfuse.com   # or your self-hosted URL`}
        </pre>
        <div className="rag-cfg-hint">
          Create a free project at <strong>cloud.langfuse.com</strong> (or
          self-host Langfuse), copy the API keys, and every question answered
          by this deployed agent will be traced automatically.
        </div>
      </div>
    );
  }

  const lat = data?.latency || {};
  const tok = data?.tokens || {};
  const cost = data?.cost || {};

  return (
    <div className="rag-cfg-panel">
      <div className="rag-cfg-head">
        <div>
          <div className="rag-cfg-title">Production monitoring</div>
          <div className="rag-cfg-sub">
            Real traffic of the deployed agent — every question is traced.
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <div style={{ display: "inline-flex", gap: 2, padding: 3,
                        background: "#eef2f7", borderRadius: 9 }}>
            {RANGES.map(([d, label]) => (
              <button key={d} onClick={() => setDays(d)}
                style={{ border: "none", borderRadius: 7, padding: "5px 12px",
                         font: "600 11.5px system-ui", cursor: "pointer",
                         background: days === d ? "#fff" : "transparent",
                         color: days === d ? "#0f172a" : "#64748b",
                         boxShadow: days === d
                           ? "0 1px 2px rgba(15,23,42,.1)" : "none" }}>
                {label}
              </button>
            ))}
          </div>
          <button className="rag-btn rag-btn-sm" onClick={() => load()}
                  disabled={busy}>
            <RefreshCw size={13} className={busy ? "spin" : undefined} />
          </button>
        </div>
      </div>

      {error && <div className="rag-cfg-warn" style={{ marginBottom: 10 }}>{error}</div>}
      {!data && !error && <div className="rag-cfg-hint">Loading…</div>}

      {data && (
        <div style={{ display: "grid", gap: 12 }}>
          {/* ═══ Requests · Errors · Avg latency · Tokens · Cost ═══ */}
          <div style={{ display: "grid", gap: 10,
                        gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))" }}>
            <Tile icon={<Activity size={16} />} label="Requests"
                  value={num(data.requests)}
                  sub={`last ${data.days} day${data.days > 1 ? "s" : ""}`} />
            <Tile icon={<AlertTriangle size={16} />} label="Errors"
                  value={num(data.errors)} warn={data.errors > 0}
                  sub={data.error_rate != null
                    ? `${(data.error_rate * 100).toFixed(1)}% of requests` : null} />
            <Tile icon={<Timer size={16} />} label="Avg latency"
                  value={ms(lat.avg_ms)}
                  sub={lat.avg_retrieval_ms != null
                    ? `retrieval ${ms(lat.avg_retrieval_ms)}` : null} />
            <Tile icon={<Hash size={16} />} label="Tokens"
                  value={num(tok.total)}
                  sub={tok.avg_per_request != null
                    ? `~${Math.round(tok.avg_per_request)}/request` : null} />
            <Tile icon={<Coins size={16} />} label="Cost"
                  value={money(cost.total)}
                  sub={cost.avg_per_request != null
                    ? `${money(cost.avg_per_request)}/request` : null} />
          </div>

          {data.requests === 0 ? (
            <div className="rag-cfg-hint">
              No traffic in this window yet — traces appear here as soon as
              end users ask the deployed agent questions.
            </div>
          ) : (
            <div>
              <div style={{ font: "700 11px system-ui", color: "#64748b",
                            textTransform: "uppercase",
                            letterSpacing: "0.05em", margin: "4px 0 8px" }}>
                Activity — last {data.days} day{data.days > 1 ? "s" : ""}
              </div>
            <div style={{ display: "grid", gap: 10,
                          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
              <ChartCard icon={<Activity size={14} color="#2563eb" />}
                         title="Requests per day">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.series}
                            margin={{ top: 4, right: 6, left: -22, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="#eef2f6" />
                    <XAxis dataKey="day" tick={TICK} tickLine={false}
                           tickFormatter={(v) => v.slice(5)} />
                    <YAxis tick={TICK} tickLine={false} axisLine={false}
                           allowDecimals={false} />
                    <Tooltip {...TIP} />
                    <Bar dataKey="requests" name="requests" fill="#2563eb"
                         radius={[3, 3, 0, 0]} maxBarSize={22} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
              <ChartCard icon={<Timer size={14} color="#0d9488" />}
                         title="Avg latency per day (ms)">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.series}
                             margin={{ top: 4, right: 6, left: -14, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="#eef2f6" />
                    <XAxis dataKey="day" tick={TICK} tickLine={false}
                           tickFormatter={(v) => v.slice(5)} />
                    <YAxis tick={TICK} tickLine={false} axisLine={false} />
                    <Tooltip {...TIP} />
                    <Line dataKey="avg_ms" name="avg ms" stroke="#0d9488"
                          strokeWidth={2} dot={{ r: 2.5 }} />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>
              <ChartCard icon={<Coins size={14} color="#d97706" />}
                         title="Cost per day ($)">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.series}
                            margin={{ top: 4, right: 6, left: -14, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="#eef2f6" />
                    <XAxis dataKey="day" tick={TICK} tickLine={false}
                           tickFormatter={(v) => v.slice(5)} />
                    <YAxis tick={TICK} tickLine={false} axisLine={false} />
                    <Tooltip {...TIP} />
                    <Bar dataKey="cost" name="cost $" fill="#d97706"
                         radius={[3, 3, 0, 0]} maxBarSize={22} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
            </div>
            </div>
          )}

          {/* ═══ Recent traces ═══ */}
          <div>
            <div style={{ font: "700 11px system-ui", color: "#64748b",
                          textTransform: "uppercase", letterSpacing: "0.05em",
                          margin: "2px 0 6px" }}>
              Recent traces
            </div>
            {traces.length === 0 ? (
              <div className="rag-cfg-hint">No traces in this window.</div>
            ) : (
              <table className="ev-table">
                <thead>
                  <tr><th style={{ width: 20 }} /><th>Time</th><th>Question</th>
                      <th>Latency</th><th>Tokens</th><th>Cost</th><th>Chunks</th></tr>
                </thead>
                <tbody>
                  {traces.map((t) => (
                    <React.Fragment key={t.id}>
                      <tr onClick={() =>
                            setOpenTrace(openTrace === t.id ? null : t.id)}
                          style={{ cursor: "pointer" }}>
                        <td style={{ color: "#94a3b8" }}>
                          {openTrace === t.id ? <ChevronDown size={13} />
                                              : <ChevronRight size={13} />}
                        </td>
                        <td style={{ whiteSpace: "nowrap",
                                     fontVariantNumeric: "tabular-nums" }}>
                          {when(t.time)}
                        </td>
                        <td style={{ maxWidth: 340, overflow: "hidden",
                                     textOverflow: "ellipsis",
                                     whiteSpace: "nowrap" }} title={t.question}>
                          {t.error && (
                            <AlertTriangle size={12} color="#dc2626"
                                           style={{ marginRight: 5,
                                                    verticalAlign: "-2px" }} />
                          )}
                          {t.question || "—"}
                        </td>
                        <td>{ms(t.latency_ms)}</td>
                        <td>{t.tokens != null ? Math.round(t.tokens) : "—"}</td>
                        <td>{money(t.cost)}</td>
                        <td>{t.chunks ?? "—"}</td>
                      </tr>
                      {openTrace === t.id && (
                        <tr>
                          <td colSpan={7} style={{ background: "#fafbfc" }}>
                            {t.error && (
                              <div style={{ fontSize: 12, color: "#b91c1c",
                                            marginBottom: 6 }}>
                                Error: {t.error}
                              </div>
                            )}
                            <div style={{ fontSize: 12.5, color: "#334155",
                                          lineHeight: 1.6, maxHeight: 120,
                                          overflow: "auto" }}>
                              <b>Answer:</b> {t.answer || "—"}
                            </div>
                            <a href={t.langfuse_url} target="_blank"
                               rel="noreferrer"
                               style={{ display: "inline-flex",
                                        alignItems: "center", gap: 4,
                                        color: "#2563eb", marginTop: 7,
                                        font: "600 11.5px system-ui",
                                        textDecoration: "none" }}>
                              Open the full trace in Langfuse
                              <ExternalLink size={11} />
                            </a>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
