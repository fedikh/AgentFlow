import React, { useEffect, useMemo, useState } from "react";
import { Activity, Bot, Building2, FileText } from "lucide-react";
import { listSpaces } from "../../services/ragApi";
import ObservabilityPanel from "../../components/it/rag/ObservabilityPanel";
import "../../styles/it/spacesgrid.css";

/*
 * RAG Observability — standalone page (IT and Admin routes share it):
 * pick a DEPLOYED agent, see its production behavior (the Langfuse-backed
 * dashboard). Same two-select mechanism, dressed as labeled field cards.
 *
 * Scoping comes from the backend: listSpaces returns the caller's visible
 * spaces (IT → their departments' agents, ADMIN → the whole organization),
 * and only status ACTIVE (deployed) agents are monitored.
 */

const ink = {
  primary: "#0f172a", muted: "#64748b", faint: "#94a3b8",
  line: "#e2e8f0", blue: "#2563eb", tint: "#f2f6ff",
};

/* a labeled select dressed as a field card: icon chip · eyebrow · value */
function Field({ icon, label, children, minWidth = 230 }) {
  return (
    <label style={{
      display: "flex", alignItems: "center", gap: 11, minWidth,
      border: `1px solid ${ink.line}`, borderRadius: 13,
      padding: "9px 13px", background: "#fff", cursor: "pointer",
      boxShadow: "0 1px 3px rgba(15,23,42,.04)",
    }}>
      <span style={{
        width: 34, height: 34, borderRadius: 10, flexShrink: 0,
        display: "grid", placeItems: "center",
        background: ink.tint, color: ink.blue,
      }}>
        {icon}
      </span>
      <span style={{ display: "grid", flex: 1, minWidth: 0, gap: 1 }}>
        <span style={{ font: "700 9.5px system-ui", letterSpacing: "0.07em",
                       textTransform: "uppercase", color: ink.faint }}>
          {label}
        </span>
        {children}
      </span>
    </label>
  );
}

const selectStyle = {
  border: "none", outline: "none", background: "transparent",
  font: "700 13.5px system-ui", color: ink.primary,
  padding: 0, cursor: "pointer", width: "100%",
};

export default function RAGObservabilityPage({
  title = "RAG Observability",
  subtitle = "Production monitoring of your deployed RAG agents",
}) {
  const [spaces, setSpaces] = useState(null);      // null = loading
  const [dept, setDept] = useState("");            // "" = all departments
  const [spaceId, setSpaceId] = useState("");

  useEffect(() => {
    listSpaces()
      .then((all) => setSpaces((all || []).filter((s) => s.status === "ACTIVE")))
      .catch(() => setSpaces([]));
  }, []);

  const departments = useMemo(
    () => [...new Set((spaces || []).map((s) => s.department_name || "General"))],
    [spaces],
  );
  const deptSpaces = (spaces || []).filter(
    (s) => !dept || (s.department_name || "General") === dept,
  );
  const selected = deptSpaces.find((s) => s.id === spaceId) || deptSpaces[0] || null;

  return (
    <div>
      <div className="sg-head">
        <div>
          <h1 className="sg-title">{title}</h1>
          <p className="sg-sub">{subtitle}</p>
        </div>
        {spaces !== null && spaces.length > 0 && (
          <span style={{
            display: "inline-flex", alignItems: "center", gap: 7,
            border: `1px solid ${ink.line}`, borderRadius: 999,
            padding: "7px 15px", background: "#fff",
            font: "600 12px system-ui", color: "#334155",
            boxShadow: "0 1px 3px rgba(15,23,42,.04)",
          }}>
            <Activity size={13} color={ink.blue} />
            {spaces.length} deployed agent{spaces.length === 1 ? "" : "s"}
          </span>
        )}
      </div>

      {spaces === null ? (
        <div className="rag-cfg-hint">Loading…</div>
      ) : spaces.length === 0 ? (
        <div className="sg-empty">
          <div className="sg-empty-ic"><Activity size={24} /></div>
          <div className="sg-empty-title">No deployed agents to monitor</div>
          <div className="sg-empty-sub">
            Observability watches agents in production — deploy a RAG space
            first, then its traffic shows up here.
          </div>
        </div>
      ) : (
        <>
          {/* ── which deployed agent to inspect ── */}
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap",
                        alignItems: "center", margin: "4px 0 16px" }}>
            {departments.length > 1 && (
              <Field icon={<Building2 size={16} />} label="Department"
                     minWidth={220}>
                <select style={selectStyle} value={dept}
                        onChange={(e) => { setDept(e.target.value); setSpaceId(""); }}>
                  <option value="">All departments</option>
                  {departments.map((d) => <option key={d}>{d}</option>)}
                </select>
              </Field>
            )}
            <Field icon={<Bot size={16} />} label="Deployed agent"
                   minWidth={300}>
              <select style={selectStyle} value={selected?.id || ""}
                      onChange={(e) => setSpaceId(e.target.value)}>
                {deptSpaces.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} — {s.department_name || "General"}
                  </option>
                ))}
              </select>
            </Field>
            {selected && (
              <span style={{
                display: "inline-flex", alignItems: "center", gap: 7,
                fontSize: 12, color: ink.muted, marginLeft: 2,
              }}>
                <span style={{ width: 7, height: 7, borderRadius: "50%",
                               background: "#22c55e", flexShrink: 0 }} />
                Live
                <span style={{ color: ink.faint }}>·</span>
                <FileText size={12} color={ink.faint} />
                {selected.num_documents || 0} docs
                <span style={{ color: ink.faint }}>
                  · {deptSpaces.length} agent{deptSpaces.length === 1 ? "" : "s"} in scope
                </span>
              </span>
            )}
          </div>

          {selected && (
            <ObservabilityPanel key={selected.id} space={selected} />
          )}
        </>
      )}
    </div>
  );
}
