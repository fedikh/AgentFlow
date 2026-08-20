import React, { useEffect, useRef, useState } from "react";
import {
  ChevronDown, ChevronRight, RefreshCw, Sparkles,
} from "lucide-react";
import {
  dataJobStatus, getSourceSchema, introspectSource, trainSource,
  updateSourceTable,
} from "../../../services/dataAgentApi";
import { card, ink, mono } from "../../dashboard/tokens";
import { btn, inputStyle } from "./ui";

/*
 * SchemaSection — introspect the connected database, curate the table tree
 * (enable toggles + trainable descriptions, PK/FK display), then TRAIN the
 * Vanna index (DDL + FK graph + docs → per-source pgvector collections).
 * Progress via the job-polling pattern. onChanged() tells the parent the
 * source row (status/table_count) moved.
 */
export default function SchemaSection({ source, onChanged, setError }) {
  const [schema, setSchema] = useState([]);
  const [open, setOpen] = useState({});
  const [job, setJob] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => {
    getSourceSchema(source.id).then(setSchema).catch(() => setSchema([]));
    return () => clearInterval(pollRef.current);
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
            getSourceSchema(source.id).then(setSchema).catch(() => {});
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

  const mode = source.mode;
  return (
    <div style={{ ...card, display: "grid", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 13.5, color: ink.primary }}>
            Schema & training
          </div>
          <div style={{ fontSize: 11.5, color: ink.muted, marginTop: 2 }}>
            {source.table_count
              ? `${source.table_count} tables · ${mode} mode ${mode === "rag"
                  ? "— schema is embedded in the vector store, the agent retrieves the relevant subset"
                  : "— the whole schema fits in the prompt"}`
              : "Introspect to discover tables, curate them, then train the agent."}
          </div>
        </div>
        <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button style={btn(false)} onClick={() => runJob("introspect", introspectSource)}
                  disabled={job?.status === "running"}>
            <RefreshCw size={14} /> Introspect
          </button>
          <button style={btn(true)} onClick={() => runJob("train", trainSource)}
                  disabled={job?.status === "running" || !schema.length}>
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
          {job.status === "running" && (
            <div style={{ height: 7, background: "#EEF2F5", borderRadius: 4 }}>
              <div style={{
                width: job.total ? `${Math.round((job.done / job.total) * 100)}%` : "30%",
                height: "100%", background: ink.blue, borderRadius: 4, transition: "width .4s",
              }} />
            </div>
          )}
        </div>
      )}

      <div style={{ display: "grid", gap: 8 }}>
        {schema.map((t) => (
          <div key={t.id} style={{
            border: `1px solid ${ink.line}`, borderRadius: 10,
            padding: "10px 12px", opacity: t.is_enabled ? 1 : 0.55,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <button onClick={() => setOpen((o) => ({ ...o, [t.id]: !o[t.id] }))}
                      style={{ border: "none", background: "none", cursor: "pointer", color: ink.muted, display: "inline-flex" }}>
                {open[t.id] ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
              </button>
              <span style={{ fontWeight: 700, fontSize: 13, color: ink.primary }}>
                {t.schema}.{t.table}
              </span>
              <span style={{ fontSize: 11, color: ink.faint }}>
                {t.columns.length} cols{t.row_estimate != null ? ` · ~${t.row_estimate} rows` : ""}
              </span>
              <label style={{ marginLeft: "auto", fontSize: 11.5, color: ink.muted, display: "inline-flex", gap: 6, alignItems: "center", cursor: "pointer" }}>
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
            {open[t.id] && (
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
            No schema yet — run <strong>Introspect</strong> after the connection test passes.
          </div>
        )}
      </div>
    </div>
  );
}
