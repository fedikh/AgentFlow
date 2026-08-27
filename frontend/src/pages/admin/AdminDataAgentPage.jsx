import React, { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Bot,
  Building2,
  Calendar,
  Database,
  KeyRound,
  Search,
  ShieldCheck,
  Table2,
  User,
} from "lucide-react";
import { listDataSources } from "../../services/dataAgentApi";
import { listDepartments, listDepartmentUsers } from "../../services/ragApi";
import { listUsers } from "../../services/usersApi";
import StatusBadge from "../../components/it/dataagent/StatusBadge";
import { dialectLabel } from "../../components/it/dataagent/ui";
import { Kpi } from "../../components/dashboard/DashKit";
import { card, ink } from "../../components/dashboard/tokens";
import "../../styles/it/spacesgrid.css";

/**
 * Admin Data Agents — read-only governance, the mirror of AdminRAGPage:
 *   1. card GRID (same design language) grouped by department
 *   2. full-page DETAIL on click: identity, access review, connection &
 *      guardrails, pipeline configuration, knowledge indexes
 * Building and lifecycle stay with the owner in the IT workspace.
 */

const fmtDate = (s) => {
  const d = new Date(String(s || "").replace(" ", "T"));
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString();
};

function Row({ k, v }) {
  return (
    <div style={{ display: "flex", gap: 12, padding: "8px 0", borderBottom: "1px dashed #EDF1F5", fontSize: 12.5 }}>
      <span style={{ color: ink.muted, width: 170, flexShrink: 0 }}>{k}</span>
      <span style={{ color: ink.primary, fontWeight: 600, minWidth: 0 }}>{v}</span>
    </div>
  );
}

function SubTitle({ children }) {
  return (
    <div style={{ fontSize: 10.5, fontWeight: 800, color: ink.faint, textTransform: "uppercase", letterSpacing: ".06em", margin: "14px 0 2px" }}>
      {children}
    </div>
  );
}

function Card({ icon, title, right, children, style }) {
  return (
    <div style={{ ...card, minWidth: 0, ...style }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{
          width: 30, height: 30, borderRadius: 9, background: "#EFF6FF", color: ink.blue,
          display: "grid", placeItems: "center", flexShrink: 0,
        }}>
          {icon}
        </span>
        <span style={{ fontWeight: 700, fontSize: 13.5, color: ink.primary }}>{title}</span>
        {right && <span style={{ marginLeft: "auto", fontSize: 11, color: ink.muted }}>{right}</span>}
      </div>
      <div style={{ marginTop: 6 }}>{children}</div>
    </div>
  );
}

