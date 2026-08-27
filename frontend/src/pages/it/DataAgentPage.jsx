import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Check, ChevronDown, ChevronRight, Database, Loader2, Plug, RefreshCw,
  Table2, X,
} from "lucide-react";
import {
  createDataSource, dataJobStatus, deleteDataSource, deploySource,
  getSourceSchema, introspectSource, listDataSources, pauseSource,
  setSourceAuthorization, testDataSource, updateDataSource,
} from "../../services/dataAgentApi";
import {
  getEmbeddingModels, listDepartments, listDepartmentUsers,
} from "../../services/ragApi";
import CustomDropdown from "../../components/it/rag/CustomDropdown";
import LLMSourceSelector from "../../components/it/rag/LLMSourceSelector";
import EmbeddingSourceSelector from "../../components/it/rag/EmbeddingSourceSelector";
import AccessSelector from "../../components/it/rag/AccessSelector";
import KnowledgePanel from "../../components/it/dataagent/KnowledgePanel";
import VersionsPanel from "../../components/it/dataagent/VersionsPanel";
import TestingPanel from "../../components/it/dataagent/TestingPanel";
import StatusBadge from "../../components/it/dataagent/StatusBadge";
import SavedBar from "../../components/it/dataagent/SavedBar";
import RetrievalPanel from "../../components/it/dataagent/RetrievalPanel";
import DataFlowPanel from "../../components/it/dataagent/DataFlowPanel";
import { DIALECTS, dialectLabel } from "../../components/it/dataagent/ui";
import "../../styles/it/rag.css";
import "../../styles/it/spacesgrid.css";

/*
 * Data Agent — WORKSPACE, in the exact RAG-space format:
 *   page 1  sg-card grid by department + the RAG create modal
 *           (Department · Name · Description · Visibility)
 *   page 2  rag-space-layout: content panels + right STEPPER sidebar
 *           1 Connection → 2 Models (Local/Company/My key, same selectors
 *           as RAG) → 3 Schema & Training → 4 Authorization · Manage: Test
 *           console. Deploy / Pause / Delete live in the header.
 */

/* ── the stepper (RightSidebar pattern, data-agent steps) ── */
function DataAgentSidebar({ panel, setPanel, source }) {
  const hints = {
    connection: source.host
      ? `${dialectLabel(source.dialect)} · ${source.database || "—"}`
      : "Connect your database",
    models: (source.llm_model || "choose models").split("/").pop(),
    knowledge: source.table_count
      ? `${source.table_count} tables · ${source.mode} mode`
      : "Schema · training · business",
    retrieval: `hybrid · top-k `
      + `${source.retrieval?.n_ddl ?? 10}/${source.retrieval?.n_sql ?? 5}/`
      + `${source.retrieval?.n_business ?? 8}`,
  };
  const STEPS = [
    { key: "connection", label: "Connection" },
    { key: "models", label: "Models" },
    { key: "knowledge", label: "Knowledge" },
    { key: "retrieval", label: "Retrieval" },
  ];
  return (
    <div className="rag-side">
      <button
        className={`rag-side-flow ${panel === "flow" ? "active" : ""}`}
        onClick={() => setPanel("flow")}
      >
        View flow
      </button>
      <div className="rag-side-eyebrow">Pipeline</div>
      <div className="rag-steps">
        {STEPS.map((s, i) => (
          <button key={s.key}
                  className={`rag-step ${panel === s.key ? "active" : ""}`}
                  onClick={() => setPanel(s.key)}>
            <span className="rag-step-badge">{i + 1}</span>
            <span className="rag-step-txt">
              <span className="rag-step-name">{s.label}</span>
              <span className="rag-step-hint">{hints[s.key]}</span>
            </span>
          </button>
        ))}
      </div>
      <div className="rag-side-eyebrow" style={{ marginTop: 18 }}>Manage</div>
      <div className="rag-steps rag-steps-manage">
        <button className={`rag-step ${panel === "test" ? "active" : ""}`}
                onClick={() => setPanel("test")}>
          <span className="rag-step-badge">✓</span>
          <span className="rag-step-txt">
            <span className="rag-step-name">Testing</span>
            <span className="rag-step-hint">Manual · auto · security</span>
          </span>
        </button>
        <button className={`rag-step ${panel === "versions" ? "active" : ""}`}
                onClick={() => setPanel("versions")}>
          <span className="rag-step-badge">⧉</span>
          <span className="rag-step-txt">
            <span className="rag-step-name">Versions</span>
            <span className="rag-step-hint">Save &amp; deploy configs</span>
          </span>
        </button>
      </div>
    </div>
  );
}

