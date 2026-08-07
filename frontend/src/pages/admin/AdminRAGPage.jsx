import React, { useState, useEffect, useMemo } from "react";
import {
  ArrowLeft,
  Bot,
  Building2,
  Calendar,
  FileText,
  GitBranch,
  KeyRound,
  Layers,
  Scissors,
  Search,
  ShieldCheck,
  Target,
  User,
} from "lucide-react";
import {
  listSpaces,
  listDocuments,
  listApiKeys,
  listDepartmentUsers,
} from "../../services/ragApi";
import { listUsers } from "../../services/usersApi";
import { Badge, Kpi } from "../../components/dashboard/DashKit";
import { card, ink, mono } from "../../components/dashboard/tokens";
import "../../styles/it/spacesgrid.css";

/**
 * Admin RAG Spaces — read-only governance, two views:
 *   1. card GRID (same design language as the workspace) grouped by department
 *   2. full-page DETAIL on click: identity, access review (humans + machines),
 *      pipeline configuration, documents
 * Building and lifecycle stay with the owner in the IT workspace.
 */

const ext = (name = "") => (name.split(".").pop() || "FILE").toUpperCase().slice(0, 4);
const fmtDate = (s) => {
  const d = new Date(String(s || "").replace(" ", "T"));
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString();
};

/* the REAL chunking — the legacy chunk_strategy column defaults to
   "recursive" and hides per-document / per-format setups */
const chunkingLabel = (s) => {
  if (s.chunk_mode === "PER_DOCUMENT") return "Per document";
  const fmtMap = s.chunk_format_map || {};
  if (Object.keys(fmtMap).length) return `Per format (${Object.keys(fmtMap).length})`;
  return s.chunk_strategy || "recursive";
};

const chunkingDetail = (s) => {
  const fmtMap = s.chunk_format_map || {};
  if (s.chunk_mode === "PER_DOCUMENT")
    return "Each document keeps its own strategy (see workspace for the per-file map)";
  if (Object.keys(fmtMap).length)
    return Object.entries(fmtMap).map(([t, v]) => `${t}: ${v?.strategy || "—"}`).join("  ·  ");
  return `${s.chunk_strategy || "recursive"} — size ${s.chunk_size ?? 512}, overlap ${s.chunk_overlap ?? 50}`;
};

/* ── small pieces ── */

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