const AdminDataAgentPage = () => {
  const [agents, setAgents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [depts, setDepts] = useState({});
  const [deptUsers, setDeptUsers] = useState(null);
  const [users, setUsers] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    (async () => {
      try {
        setAgents(await listDataSources());
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
      try {
        const all = await listUsers();
        setUsers(Object.fromEntries(
          (all || []).map((u) => [u.id, { name: u.name || u.email, email: u.email }]),
        ));
      } catch { /* names fall back to ids */ }
      try {
        const ds = await listDepartments();
        setDepts(Object.fromEntries((ds || []).map((d) => [d.id, d.name])));
      } catch { /* department names fall back to "No department" */ }
    })();
  }, []);

  const deptName = (id) => (id ? depts[id] || "…" : "No department");

  const openAgent = (a) => {
    setSelected(a);
    setDeptUsers(null);
    if (a.department_id)
      listDepartmentUsers(a.department_id).then(setDeptUsers).catch(() => {});
  };

  const grouped = useMemo(() => {
    const filtered = agents.filter((a) =>
      (a.name || "").toLowerCase().includes(q.trim().toLowerCase()));
    const g = {};
    filtered.forEach((a) => {
      (g[deptName(a.department_id)] ||= []).push(a);
    });
    return g;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agents, q, depts]);

  const personName = (uid) =>
    users[uid]?.name || (deptUsers || []).find((u) => u.id === uid)?.name || `${uid.slice(0, 8)}…`;
  const personEmail = (uid) =>
    users[uid]?.email || (deptUsers || []).find((u) => u.id === uid)?.email || "";

  if (loading) return <div style={{ ...card, color: ink.muted }}>Loading data agents…</div>;

  /* ═══════════ VIEW 1 — card grid, grouped by department ═══════════ */
  if (!selected) {
    const totalTables = agents.reduce((a, s) => a + (s.table_count || 0), 0);
    const deployed = agents.filter((a) => a.status === "deployed").length;
    return (
      <div style={{ display: "grid", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 800, color: ink.primary, letterSpacing: "-0.3px", margin: 0 }}>
              Data Agents
            </h1>
            <p style={{ fontSize: 13, color: ink.muted, margin: "3px 0 0" }}>
              Every NL→SQL agent in the organization — open a card to inspect it (read-only)
            </p>
          </div>
          <div style={{
            marginLeft: "auto", display: "flex", alignItems: "center", gap: 7,
            background: "#fff", border: `1px solid ${ink.line}`, borderRadius: 10,
            padding: "8px 12px", minWidth: 230,
          }}>
            <Search size={13} color={ink.faint} />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search agents…"
              style={{ border: "none", outline: "none", font: "500 12.5px system-ui", flex: 1, color: ink.primary }}
            />
          </div>
        </div>

        {error && <div style={{ ...card, color: "#B91C1C" }}>{error}</div>}

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Kpi icon={<Database size={16} />} label="Data agents" value={agents.length}
               sub={`${deployed} deployed`} />
          <Kpi icon={<Table2 size={16} />} label="Tables introspected" value={totalTables} />
          <Kpi icon={<Building2 size={16} />} label="Departments"
               value={new Set(agents.map((a) => a.department_id || "—")).size} />
          <Kpi icon={<ShieldCheck size={16} />} label="SQL dialects"
               value={new Set(agents.map((a) => a.dialect)).size} />
        </div>

        {agents.length === 0 && (
          <div style={{ ...card, color: ink.muted }}>No data agents created yet.</div>
        )}

        {Object.entries(grouped).map(([dept, ds]) => (
          <section key={dept} className="sg-section">
            <div className="sg-section-head">
              <span className="sg-section-name">{dept}</span>
              <span className="sg-section-count">{ds.length}</span>
              <span className="sg-section-rule" />
            </div>
            <div className="sg-grid">
              {ds.map((a) => (
                <button key={a.id} className="sg-card" onClick={() => openAgent(a)}>
                  <div className="sg-card-head">
                    <span className="sg-mono"><Database size={16} /></span>
                    <div className="sg-card-titles">
                      <div className="sg-name-row">
                        <div className="sg-card-name">{a.name}</div>
                      </div>
                    </div>
                    <span className="sg-status-wrap">
                      <StatusBadge status={a.status} />
                    </span>
                  </div>
                  <div className="sg-card-desc">
                    {a.description || "No description"}
                  </div>
                  <div className="sg-card-foot">
                    <span className="sg-stat"><Table2 size={13} /> {a.table_count || 0} tables</span>
                    <span className="sg-stat">{dialectLabel(a.dialect)}</span>
                    {a.status === "deployed" && (
                      <span className="sg-stat" style={{ color: a.is_private ? "#B45309" : "#166534" }}>
                        {a.is_private ? "unpublished" : "published"}
                      </span>
                    )}
                    <span className="sg-open">→</span>
                  </div>
                </button>
              ))}
            </div>
          </section>
        ))}
      </div>
    );
  }

  /* ═══════════ VIEW 2 — full-page detail ═══════════ */
  const restricted = selected.allowed_user_ids || [];
  const gen = selected.generation || {};
  const rp = selected.retrieval || {};

  return (
    <div style={{ display: "grid", gap: 14 }}>
      {/* identity band */}
      <div style={{ ...card, display: "flex", alignItems: "center", gap: 14, padding: "18px 20px" }}>
        <button
          onClick={() => setSelected(null)}
          style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            border: `1px solid ${ink.line}`, background: "#fff", borderRadius: 9,
            padding: "8px 13px", font: "600 12.5px system-ui", color: ink.primary, cursor: "pointer",
          }}
        >
          <ArrowLeft size={14} /> Back
        </button>
        <span style={{
          width: 46, height: 46, borderRadius: 13, flexShrink: 0,
          background: ink.primary, color: "#fff", display: "grid", placeItems: "center",
        }}>
          <Database size={20} />
        </span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontWeight: 800, fontSize: 17, color: ink.primary, letterSpacing: "-0.02em" }}>
            {selected.name}
          </div>
          <div style={{ fontSize: 12.5, color: ink.muted, marginTop: 2 }}>
            {deptName(selected.department_id)} · {selected.description || "No description"}
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
          <StatusBadge status={selected.status} />
          {selected.status === "deployed" && (
            <span style={{
              fontSize: 10, fontWeight: 700, padding: "2px 9px", borderRadius: 20,
              background: selected.is_private ? "#FEF2F2" : "#EFF6FF",
              color: selected.is_private ? "#991B1B" : "#1D4ED8",
            }}>
              {selected.is_private ? "NOT PUBLISHED" : "PUBLISHED"}
            </span>
          )}
        </div>
      </div>

      {selected.status === "error" && selected.last_error && (
        <div style={{ ...card, color: "#B91C1C", fontSize: 12.5 }}>
          Last error: {selected.last_error}
        </div>
      )}

      {/* stat tiles */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Kpi icon={<Table2 size={16} />} label="Tables" value={selected.table_count || 0} />
        <Kpi icon={<Database size={16} />} label="Dialect" value={dialectLabel(selected.dialect)} />
        <Kpi icon={<Calendar size={16} />} label="Created" value={fmtDate(selected.created_at)} />
      </div>

      {/* access | pipeline */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12, alignItems: "start" }}>
        <Card icon={<ShieldCheck size={15} />} title="Who can query this data?">
          <SubTitle>People</SubTitle>
          <Row k="Owner" v={
            selected.owner_id
              ? `${personName(selected.owner_id)}${personEmail(selected.owner_id) ? ` — ${personEmail(selected.owner_id)}` : ""}`
              : "—"} />
          <Row k="Department" v={
            `${deptName(selected.department_id)}${deptUsers ? ` · ${deptUsers.length} end user${deptUsers.length === 1 ? "" : "s"}` : ""}`} />
          <Row k="Visible to end users" v={
            selected.status !== "deployed"
              ? "No — not deployed"
              : selected.is_private
                ? "No — deployed but not published"
                : "Yes — live for its department"} />
          <Row k="Platform access" v={
            restricted.length === 0
              ? `Open — every department end user${deptUsers ? ` (${deptUsers.length} people)` : ""}`
              : `Restricted — only ${restricted.length} allowed user${restricted.length > 1 ? "s" : ""}`} />
          {restricted.length > 0 && (
            <div style={{ display: "grid", gap: 6, margin: "10px 0 2px" }}>
              {restricted.map((uid) => (
                <div key={uid} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5 }}>
                  <User size={12} color={ink.muted} />
                  <span style={{ fontWeight: 600, color: ink.primary }}>{personName(uid)}</span>
                  <span style={{ color: ink.faint, fontSize: 11.5 }}>{personEmail(uid)}</span>
                </div>
              ))}
            </div>
          )}

          <SubTitle>Connection</SubTitle>
          <Row k="Server" v={`${selected.host || "—"}${selected.port ? `:${selected.port}` : ""}`} />
          <Row k="Database" v={selected.database || "—"} />
          <Row k="DB account" v={selected.username || "—"} />
          <Row k="DB password" v={
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <KeyRound size={12} color={selected.has_password ? "#16A34A" : ink.faint} />
              {selected.has_password
                ? "Set — encrypted at rest, never displayed"
                : "Not set"}
            </span>} />
        </Card>

        <Card icon={<Bot size={15} />} title="Pipeline configuration" right="read-only">
          <SubTitle>Models</SubTitle>
          <Row k="SQL LLM" v={
            `${selected.llm_model || "—"}${selected.llm_provider_id ? " · company" : selected.llm_has_own_key ? " · own key" : ""}`} />
          <Row k="Embedding" v={
            `${(selected.embedding_model || "—").split("/").pop()}${selected.embedding_provider_id ? " · company" : selected.embedding_has_own_key ? " · own key" : ""}`} />
          <Row k="Temperature / max tokens" v={`${gen.temperature ?? 0} / ${gen.max_tokens ?? 2000}`} />
          <Row k="System prompt" v={gen.prompt_mode === "custom" ? "Custom" : "Default"} />

          <SubTitle>Retrieval</SubTitle>
          <Row k="Search mode" v="Hybrid (always — vector + keyword)" />
          <Row k="Context per index" v={`DDL ${rp.n_ddl ?? 10} · SQL ${rp.n_sql ?? 5} · business ${rp.n_business ?? 8}`} />
          <Row k="Query enhancement" v={rp.transform_enabled ? "On" : "Off"} />
          <Row k="Re-ranker" v={
            rp.reranker_provider === "voyage"
              ? (rp.reranker_model || "rerank-2.5") : "BGE v2-m3 (local)"} />

          <SubTitle>Guardrails</SubTitle>
          <Row k="Write protection" v="Read-only session + SELECT-only validation" />
          <Row k="Row limit / timeout" v={`${selected.row_limit ?? 1000} rows / ${Math.round((selected.timeout_ms ?? 30000) / 1000)}s`} />
          <Row k="Result rows sent to LLM" v={gen.send_results_to_llm ? "Yes (opt-in)" : "No — only shown to the user"} />
        </Card>
      </div>

    </div>
  );
};

export default AdminDataAgentPage;