/* ── read-only schema preview (Connection page) ──
   Shows what introspection captured from the connected database; when the
   catalog is still empty it offers to run introspection right here (same
   background job + polling as Knowledge). Curation — enable toggles and
   descriptions — deliberately stays in Knowledge: this is a viewer. */
function SchemaModal({ source, onClose, onChanged, setError }) {
  const [schema, setSchema] = useState(null);        // null = loading
  const [openTables, setOpenTables] = useState({});
  const [filter, setFilter] = useState("");
  const [job, setJob] = useState(null);
  const pollRef = useRef(null);

  const load = () =>
    getSourceSchema(source.id).then(setSchema).catch(() => setSchema([]));
  useEffect(() => {
    load();
    return () => clearInterval(pollRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source.id]);

  const introspect = async () => {
    try {
      const { job_id: jobId } = await introspectSource(source.id);
      setJob({ status: "running", step: "Starting…" });
      pollRef.current = setInterval(async () => {
        try {
          const st = await dataJobStatus(jobId);
          setJob(st);
          if (st.status !== "running") {
            clearInterval(pollRef.current);
            onChanged();
            load();
          }
        } catch {
          clearInterval(pollRef.current);
        }
      }, 1200);
    } catch (e) {
      setError(e.message);
    }
  };

  const running = job?.status === "running";
  const rows = (schema || []).filter((t) =>
    !filter.trim() ||
    `${t.schema}.${t.table}`.toLowerCase().includes(filter.trim().toLowerCase()));

  return (
    <div className="rag-create-overlay" onClick={onClose}>
      <div className="rag-create-modal" style={{ maxWidth: 720 }}
           onClick={(e) => e.stopPropagation()}>
        <div className="rag-create-modal-head">
          <span className="rag-create-title" style={{ display: "inline-flex",
                                                      alignItems: "center", gap: 8 }}>
            <Database size={16} /> Schema — {source.database || source.name}
          </span>
          <button className="rag-create-x" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div style={{ padding: "16px 22px", overflowY: "auto", minHeight: 160 }}>
          {schema === null && <div className="rag-cfg-hint">Loading…</div>}

          {running && (
            <div style={{ display: "grid", gap: 6, marginBottom: 12 }}>
              <div style={{ font: "600 12.5px system-ui", color: "#0F172A" }}>
                Introspecting… {job.step ? `· ${job.step}` : ""}
                {job.total ? ` · ${job.done}/${job.total}` : ""}
              </div>
              <div style={{ height: 6, background: "#EEF2F5", borderRadius: 4 }}>
                <div style={{
                  width: job.total ? `${Math.round((job.done / job.total) * 100)}%` : "30%",
                  height: "100%", background: "#2563EB", borderRadius: 4,
                  transition: "width .4s",
                }} />
              </div>
            </div>
          )}
          {job && !running && job.status === "error" && (
            <div className="rag-cfg-warn" style={{ marginBottom: 12 }}>
              Introspection failed: {job.error}
            </div>
          )}

          {schema?.length === 0 && !running && (
            <div style={{ textAlign: "center", padding: "22px 0",
                          display: "grid", gap: 10, justifyItems: "center" }}>
              <div className="rag-cfg-hint" style={{ margin: 0 }}>
                No schema captured yet — introspection reads the tables and
                columns from the connected database.
              </div>
              <button className="rag-btn rag-btn-blue" onClick={introspect}>
                <RefreshCw size={13} /> Introspect now
              </button>
            </div>
          )}

          {rows.length > 0 && (
            <div style={{ display: "grid", gap: 8 }}>
              {schema.length > 6 && (
                <input className="rag-cfg-select" style={{ maxWidth: 260 }}
                       value={filter} onChange={(e) => setFilter(e.target.value)}
                       placeholder="Filter tables…" />
              )}
              {rows.map((t) => (
                <div key={t.id} style={{ border: "1px solid #E5E9F0",
                                         borderRadius: 10, padding: "9px 12px",
                                         opacity: t.is_enabled ? 1 : 0.55 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                    <button onClick={() => setOpenTables((o) => ({ ...o, [t.id]: !o[t.id] }))}
                            style={{ border: "none", background: "none", cursor: "pointer",
                                     color: "#64748B", display: "inline-flex" }}>
                      {openTables[t.id] ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                    </button>
                    <span style={{ fontWeight: 700, fontSize: 13, color: "#0F172A" }}>
                      {t.schema}.{t.table}
                    </span>
                    <span style={{ fontSize: 11, color: "#94A3B8" }}>
                      {t.columns.length} cols
                      {t.row_estimate != null ? ` · ~${t.row_estimate} rows` : ""}
                    </span>
                    {!t.is_enabled && (
                      <span style={{ marginLeft: "auto", fontSize: 9.5, fontWeight: 800,
                                     padding: "2px 7px", borderRadius: 20,
                                     background: "#F1F5F9", color: "#64748B" }}>
                        DISABLED
                      </span>
                    )}
                  </div>
                  {openTables[t.id] && (
                    <div style={{ marginTop: 9, display: "grid", gap: 4 }}>
                      {t.columns.map((c) => (
                        <div key={c.name}
                             style={{ display: "flex", gap: 8, fontSize: 12,
                                      fontFamily: "ui-monospace, Consolas, monospace" }}>
                          <span style={{ color: "#0F172A", fontWeight: 600,
                                         minWidth: 180 }}>{c.name}</span>
                          <span style={{ color: "#64748B" }}>{c.data_type}</span>
                          {c.pk && <span style={{ color: "#1D4ED8", fontWeight: 700 }}>PK</span>}
                          {c.fk_ref && <span style={{ color: "#94A3B8" }}>→ {c.fk_ref}</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
          {schema?.length > 0 && rows.length === 0 && (
            <div className="rag-cfg-hint">No table matches “{filter}”.</div>
          )}
        </div>

        {schema?.length > 0 && (
          <div style={{ padding: "10px 22px", borderTop: "1px solid #EEF2F7",
                        fontSize: 11.5, color: "#94A3B8" }}>
            Read-only preview — enable/disable tables and add descriptions in
            Knowledge → Schema.
          </div>
        )}
      </div>
    </div>
  );
}

/* ── panel 1: connection ── */
function ConnectionPanel({ source, onChanged, setError, editable }) {
  const [form, setForm] = useState({
    dialect: source.dialect, host: source.host, port: source.port,
    database: source.database, username: source.username, password: "",
  });
  const [testState, setTestState] = useState(null);
  const [schemaOpen, setSchemaOpen] = useState(false);
  const setF = (k, v) => {
    setForm((f) => {
      const next = { ...f, [k]: v };
      if (k === "dialect") {
        const p = DIALECTS.find((d) => d.name === v)?.port;
        if (p) next.port = p;
      }
      return next;
    });
    setTestState(null);
  };

  const handleTest = async () => {
    setTestState("testing");
    try {
      await updateDataSource(source.id, {
        dialect: form.dialect, host: form.host,
        port: Number(form.port) || undefined,
        database: form.database, username: form.username,
        ...(form.password ? { password: form.password } : {}),
      });
      setTestState(await testDataSource(source.id));
      onChanged();
    } catch (e) {
      setTestState({ ok: false, error: e.message });
      setError(e.message);
    }
  };

  return (
    <div className="rag-cfg-panel">
      <div className="rag-cfg-head">
        <div>
          <div className="rag-cfg-title">Database connection</div>
          <div className="rag-cfg-sub">
            The enterprise database this agent answers from.
          </div>
        </div>
      </div>

      <div className="rag-cfg-warn" style={{ marginBottom: 12 }}>
        🔐 Use a <strong>read-only database user</strong> scoped to the schemas you
        expose. The agent enforces SELECT-only + timeouts + row caps on top — the
        account stays the primary control.
      </div>

      <label className="rag-cfg-label">Dialect</label>
      <CustomDropdown
        showLogo
        disabled={!editable}
        value={form.dialect}
        onChange={(v) => setF("dialect", v)}
        options={DIALECTS.map((d) => ({
          value: d.name, label: d.label, family: d.name,
          sub: `Default port ${d.port}`,
        }))}
      />

      <label className="rag-cfg-label">Host : Port</label>
      <div style={{ display: "flex", gap: 8 }}>
        <input className="rag-cfg-select" value={form.host} disabled={!editable}
               onChange={(e) => setF("host", e.target.value)} />
        <input className="rag-cfg-select" style={{ width: 110 }} value={form.port}
               disabled={!editable} onChange={(e) => setF("port", e.target.value)} />
      </div>

      <label className="rag-cfg-label">Database</label>
      <input className="rag-cfg-select" value={form.database} disabled={!editable}
             onChange={(e) => setF("database", e.target.value)} />

      <label className="rag-cfg-label">Username (read-only user)</label>
      <input className="rag-cfg-select" value={form.username} disabled={!editable}
             onChange={(e) => setF("username", e.target.value)} />

      <label className="rag-cfg-label">
        Password{source.has_password && !form.password ? " · saved (type to replace)" : ""}
      </label>
      <input className="rag-cfg-select" type="password" value={form.password}
             disabled={!editable} placeholder={source.has_password ? "••••••••" : ""}
             onChange={(e) => setF("password", e.target.value)} />

      {testState && testState !== "testing" && (
        <div className={testState.ok ? "rag-cfg-hint" : "rag-cfg-warn"}
             style={{ marginTop: 10 }}>
          {testState.ok ? <><Check size={13} /> Connected — {testState.version}</>
                        : <><X size={13} /> {testState.error || "Connection failed"}</>}
        </div>
      )}
      <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "center" }}>
        <button className="rag-btn rag-btn-blue" onClick={handleTest}
                disabled={!editable || testState === "testing" || !form.host || !form.database || !form.username}>
          {testState === "testing" ? <Loader2 size={13} className="spin" /> : <Plug size={13} />}
          {" "}Test connection
        </button>
        {(testState?.ok ||
          ["connected", "trained", "stale", "deployed"].includes(source.status)) && (
          <button className="rag-btn" onClick={() => setSchemaOpen(true)}>
            <Table2 size={13} /> View schema
          </button>
        )}
      </div>

      {schemaOpen && (
        <SchemaModal source={source} onClose={() => setSchemaOpen(false)}
                     onChanged={onChanged} setError={setError} />
      )}
    </div>
  );
}

/* ── panel 2: models (the RAG selectors, verbatim) ── */
function ModelsPanel({ source, onChanged, setError, editable }) {
  const [cfg, setCfg] = useState({ ...source });
  const [embedModels, setEmbedModels] = useState([]);
  const [saving, setSaving] = useState(false);
  const setC = (patch) => setCfg((c) => ({ ...c, ...patch }));

  useEffect(() => {
    getEmbeddingModels().then((r) => setEmbedModels(r.models || r || []))
      .catch(() => {});
  }, []);
  useEffect(() => { setCfg({ ...source }); }, [source.id]);   // eslint-disable-line react-hooks/exhaustive-deps

  const save = async () => {
    setSaving(true);
    try {
      await updateDataSource(source.id, {
        llm_provider: cfg.llm_provider, llm_provider_id: cfg.llm_provider_id,
        llm_model: cfg.llm_model, llm_base_url: cfg.llm_base_url,
        ...(cfg.llm_api_key ? { llm_api_key: cfg.llm_api_key } : {}),
        llm_temperature: cfg.llm_temperature ?? 0,
        llm_max_tokens: cfg.llm_max_tokens ?? 2000,
        prompt_mode: cfg.prompt_mode || "default",
        system_prompt: cfg.system_prompt || "",
        embedding_provider: cfg.embedding_provider,
        embedding_provider_id: cfg.embedding_provider_id,
        embedding_model: cfg.embedding_model,
        embedding_base_url: cfg.embedding_base_url,
        ...(cfg.embedding_api_key ? { embedding_api_key: cfg.embedding_api_key } : {}),
      });
      onChanged();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rag-cfg-panel">
      <div className="rag-cfg-head">
        <div>
          <div className="rag-cfg-title">Models</div>
          <div className="rag-cfg-sub">
            Same sources as your RAG spaces. The LLM writes the SQL; the
            embedding model powers the schema vector store (re-train after
            changing it).
          </div>
        </div>
      </div>

      <LLMSourceSelector value={cfg} onChange={setC}
                         hasOwnKey={source.llm_has_own_key} />

      {/* generation config — determinism, budget, and the system prompt */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 14 }}>
        <div>
          <label className="rag-cfg-label">Temperature</label>
          <input className="rag-cfg-select" type="number" step="0.1" min="0" max="1"
                 value={cfg.llm_temperature ?? 0}
                 onChange={(e) => setC({ llm_temperature: Number(e.target.value) })} />
          <div className="rag-cfg-hint">0 = deterministic. SQL generation wants 0.</div>
        </div>
        <div>
          <label className="rag-cfg-label">Max tokens</label>
          <input className="rag-cfg-select" type="number" min="256" max="8000" step="128"
                 value={cfg.llm_max_tokens ?? 2000}
                 onChange={(e) => setC({ llm_max_tokens: Number(e.target.value) })} />
          <div className="rag-cfg-hint">Ceiling for the generated SQL.</div>
        </div>
      </div>

      <label className="rag-cfg-label" style={{ marginTop: 14 }}>System prompt</label>
      <div className="rag-cfg-cards">
        {[["default", "Default", "Platform-hardened rules"],
          ["custom", "Custom", "Your own instructions"]].map(([k, n, d]) => (
          <button key={k}
                  className={`rag-cfg-card ${(cfg.prompt_mode || "default") === k ? "active" : ""}`}
                  onClick={() => setC({ prompt_mode: k })}>
            <div className="rag-cfg-card-n">{n}</div>
            <div className="rag-cfg-card-d">{d}</div>
          </button>
        ))}
      </div>
      {cfg.prompt_mode === "custom" && (
        <>
          <textarea className="rag-cfg-select" rows={6}
                    style={{ marginTop: 10, fontFamily: "inherit" }}
                    value={cfg.system_prompt || ""}
                    onChange={(e) => setC({ system_prompt: e.target.value })}
                    placeholder="e.g. Always filter out test accounts (email LIKE '%@test%'). Prefer French column labels in the output." />
          <div className="rag-cfg-hint">
            The <strong>safety rules</strong> (one SELECT · no writes · only known
            tables · INSUFFICIENT_SCHEMA) are always appended — they are what makes
            validation and honest refusals possible.
          </div>
        </>
      )}

      <div style={{ height: 18 }} />
      <EmbeddingSourceSelector value={cfg} onChange={setC}
                               hasOwnKey={source.embedding_has_own_key}
                               embedModels={embedModels} />

      <div style={{ marginTop: 16 }}>
        <button className="rag-btn rag-btn-blue" onClick={save}
                disabled={!editable || saving}>
          {saving ? "Saving…" : "Save models"}
        </button>
      </div>
    </div>
  );
}

/* ── panel: access (the RAG AccessSelector, verbatim) ── */
function AccessPanel({ source, onChanged, setError }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [allowed, setAllowed] = useState(source.allowed_user_ids || []);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setAllowed(source.allowed_user_ids || []);
    if (source.department_id) {
      setLoading(true);
      listDepartmentUsers(source.department_id)
        .then(setUsers).catch(() => setUsers([]))
        .finally(() => setLoading(false));
    } else {
      setUsers([]);
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source.id, source.department_id]);

  const save = async () => {
    setSaving(true);
    try { await setSourceAuthorization(source.id, allowed); onChanged(); }
    catch (e) { setError(e.message); }
    finally { setSaving(false); }
  };

  return (
    <div className="rag-cfg-panel">
      <div className="rag-cfg-head">
        <div>
          <div className="rag-cfg-title">Access</div>
          <div className="rag-cfg-sub">Who in the department can query this agent.</div>
        </div>
        <button className="rag-btn rag-btn-dark" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
      </div>

      <label className="rag-cfg-label">Who can use this agent</label>
      <AccessSelector users={users} allowedIds={allowed}
                      onChange={setAllowed} loading={loading} />
      <div className="rag-cfg-hint" style={{ marginTop: 10 }}>
        Choose who in the department can use this agent — end users and IT
        members. Click a member to exclude them. Changes apply after you press{" "}
        <strong>Save</strong>. You (the owner) and admins always have access.
      </div>
    </div>
  );
}

/* ═══════════════════ PAGE ═══════════════════ */

const DataAgentPage = () => {
  const [rows, setRows] = useState([]);
  const [departments, setDepartments] = useState([]);
  // The URL is the source of truth for which agent is open (like the RAG
  // workspace): /it/data-agent/:sourceId — refresh and the browser back
  // button both land where they should.
  const { sourceId } = useParams();
  const navigate = useNavigate();
  const openAgent = (id) => {
    setPanel("connection");
    navigate(`/it/data-agent/${id}`);
  };
  const goBack = () => navigate("/it/data-agent");
  const [panel, setPanel] = useState("connection");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [acting, setActing] = useState(false);

  // create modal (RAG format: department / name / description / visibility)
  const [showCreate, setShowCreate] = useState(false);
  const [createDept, setCreateDept] = useState("");
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [createPrivate, setCreatePrivate] = useState(true);
  const [createDeptUsers, setCreateDeptUsers] = useState([]);
  const [createUserIds, setCreateUserIds] = useState([]);
  const [showCreateAccess, setShowCreateAccess] = useState(false);

  useEffect(() => {
    setCreateUserIds([]);
    setShowCreateAccess(false);
    if (createDept)
      listDepartmentUsers(createDept).then(setCreateDeptUsers)
        .catch(() => setCreateDeptUsers([]));
    else setCreateDeptUsers([]);
  }, [createDept]);

  const refresh = async () => {
    try { setRows(await listDataSources()); } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };
  useEffect(() => {
    refresh();
    listDepartments().then(setDepartments).catch(() => {});
  }, []);

  const selected = rows.find((s) => s.id === sourceId);

  // unknown / deleted id in the URL → back to the grid
  useEffect(() => {
    if (!loading && sourceId && !selected) navigate("/it/data-agent", { replace: true });
  }, [loading, sourceId, selected, navigate]);
  const deptName = (id) => departments.find((d) => d.id === id)?.name || "No department";

  const grouped = useMemo(() => {
    const g = {};
    rows.forEach((s) => { (g[deptName(s.department_id)] ||= []).push(s); });
    return g;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, departments]);

  const handleCreate = async () => {
    try {
      const d = await createDataSource({
        name: newName || "Unnamed agent", description: newDesc,
        department_id: createDept || null, is_private: createPrivate,
        dialect: "postgres", host: "localhost", port: 5432,
        database: "", username: "",
      });
      if (createUserIds.length)                     // RAG rule: empty = open
        await setSourceAuthorization(d.id, createUserIds);
      setShowCreate(false);
      setNewName(""); setNewDesc(""); setCreateDept(""); setCreatePrivate(true);
      setCreateUserIds([]);
      await refresh();
      openAgent(d.id);
      setPanel("connection");
    } catch (e) { setError(e.message); }
  };

  const handleDelete = async (s) => {
    if (!window.confirm(`Delete “${s.name}”? Schema, training and chat history disappear.`)) return;
    try { await deleteDataSource(s.id); goBack(); refresh(); }
    catch (e) { setError(e.message); }
  };

  const handleDeploy = async () => {
    setActing(true);
    try {
      if (selected.status === "deployed") await pauseSource(selected.id);
      else await deploySource(selected.id);
      refresh();
    } catch (e) { setError(e.message); }
    finally { setActing(false); }
  };

  if (loading)
    return <div className="rag-page"><div className="rag-empty-state">Loading…</div></div>;

  /* ═══ PAGE 1 — grid + RAG create modal ═══ */
  if (!selected) {
    return (
      <div className="rag-page" style={{ display: "block" }}>
        <div className="rag-main">
          {error && <div className="rag-toast rag-toast-error">{error}</div>}

          <div className="sg-head">
            <div>
              <h1 className="sg-title">Data Agent — Workspace</h1>
              <p className="sg-sub">
                Build NL→SQL agents on your databases, then deploy them to your departments
              </p>
            </div>
            <button className="sg-new" onClick={() => setShowCreate(true)}>
              + New data agent
            </button>
          </div>

          {showCreate && (
            <div className="rag-create-overlay"
                 onClick={(e) => e.target === e.currentTarget && setShowCreate(false)}>
              <div className="rag-create-modal">
                <div className="rag-create-modal-head">
                  <span className="rag-create-title">New Data Agent</span>
                  <button className="rag-create-x" onClick={() => setShowCreate(false)}>✕</button>
                </div>
                <div className="rag-create-body">
                  <label className="rag-create-label">Department</label>
                  <select className="rag-create-input" value={createDept}
                          onChange={(e) => setCreateDept(e.target.value)}>
                    <option value="">Select a department…</option>
                    {departments.map((d) => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>

                  <label className="rag-create-label">Name</label>
                  <input className="rag-create-input" placeholder="e.g. Sales analytics"
                         value={newName} onChange={(e) => setNewName(e.target.value)} />

                  <label className="rag-create-label">Description (optional)</label>
                  <input className="rag-create-input"
                         placeholder="What can users ask this agent?"
                         value={newDesc} onChange={(e) => setNewDesc(e.target.value)} />

                  <label className="rag-create-label">Visibility</label>
                  <div className="sg-vis">
                    <button type="button"
                            className={`sg-vis-opt ${createPrivate ? "active" : ""}`}
                            onClick={() => setCreatePrivate(true)}>
                      🔒 Private
                      <span>Only me &amp; my IT team</span>
                    </button>
                    <button type="button"
                            className={`sg-vis-opt ${!createPrivate ? "active" : ""}`}
                            onClick={() => setCreatePrivate(false)}>
                      🏢 Department
                      <span>Members can use it once deployed</span>
                    </button>
                  </div>

                  {/* Member access — only when targeting the department (RAG pattern) */}
                  {!createPrivate && createDept && !showCreateAccess && (
                    <div className="rag-create-access">
                      <span className="rag-create-access-dot" />
                      <div style={{ flex: 1 }}>
                        <div className="rag-create-access-title">
                          Open to everyone in the department
                        </div>
                        <div className="rag-create-access-sub">
                          All members can use this agent by default.
                        </div>
                      </div>
                      <button type="button" className="rag-btn rag-btn-sm"
                              onClick={() => setShowCreateAccess(true)}>
                        Personalize
                      </button>
                    </div>
                  )}
                  {!createPrivate && createDept && showCreateAccess && (
                    <>
                      <div style={{ display: "flex", justifyContent: "space-between",
                                    alignItems: "center", margin: "16px 0 8px" }}>
                        <label className="rag-create-label" style={{ margin: 0 }}>
                          Personalize access
                        </label>
                        <button type="button" className="rag-btn rag-btn-sm"
                                onClick={() => {
                                  setShowCreateAccess(false);
                                  setCreateUserIds([]);
                                }}>
                          Reset to everyone
                        </button>
                      </div>
                      <AccessSelector
                        compact
                        users={createDeptUsers}
                        allowedIds={createUserIds}
                        onChange={setCreateUserIds}
                      />
                    </>
                  )}
                </div>

                <div className="rag-create-foot">
                  <button className="rag-btn" onClick={() => setShowCreate(false)}>
                    Cancel
                  </button>
                  <button className="rag-btn rag-btn-blue"
                          onClick={handleCreate}
                          disabled={!newName.trim() || !createDept}>
                    Create agent
                  </button>
                </div>
              </div>
            </div>
          )}

          {rows.length === 0 && (
            <div className="sg-empty">
              <div className="sg-empty-ic"><Database size={26} /></div>
              <div className="sg-empty-title">No data agents yet</div>
              <div className="sg-empty-sub">
                Create one, connect a database, train it, and deploy it.
              </div>
            </div>
          )}

          {Object.entries(grouped).map(([dept, ds]) => (
            <section key={dept} className="sg-section">
              <div className="sg-section-head">
                <span className="sg-section-name">{dept}</span>
                <span className="sg-section-count">{ds.length}</span>
                <span className="sg-section-rule" />
              </div>
              <div className="sg-grid">
                {ds.map((s) => (
                  <button key={s.id} className="sg-card"
                          onClick={() => openAgent(s.id)}>
                    <div className="sg-card-head">
                      <span className="sg-mono"><Database size={16} /></span>
                      <div className="sg-card-titles">
                        <div className="sg-name-row">
                          <div className="sg-card-name">{s.name}</div>
                        </div>
                      </div>
                      <span className="sg-status-wrap"><StatusBadge status={s.status} /></span>
                    </div>
                    <div className="sg-card-desc">
                      {s.description || `${dialectLabel(s.dialect)} · natural-language SQL agent`}
                    </div>
                    <div className="sg-card-foot">
                      <span className="sg-stat"><Table2 size={13} /> {s.table_count || 0} tables</span>
                      <span className="sg-stat">{dialectLabel(s.dialect)}</span>
                      <span className="sg-open">→</span>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    );
  }

  /* ═══ PAGE 2 — RAG space layout: content + stepper ═══ */
  const testable = ["trained", "stale", "deployed"].includes(selected.status);
  return (
    <div className="rag-page">
      <div className="rag-space-layout">
        <div className="rag-space-content">
          <div className="rag-header">
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <button className="rag-btn rag-btn-sm" onClick={goBack}>
                ← Back
              </button>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div className="rag-header-title">{selected.name}</div>
                  <StatusBadge status={selected.status} />
                </div>
                <div className="rag-header-desc">
                  {deptName(selected.department_id)}
                  {selected.description ? ` · ${selected.description}` : ""}
                </div>
              </div>
            </div>
            <div className="rag-header-actions">
              <span className="rag-config-tag">
                {selected.table_count || 0} tables · {selected.mode}
              </span>
              <button
                className={`rag-btn rag-btn-sm ${panel === "access" ? "rag-btn-dark" : ""}`}
                onClick={() => setPanel("access")}
              >
                🔒 Access
              </button>
              {selected.status === "deployed" ? (
                <button className="rag-btn rag-btn-sm" onClick={handleDeploy} disabled={acting}>
                  {acting ? "Pausing…" : "⏸ Pause deployment"}
                </button>
              ) : (
                <button className="rag-btn rag-btn-sm rag-btn-blue" onClick={handleDeploy}
                        disabled={acting || !testable}
                        title={!testable ? "Train the agent first" : ""}>
                  🚀 Deploy
                </button>
              )}
              <button className="rag-btn rag-btn-sm rag-btn-red"
                      onClick={() => handleDelete(selected)}>
                Delete
              </button>
            </div>
          </div>

          {error && <div className="rag-toast rag-toast-error">{error}</div>}

          {selected.status === "stale" && (
            <div className="rag-cfg-warn" style={{ margin: "0 0 12px" }}>
              ⚠️ <strong>Re-train needed.</strong> The schema or its curation changed —
              train again (Knowledge → Train) so the agent uses the new state.
            </div>
          )}

          {panel === "connection" && (
            <>
              <SavedBar title="Connection" accent="#2563eb" chips={{
                Dialect: dialectLabel(selected.dialect),
                Host: `${selected.host || "—"}:${selected.port || ""}`,
                Database: selected.database || "—",
                User: selected.username || "—",
                Status: selected.status,
              }} />
              <ConnectionPanel source={selected} onChanged={refresh}
                               setError={setError} editable />
            </>
          )}
          {panel === "models" && (
            <>
              <SavedBar title="Models" accent="#8b5cf6" chips={{
                LLM: selected.llm_model || "—",
                "LLM source": selected.llm_provider_id ? "Company"
                  : selected.llm_has_own_key ? "My key" : selected.llm_provider,
                Embedding: (selected.embedding_model || "—").split("/").pop(),
                "Embedding source": selected.embedding_provider_id ? "Company"
                  : selected.embedding_has_own_key ? "My key" : "Local",
              }} />
              <ModelsPanel key={selected.id} source={selected} onChanged={refresh}
                           setError={setError} editable />
            </>
          )}
          {panel === "knowledge" && (
            <KnowledgePanel key={selected.id} source={selected}
                            onChanged={refresh} setError={setError} />
          )}
          {panel === "retrieval" && (
            <RetrievalPanel key={selected.id} source={selected}
                            onChanged={refresh} setError={setError} />
          )}
          {panel === "flow" && <DataFlowPanel source={selected} />}
          {panel === "versions" && (
            <VersionsPanel key={selected.id} source={selected}
                           onChanged={refresh} setError={setError} />
          )}
          {panel === "access" && (
            <AccessPanel key={selected.id} source={selected} onChanged={refresh}
                         setError={setError} />
          )}
          {panel === "test" && (
            <TestingPanel key={selected.id} source={selected}
                          setError={setError} testable={testable} />
          )}
        </div>

        <DataAgentSidebar panel={panel} setPanel={setPanel} source={selected} />
      </div>
    </div>
  );
};

export default DataAgentPage;