const AdminRAGPage = () => {
  const [spaces, setSpaces] = useState([]);
  const [selected, setSelected] = useState(null);
  const [docs, setDocs] = useState([]);
  const [keys, setKeys] = useState([]);
  const [deptUsers, setDeptUsers] = useState(null);
  const [users, setUsers] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    (async () => {
      try {
        setSpaces(await listSpaces());
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
    })();
  }, []);

  const openSpace = (space) => {
    setSelected(space);
    setDocs([]); setKeys([]); setDeptUsers(null);
    listDocuments(space.id).then(setDocs).catch(() => {});
    listApiKeys(space.id).then(setKeys).catch(() => {});
    if (space.department_id)
      listDepartmentUsers(space.department_id).then(setDeptUsers).catch(() => {});
  };

  const grouped = useMemo(() => {
    const filtered = spaces.filter((s) =>
      (s.name || "").toLowerCase().includes(q.trim().toLowerCase()));
    const g = {};
    filtered.forEach((s) => {
      (g[s.department_name || "No department"] ||= []).push(s);
    });
    return g;
  }, [spaces, q]);

  const personName = (uid) =>
    users[uid]?.name || (deptUsers || []).find((u) => u.id === uid)?.name || `${uid.slice(0, 8)}…`;
  const personEmail = (uid) =>
    users[uid]?.email || (deptUsers || []).find((u) => u.id === uid)?.email || "";

  if (loading) return <div style={{ ...card, color: ink.muted }}>Loading spaces…</div>;

  /* ═══════════ VIEW 1 — card grid, grouped by department ═══════════ */
  if (!selected) {
    const totalDocs = spaces.reduce((a, s) => a + (s.num_documents || 0), 0);
    const totalChunks = spaces.reduce((a, s) => a + (s.num_chunks || 0), 0);
    return (
      <div style={{ display: "grid", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 800, color: ink.primary, letterSpacing: "-0.3px", margin: 0 }}>
              RAG Spaces
            </h1>
            <p style={{ fontSize: 13, color: ink.muted, margin: "3px 0 0" }}>
              Every agent in the organization — open a card to inspect it (read-only)
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
              placeholder="Search spaces…"
              style={{ border: "none", outline: "none", font: "500 12.5px system-ui", flex: 1, color: ink.primary }}
            />
          </div>
        </div>

        {error && <div style={{ ...card, color: "#B91C1C" }}>{error}</div>}

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Kpi icon={<Bot size={16} />} label="Spaces" value={spaces.length}
               sub={`${spaces.filter((s) => s.status === "ACTIVE").length} deployed`} />
          <Kpi icon={<FileText size={16} />} label="Documents" value={totalDocs} />
          <Kpi icon={<Layers size={16} />} label="Indexed chunks" value={totalChunks} />
          <Kpi icon={<Building2 size={16} />} label="Departments"
               value={new Set(spaces.map((s) => s.department_name || "—")).size} />
        </div>

        {spaces.length === 0 && (
          <div style={{ ...card, color: ink.muted }}>No RAG spaces created yet.</div>
        )}

        {Object.entries(grouped).map(([deptName, ds]) => (
          <section key={deptName} className="sg-section">
            <div className="sg-section-head">
              <span className="sg-section-name">{deptName}</span>
              <span className="sg-section-count">{ds.length}</span>
              <span className="sg-section-rule" />
            </div>
            <div className="sg-grid">
              {ds.map((s) => (
                <button key={s.id} className="sg-card" onClick={() => openSpace(s)}>
                  <div className="sg-card-head">
                    <span className="sg-mono">{(s.name || "?").trim()[0]?.toUpperCase()}</span>
                    <div className="sg-card-titles">
                      <div className="sg-name-row">
                        <div className="sg-card-name">{s.name}</div>
                      </div>
                    </div>
                    <span className="sg-status-wrap">
                      <Badge status={s.status} />
                    </span>
                  </div>
                  <div className="sg-card-desc">
                    {s.description || "No description"}
                  </div>
                  <div className="sg-card-foot">
                    <span className="sg-stat"><FileText size={13} /> {s.num_documents || 0} docs</span>
                    <span className="sg-stat"><Layers size={13} /> {s.num_chunks || 0} chunks</span>
                    {s.status === "ACTIVE" && (
                      <span className="sg-stat" style={{ color: s.is_private ? "#B45309" : "#166534" }}>
                        {s.is_private ? "unpublished" : "published"}
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
  const activeKeys = keys.filter((k) => k.status === "active");
  const rp = selected.retrieval_params || {};

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
          background: ink.primary, color: "#fff",
          display: "grid", placeItems: "center", fontWeight: 800, fontSize: 19,
        }}>
          {(selected.name || "?").trim()[0]?.toUpperCase()}
        </span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontWeight: 800, fontSize: 17, color: ink.primary, letterSpacing: "-0.02em" }}>
            {selected.name}
          </div>
          <div style={{ fontSize: 12.5, color: ink.muted, marginTop: 2 }}>
            {selected.department_name || "No department"} · {selected.description || "No description"}
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
          <Badge status={selected.status} />
          {selected.status === "ACTIVE" && (
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

      {/* stat tiles */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Kpi icon={<FileText size={16} />} label="Documents" value={selected.num_documents || 0} />
        <Kpi icon={<Layers size={16} />} label="Indexed chunks" value={selected.num_chunks || 0} />
        <Kpi icon={<Scissors size={16} />} label="Chunking" value={chunkingLabel(selected)} />
        <Kpi icon={<Target size={16} />} label="Top-K" value={selected.top_k ?? 5} />
        <Kpi icon={<GitBranch size={16} />} label="Versions" value={selected.version_count ?? 0} />
        <Kpi icon={<Calendar size={16} />} label="Created" value={fmtDate(selected.created_at)} />
      </div>

      {/* access | configuration */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12, alignItems: "start" }}>
        <Card icon={<ShieldCheck size={15} />} title="Who can talk to this bot?">
          <SubTitle>People</SubTitle>
          <Row k="Owner" v={
            selected.owner_id
              ? `${personName(selected.owner_id)}${personEmail(selected.owner_id) ? ` — ${personEmail(selected.owner_id)}` : ""}`
              : "—"} />
          <Row k="Department" v={
            `${selected.department_name || "—"}${deptUsers ? ` · ${deptUsers.length} end user${deptUsers.length === 1 ? "" : "s"}` : ""}`} />
          <Row k="Visible to end users" v={
            selected.status !== "ACTIVE"
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

          <SubTitle>Machines (API)</SubTitle>
          <Row k="External apps" v={
            activeKeys.length === 0
              ? "None — no active API keys"
              : `${activeKeys.length} active key${activeKeys.length > 1 ? "s" : ""} can chat with this agent`} />
          {activeKeys.length > 0 && (
            <div style={{ display: "grid", gap: 7, marginTop: 8 }}>
              {activeKeys.map((k) => (
                <div key={k.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, flexWrap: "wrap" }}>
                  <KeyRound size={12} color="#16A34A" />
                  <span style={{ fontWeight: 600, color: ink.primary }}>{k.name}</span>
                  <span style={{ ...mono, color: ink.faint }}>{k.key_display}</span>
                  <span style={{ marginLeft: "auto", color: ink.muted, fontSize: 11.5 }}>
                    {k.request_count ?? 0} req{k.last_used_at ? ` · last ${fmtDate(k.last_used_at)}` : " · never used"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card icon={<Bot size={15} />} title="Pipeline configuration" right="read-only">
          <SubTitle>Models</SubTitle>
          <Row k="Embedding" v={
            `${(selected.embedding_model || "—").split("/").pop()}${selected.embedding_provider_id ? " · company" : selected.embedding_has_own_key ? " · own key" : ""}`} />
          <Row k="LLM" v={
            `${selected.llm_model || "—"}${selected.llm_provider_id ? " · company" : selected.llm_has_own_key ? " · own key" : ""}`} />
          <Row k="Temperature / max tokens" v={`${selected.llm_temperature ?? 0.2} / ${selected.llm_max_tokens ?? 1024}`} />
          <Row k="System prompt" v={selected.system_prompt ? "Custom" : "Default"} />

          <SubTitle>Chunking</SubTitle>
          <Row k="Mode" v={chunkingLabel(selected)} />
          <Row k="Detail" v={chunkingDetail(selected)} />

          <SubTitle>Retrieval</SubTitle>
          <Row k="Search mode" v={rp.search_mode || "hybrid"} />
          <Row k="Top-K" v={selected.top_k ?? 5} />
          <Row k="Query enhancement" v={(rp.transform_enabled ?? true) ? "On" : "Off"} />
          <Row k="Re-ranker" v={
            rp.reranker_provider === "voyage" ? (rp.reranker_model || "rerank-2.5") : "BGE v2-m3 (local)"} />
        </Card>
      </div>

      {/* documents */}
      <Card icon={<FileText size={15} />} title="Knowledge base" right={`${docs.length} document${docs.length === 1 ? "" : "s"}`}>
        {docs.length === 0 ? (
          <div style={{ fontSize: 12.5, color: ink.muted }}>No documents uploaded yet.</div>
        ) : (
          <div style={{ display: "grid", gap: 8, marginTop: 4 }}>
            {docs.map((d) => (
              <div key={d.id} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12.5 }}>
                <span style={{
                  fontSize: 9.5, fontWeight: 800, color: ink.blue, background: "#EFF6FF",
                  borderRadius: 6, padding: "3px 8px", flexShrink: 0, letterSpacing: ".03em",
                }}>
                  {ext(d.file_name)}
                </span>
                <span style={{ fontWeight: 600, color: ink.primary, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {d.file_name}
                </span>
                <span style={{ color: ink.faint, fontSize: 11.5, flexShrink: 0 }}>
                  {d.num_chunks || 0} chunks · {String(d.status || "")}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};

export default AdminRAGPage;
