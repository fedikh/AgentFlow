import React, { useState, useEffect, useRef } from "react";
import "../../styles/it/rag.css";
import "../../styles/it/dataagent.css";
import {
  createDataSpace,
  listDataSpaces,
  deleteDataSpace,
  uploadDataFile,
  listDataFiles,
  previewDataFile,
  getFileSchema,
  queryData,
  deleteDataFile,
  connectDatabase,
  getDatabaseInfo,
  disconnectDb,
  tablePreview,
  tableSchema,
  queryDatabase,
  getFullSchema,
} from "../../services/dataAgentApi";
import { listDepartments } from "../../services/ragApi";

/* ── Data-themed line icons ── */
const IcDatabase = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
    <ellipse cx="12" cy="5" rx="8" ry="3" stroke="currentColor" strokeWidth="1.8" />
    <path d="M4 5v6c0 1.66 3.58 3 8 3s8-1.34 8-3V5" stroke="currentColor" strokeWidth="1.8" />
    <path d="M4 11v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6" stroke="currentColor" strokeWidth="1.8" />
  </svg>
);
const IcGrid = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
    <rect x="3" y="3" width="7" height="7" rx="1.4" stroke="currentColor" strokeWidth="1.7" />
    <rect x="14" y="3" width="7" height="7" rx="1.4" stroke="currentColor" strokeWidth="1.7" />
    <rect x="3" y="14" width="7" height="7" rx="1.4" stroke="currentColor" strokeWidth="1.7" />
    <rect x="14" y="14" width="7" height="7" rx="1.4" stroke="currentColor" strokeWidth="1.7" />
  </svg>
);
const IcSheet = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
    <rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" strokeWidth="1.6" />
    <path d="M3 9h18M3 15h18M9 4v16" stroke="currentColor" strokeWidth="1.4" />
  </svg>
);
const IcTable = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
    <rect x="3" y="4" width="18" height="16" rx="2.2" stroke="currentColor" strokeWidth="1.8" />
    <path d="M3 9h18M9 9v11M15 9v11" stroke="currentColor" strokeWidth="1.6" />
  </svg>
);
const IcDept = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
    <path d="M3 21V7l6-3 6 3v14M15 21V11l6 3v7M3 21h18" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const IcPlus = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
    <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
);
const IcArrow = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
    <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const IcChat = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
  </svg>
);
const IcDbSmall = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
    <ellipse cx="12" cy="5" rx="7" ry="2.6" stroke="currentColor" strokeWidth="1.7" />
    <path d="M5 5v6c0 1.5 3.1 2.6 7 2.6s7-1.1 7-2.6V5" stroke="currentColor" strokeWidth="1.7" />
    <path d="M5 11v6c0 1.5 3.1 2.6 7 2.6s7-1.1 7-2.6v-6" stroke="currentColor" strokeWidth="1.7" />
  </svg>
);

const DataAgentPage = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [depts, setDepts] = useState([]);
  const [spaces, setSpaces] = useState([]);
  const [activeSpace, setActiveSpace] = useState(null);
  const [files, setFiles] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [createDept, setCreateDept] = useState("");
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [uploading, setUploading] = useState(false);
  const [tab, setTab] = useState("files");
  const fileRef = useRef(null);

  // Database
  const [dbInfo, setDbInfo] = useState(null);
  const [dbForm, setDbForm] = useState({
    db_type: "postgresql",
    host: "localhost",
    port: "5432",
    database: "",
    username: "",
    password: "",
  });
  const [connecting, setConnecting] = useState(false);
  const [dbSchema, setDbSchema] = useState(null);

  // Modal
  const [modal, setModal] = useState(null);
  const [modalData, setModalData] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);

  // Chat
  const [chatHistory, setChatHistory] = useState([]);
  const [question, setQuestion] = useState("");
  const [querying, setQuerying] = useState(false);
  const [chatSource, setChatSource] = useState("files");
  const chatEndRef = useRef(null);

  useEffect(() => {
    loadData();
  }, []);
  useEffect(() => {
    if (success) {
      const t = setTimeout(() => setSuccess(""), 4000);
      return () => clearTimeout(t);
    }
  }, [success]);
  useEffect(() => {
    if (error) {
      const t = setTimeout(() => setError(""), 6000);
      return () => clearTimeout(t);
    }
  }, [error]);
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  const loadData = async () => {
    try {
      const [d, s] = await Promise.all([listDepartments(), listDataSpaces()]);
      const u = JSON.parse(localStorage.getItem("user") || "{}");
      const ids = u.departments?.map((x) => x.id) || [];
      setDepts(u.role === "admin" ? d : d.filter((x) => ids.includes(x.id)));
      setSpaces(s);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const openSpace = async (s) => {
    setActiveSpace(s);
    setChatHistory([]);
    setModal(null);
    setTab("files");
    setDbSchema(null);
    try {
      setFiles(await listDataFiles(s.id));
      const info = await getDatabaseInfo(s.id);
      setDbInfo(info.connected ? info : null);
    } catch (e) {
      setError(e.message);
    }
  };

  const goBack = () => {
    setActiveSpace(null);
    setFiles([]);
    setModal(null);
    setChatHistory([]);
    setDbInfo(null);
    setDbSchema(null);
  };

  // ── Space CRUD ──
  const handleCreate = async () => {
    if (!newName.trim() || !createDept) return;
    try {
      await createDataSpace({
        name: newName,
        description: newDesc,
        department_id: createDept,
      });
      setNewName("");
      setNewDesc("");
      setShowCreate(false);
      await loadData();
      setSuccess("Space created");
    } catch (e) {
      setError(e.message);
    }
  };
  const handleDeleteSpace = async (id) => {
    if (!confirm("Delete this space and all data?")) return;
    try {
      await deleteDataSpace(id);
      goBack();
      await loadData();
    } catch (e) {
      setError(e.message);
    }
  };

  // ── Files ──
  const handleUpload = async (e) => {
    const f = e.target.files[0];
    if (!f || !activeSpace) return;
    setUploading(true);
    setError("");
    try {
      await uploadDataFile(activeSpace.id, f);
      setSuccess(`"${f.name}" uploaded`);
      setFiles(await listDataFiles(activeSpace.id));
      await loadData();
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
      fileRef.current.value = "";
    }
  };
  const handleDeleteFile = async (id) => {
    try {
      await deleteDataFile(activeSpace.id, id);
      setFiles((p) => p.filter((f) => f.id !== id));
    } catch (e) {
      setError(e.message);
    }
  };

  // ── Database ──
  const handleConnect = async () => {
    if (!dbForm.database) {
      setError("Database name required");
      return;
    }
    setConnecting(true);
    setError("");
    try {
      const info = await connectDatabase(activeSpace.id, dbForm);
      setDbInfo(info);
      setSuccess(
        `Connected to ${info.database} — ${info.tables.length} tables`,
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setConnecting(false);
    }
  };
  const handleDisconnect = async () => {
    try {
      await disconnectDb(activeSpace.id);
      setDbInfo(null);
      setDbSchema(null);
      setSuccess("Disconnected");
    } catch (e) {
      setError(e.message);
    }
  };

  const handleShowFullSchema = async () => {
    setModalLoading(true);
    setModal("db-schema");
    try {
      setDbSchema(await getFullSchema(activeSpace.id));
    } catch (e) {
      setError(e.message);
      setModal(null);
    } finally {
      setModalLoading(false);
    }
  };

  // ── Modals ──
  const openPreview = async (type, name) => {
    setModalLoading(true);
    setModal("preview");
    try {
      if (type === "file")
        setModalData(await previewDataFile(activeSpace.id, name));
      else setModalData(await tablePreview(activeSpace.id, name));
    } catch (e) {
      setError(e.message);
      setModal(null);
    } finally {
      setModalLoading(false);
    }
  };
  const openSchema = async (type, name) => {
    setModalLoading(true);
    setModal("schema");
    try {
      if (type === "file")
        setModalData(await getFileSchema(activeSpace.id, name));
      else setModalData(await tableSchema(activeSpace.id, name));
    } catch (e) {
      setError(e.message);
      setModal(null);
    } finally {
      setModalLoading(false);
    }
  };
  const openChat = (source) => {
    setChatSource(source);
    setChatHistory([]);
    setTab("chat");
  };
  const closeModal = () => {
    setModal(null);
    setModalData(null);
    setDbSchema(null);
  };

  // ── Query ──
  const handleQuery = async () => {
    if (!question.trim() || !activeSpace) return;
    const q = question;
    setQuestion("");
    setChatHistory((h) => [...h, { role: "user", content: q }]);
    setQuerying(true);
    try {
      let res;
      if (chatSource === "database") {
        res = await queryDatabase(activeSpace.id, q, dbInfo?.tables);
      } else {
        res = await queryData(activeSpace.id, q);
      }
      setChatHistory((h) => [
        ...h,
        {
          role: "assistant",
          content: res.answer,
          data: res.data,
          type: res.type,
          chart: res.chart,
        },
      ]);
    } catch (e) {
      setChatHistory((h) => [
        ...h,
        { role: "assistant", content: `Error: ${e.message}`, type: "error" },
      ]);
    } finally {
      setQuerying(false);
    }
  };

  const deptName = (id) => depts.find((x) => x.id === id)?.name || "";

  if (loading)
    return (
      <div className="rag-page">
        <div className="rag-empty-state">Loading…</div>
      </div>
    );

  // ═══════════════════════════════════════
  // PAGE 1: Space cards (data / database vibe)
  // ═══════════════════════════════════════
  if (!activeSpace) {
    const hasVisible = depts.some((d) =>
      spaces.some((s) => s.department_id === d.id),
    );

    return (
      <div className="rag-page" style={{ display: "block" }}>
        <div className="rag-main">
          {error && <div className="rag-toast rag-toast-error">{error}</div>}
          {success && (
            <div className="rag-toast rag-toast-success">{success}</div>
          )}

          {/* Header */}
          <div className="da-head">
            <div>
              <h1 className="da-title">Data Agent</h1>
              <p className="da-sub">
                Query your files and databases in natural language
              </p>
            </div>
            <button className="da-new" onClick={() => setShowCreate(true)}>
              <IcPlus /> New space
            </button>
          </div>

          {/* Create modal */}
          {showCreate && (
            <div
              className="rag-create-overlay"
              onClick={(e) =>
                e.target === e.currentTarget && setShowCreate(false)
              }
            >
              <div className="rag-create-modal">
                <div className="rag-create-modal-head">
                  <span className="rag-create-title">New Data Space</span>
                  <button
                    className="rag-create-x"
                    onClick={() => setShowCreate(false)}
                  >
                    ✕
                  </button>
                </div>
                <div className="rag-create-body">
                  <label className="rag-create-label">Department</label>
                  <select
                    className="rag-create-input"
                    value={createDept}
                    onChange={(e) => setCreateDept(e.target.value)}
                  >
                    <option value="">Select a department…</option>
                    {depts.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                  <label className="rag-create-label">Name</label>
                  <input
                    className="rag-create-input"
                    placeholder="e.g. Sales Analytics"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                  />
                  <label className="rag-create-label">
                    Description (optional)
                  </label>
                  <input
                    className="rag-create-input"
                    placeholder="What data lives here?"
                    value={newDesc}
                    onChange={(e) => setNewDesc(e.target.value)}
                  />
                </div>
                <div className="rag-create-foot">
                  <button
                    className="rag-btn"
                    onClick={() => setShowCreate(false)}
                  >
                    Cancel
                  </button>
                  <button
                    className="rag-btn rag-btn-blue"
                    onClick={handleCreate}
                    disabled={!newName.trim() || !createDept}
                  >
                    Create space
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Grid / empty */}
          {!hasVisible ? (
            <div className="da-empty">
              <span className="da-empty-ic">
                <IcDatabase />
              </span>
              <div className="da-empty-title">No data spaces yet</div>
              <div className="da-empty-sub">
                Create a space to upload CSV / Excel files or connect a database,
                then query it in natural language.
              </div>
              <button className="da-new" onClick={() => setShowCreate(true)}>
                <IcPlus /> New space
              </button>
            </div>
          ) : (
            depts.map((dept) => {
              const ds = spaces.filter((s) => s.department_id === dept.id);
              if (!ds.length) return null;
              return (
                <section key={dept.id} className="da-section">
                  <div className="da-section-head">
                    <span className="da-section-name">{dept.name}</span>
                    <span className="da-section-count">{ds.length}</span>
                    <span className="da-section-rule" />
                  </div>
                  <div className="da-grid">
                    {ds.map((s) => (
                      <button
                        key={s.id}
                        className="da-card"
                        onClick={() => openSpace(s)}
                      >
                        <div className="da-card-head">
                          <span className="da-mono">
                            {(s.name || "?").trim().charAt(0).toUpperCase() ||
                              "?"}
                          </span>
                          <div className="da-card-titles">
                            <div className="da-card-name">{s.name}</div>
                          </div>
                          <span className="da-card-badge">DATA</span>
                        </div>
                        <div className="da-card-desc">
                          {s.description || "No description"}
                        </div>
                        <div className="da-card-foot">
                          <span className="da-card-stat">
                            <IcSheet /> {s.num_files || 0} file
                            {(s.num_files || 0) !== 1 ? "s" : ""}
                          </span>
                          <span className="da-card-open">
                            <IcArrow />
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                </section>
              );
            })
          )}
        </div>
      </div>
    );
  }

  // ═══════════════════════════════════════
  // PAGE 2: Inside space
  // ═══════════════════════════════════════
  return (
    <div className="rag-page">
      <div className="rag-space-layout">
        <div className="rag-space-content">
        {error && <div className="rag-toast rag-toast-error">{error}</div>}
        {success && (
          <div className="rag-toast rag-toast-success">{success}</div>
        )}

        {/* Header */}
        <div className="rag-header">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button className="rag-btn rag-btn-sm" onClick={goBack}>
              ← Back
            </button>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div className="rag-header-title">{activeSpace.name}</div>
                <span className="da-pill">Data</span>
              </div>
              <div className="rag-header-desc">
                {deptName(activeSpace.department_id)}
              </div>
            </div>
          </div>
          <div className="rag-header-actions">
            <button
              className="rag-btn rag-btn-sm rag-btn-red"
              onClick={() => handleDeleteSpace(activeSpace.id)}
            >
              Delete
            </button>
          </div>
        </div>

        {/* ═══ FILES PANEL ═══ */}
        {tab === "files" && (
          <div className="da-panel">
            <div className="da-panel-head">
              <div className="da-panel-title">
                <span className="da-panel-ic">
                  <IcSheet />
                </span>
                <div>
                  <div className="da-panel-t">Files</div>
                  <div className="da-panel-sub">
                    CSV &amp; Excel spreadsheets you can query
                  </div>
                </div>
              </div>
              {files.length > 0 && (
                <button className="da-new" onClick={() => openChat("files")}>
                  <IcChat /> Ask files
                </button>
              )}
            </div>

            <input
              type="file"
              ref={fileRef}
              onChange={handleUpload}
              style={{ display: "none" }}
              accept=".csv,.xlsx,.xls"
            />
            <div
              className="da-upload"
              style={{ cursor: uploading ? "default" : "pointer" }}
              onClick={() => !uploading && fileRef.current.click()}
            >
              <div className="da-upload-ic">
                <IcSheet />
              </div>
              <div className="da-upload-t">
                {uploading ? "Uploading…" : "Upload CSV / Excel"}
              </div>
              <div className="da-upload-s">
                Add a .csv or .xlsx file to this space
              </div>
              <button
                className="rag-btn rag-btn-blue rag-btn-sm"
                disabled={uploading}
              >
                Choose file
              </button>
            </div>

            <div className="rag-docs-list">
              {files.length === 0 && (
                <div className="rag-empty-state">
                  No files yet — upload a CSV or Excel file above.
                </div>
              )}
              {files.map((f) => (
                <div key={f.id} className="da-doc">
                  <div className="da-doc-ic">
                    {(f.file_type || "?").toUpperCase()}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="da-doc-name">{f.file_name}</div>
                    <div className="da-doc-meta">
                      {f.num_rows} rows × {f.num_cols} cols ·{" "}
                      {(f.file_size / 1024).toFixed(1)} KB
                    </div>
                    <div className="da-doc-btns">
                      <button
                        className="rag-btn rag-btn-xs"
                        onClick={() => openPreview("file", f.id)}
                      >
                        Preview
                      </button>
                      <button
                        className="rag-btn rag-btn-xs"
                        onClick={() => openSchema("file", f.id)}
                      >
                        Schema
                      </button>
                    </div>
                  </div>
                  <button
                    className="da-doc-del"
                    onClick={() => handleDeleteFile(f.id)}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ═══ DATABASE TAB ═══ */}
        {tab === "database" && (
          <>
            {!dbInfo ? (
              <div className="da-panel" style={{ maxWidth: 520 }}>
                <div className="da-panel-head" style={{ marginBottom: 14 }}>
                  <div className="da-panel-title">
                    <span className="da-panel-ic">
                      <IcDbSmall />
                    </span>
                    <div>
                      <div className="da-panel-t">Connect a database</div>
                      <div className="da-panel-sub">
                        Query your tables in natural language
                      </div>
                    </div>
                  </div>
                </div>
                <div className="rag-create-label">Database Type</div>
                <select
                  className="rag-create-input"
                  value={dbForm.db_type}
                  onChange={(e) =>
                    setDbForm({ ...dbForm, db_type: e.target.value })
                  }
                >
                  <option value="postgresql">PostgreSQL</option>
                  <option value="sqlite">SQLite</option>
                  <option value="mysql">MySQL</option>
                </select>
                {dbForm.db_type !== "sqlite" && (
                  <>
                    <div className="rag-create-label">Host</div>
                    <input
                      className="rag-create-input"
                      value={dbForm.host}
                      onChange={(e) =>
                        setDbForm({ ...dbForm, host: e.target.value })
                      }
                      placeholder="localhost"
                    />
                    <div className="rag-create-label">Port</div>
                    <input
                      className="rag-create-input"
                      value={dbForm.port}
                      onChange={(e) =>
                        setDbForm({ ...dbForm, port: e.target.value })
                      }
                      placeholder="5432"
                    />
                    <div className="rag-create-label">Username</div>
                    <input
                      className="rag-create-input"
                      value={dbForm.username}
                      onChange={(e) =>
                        setDbForm({ ...dbForm, username: e.target.value })
                      }
                      placeholder="postgres"
                    />
                    <div className="rag-create-label">Password</div>
                    <input
                      className="rag-create-input"
                      type="password"
                      value={dbForm.password}
                      onChange={(e) =>
                        setDbForm({ ...dbForm, password: e.target.value })
                      }
                      placeholder="••••••"
                    />
                  </>
                )}
                <div className="rag-create-label">
                  Database Name{dbForm.db_type === "sqlite" && " (file path)"}
                </div>
                <input
                  className="rag-create-input"
                  value={dbForm.database}
                  onChange={(e) =>
                    setDbForm({ ...dbForm, database: e.target.value })
                  }
                  placeholder={
                    dbForm.db_type === "sqlite"
                      ? "/path/to/database.db"
                      : "my_database"
                  }
                />
                <button
                  className="rag-btn rag-btn-blue"
                  onClick={handleConnect}
                  disabled={connecting}
                  style={{ width: "100%", marginTop: 8 }}
                >
                  {connecting ? "Connecting…" : "Connect"}
                </button>
              </div>
            ) : (
              <>
                {/* Connected banner */}
                <div className="da-conn">
                  <div className="da-conn-left">
                    <span className="da-conn-dot" />
                    <div>
                      <div className="da-conn-str">
                        {dbInfo.db_type}://{dbInfo.host}:{dbInfo.port}/
                        {dbInfo.database}
                      </div>
                      <div className="da-conn-sub">
                        {dbInfo.tables?.length || 0} table
                        {(dbInfo.tables?.length || 0) !== 1 ? "s" : ""}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    <button
                      className="rag-btn rag-btn-sm"
                      onClick={handleShowFullSchema}
                    >
                      Schema &amp; Relations
                    </button>
                    <button className="da-new" onClick={() => openChat("database")}>
                      <IcChat /> Ask database
                    </button>
                    <button
                      className="rag-btn rag-btn-sm rag-btn-red"
                      onClick={handleDisconnect}
                    >
                      Disconnect
                    </button>
                  </div>
                </div>

                {/* Table list */}
                <div className="rag-docs-list">
                  {dbInfo.tables?.map((t) => (
                    <div key={t} className="da-doc">
                      <div className="da-doc-ic">
                        <IcTable />
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="da-doc-name">{t}</div>
                        <div className="da-doc-btns">
                          <button
                            className="rag-btn rag-btn-xs"
                            onClick={() => openPreview("table", t)}
                          >
                            Preview
                          </button>
                          <button
                            className="rag-btn rag-btn-xs"
                            onClick={() => openSchema("table", t)}
                          >
                            Schema
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </>
        )}

        {/* ═══ CHAT PANEL ═══ */}
        {tab === "chat" && (
          <div className="da-panel">
            <div className="da-panel-head">
              <div className="da-panel-title">
                <span className="da-panel-ic">
                  <IcChat />
                </span>
                <div>
                  <div className="da-panel-t">Ask your data</div>
                  <div className="da-panel-sub">
                    Natural-language questions with instant tables &amp; charts
                  </div>
                </div>
              </div>
            </div>

            <div className="da-chat-src">
              <button
                className={chatSource === "files" ? "on" : ""}
                onClick={() => {
                  setChatSource("files");
                  setChatHistory([]);
                }}
              >
                <IcSheet /> Files
              </button>
              <button
                className={chatSource === "database" ? "on" : ""}
                disabled={!dbInfo}
                title={!dbInfo ? "Connect a database first" : undefined}
                onClick={() => {
                  setChatSource("database");
                  setChatHistory([]);
                }}
              >
                <IcDbSmall /> Database
              </button>
            </div>

            <div className="da-chat">
              <div className="rag-chat-messages" style={{ flex: 1 }}>
                {chatHistory.length === 0 && (
                  <div className="rag-empty-state" style={{ padding: 40 }}>
                    <div style={{ fontSize: 28, marginBottom: 12 }}>
                      {chatSource === "database" ? "🗄️" : "📊"}
                    </div>
                    <div style={{ marginBottom: 8 }}>
                      Ask about your{" "}
                      {chatSource === "database" ? "database" : "files"}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: "var(--text-3)",
                        lineHeight: 1.8,
                      }}
                    >
                      {chatSource === "database" ? (
                        <>
                          "How many users are there?"
                          <br />
                          "Show top 5 orders by total"
                          <br />
                          "Which tables have a date column?"
                        </>
                      ) : (
                        <>
                          "What is the average salary?"
                          <br />
                          "Top 5 products by revenue"
                          <br />
                          "How many rows have status = active?"
                        </>
                      )}
                    </div>
                  </div>
                )}
                {chatHistory.map((m, i) => (
                  <div
                    key={i}
                    className={`rag-chat-msg ${m.role === "user" ? "rag-chat-msg-user" : "rag-chat-msg-ai"}`}
                  >
                    <div
                      className={`rag-chat-bubble ${m.role === "user" ? "rag-chat-bubble-user" : "rag-chat-bubble-ai"}`}
                    >
                      <div>{m.content}</div>
                      {m.chart && (
                        <div style={{ marginTop: 10 }}>
                          <img
                            src={`data:image/png;base64,${m.chart}`}
                            alt="Chart"
                            style={{
                              maxWidth: "100%",
                              borderRadius: 8,
                              border: "1px solid var(--border)",
                            }}
                          />
                        </div>
                      )}
                      {m.data && m.type === "dataframe" && (
                        <div style={{ marginTop: 10, overflowX: "auto" }}>
                          <table
                            style={{
                              width: "100%",
                              borderCollapse: "collapse",
                              fontSize: 12,
                            }}
                          >
                            <thead>
                              <tr>
                                {Object.keys(m.data[0] || {}).map((k, j) => (
                                  <th
                                    key={j}
                                    style={{
                                      padding: "4px 8px",
                                      borderBottom: "2px solid var(--border)",
                                      textAlign: "left",
                                      fontWeight: 600,
                                    }}
                                  >
                                    {k}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {m.data.map((row, ri) => (
                                <tr
                                  key={ri}
                                  style={{
                                    borderBottom: "1px solid var(--border)",
                                  }}
                                >
                                  {Object.values(row).map((v, vi) => (
                                    <td key={vi} style={{ padding: "3px 8px" }}>
                                      {v != null ? String(v) : ""}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {querying && (
                  <div className="rag-chat-msg rag-chat-msg-ai">
                    <div className="rag-chat-typing">
                      Querying {chatSource}…
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
              <div className="rag-chat-input-bar">
                <input
                  className="rag-chat-input"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleQuery()}
                  placeholder={`Ask about your ${chatSource}…`}
                />
                <button
                  className="rag-chat-send"
                  onClick={handleQuery}
                  disabled={querying || !question.trim()}
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        )}
        </div>

        {/* Data-themed right sidebar */}
        <aside className="rag-side da-side">
          <button
            className={`da-side-btn ${tab === "chat" ? "active" : ""}`}
            onClick={() => setTab("chat")}
          >
            <IcChat /> Ask data
          </button>
          <div className="rag-side-label">Sources</div>
          <button
            className={`da-side-item ${tab === "files" ? "active" : ""}`}
            onClick={() => setTab("files")}
          >
            <IcSheet /> Files
            <span className="da-side-count">{files.length}</span>
          </button>
          <button
            className={`da-side-item ${tab === "database" ? "active" : ""}`}
            onClick={() => setTab("database")}
          >
            <IcDbSmall /> Database
            {dbInfo && <span className="da-side-dot" />}
          </button>
        </aside>
      </div>

      {/* ═══════════════════════════════════════
           MODAL
         ═══════════════════════════════════════ */}
      {modal && (
        <div
          className="rag-modal-overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeModal();
          }}
        >
          <div className="rag-modal">
            <div className="rag-modal-header">
              <div className="rag-modal-title">
                {modal === "preview" && "Data Preview"}
                {modal === "schema" && "Schema"}
                {modal === "db-schema" && "Database Schema & Relations"}
              </div>
              <button className="rag-btn rag-btn-sm" onClick={closeModal}>
                ✕ Close
              </button>
            </div>
            <div className="rag-modal-body">
              {modalLoading && <div className="rag-empty-state">Loading…</div>}

              {/* ── PREVIEW ── */}
              {modal === "preview" && modalData && !modalLoading && (
                <div style={{ overflowX: "auto" }}>
                  <div style={{ fontSize: 13, marginBottom: 10 }}>
                    <strong>
                      {modalData.file_name || modalData.table_name}
                    </strong>{" "}
                    — {modalData.num_rows} rows × {modalData.num_cols} cols
                  </div>
                  <table
                    style={{
                      width: "100%",
                      borderCollapse: "collapse",
                      fontSize: 12,
                    }}
                  >
                    <thead>
                      <tr>
                        {modalData.columns?.map((c, i) => (
                          <th
                            key={i}
                            style={{
                              padding: "6px 10px",
                              borderBottom: "2px solid var(--border)",
                              textAlign: "left",
                              fontWeight: 600,
                              whiteSpace: "nowrap",
                            }}
                          >
                            {typeof c === "object" ? c.name : c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {modalData.preview?.map((row, i) => (
                        <tr
                          key={i}
                          style={{ borderBottom: "1px solid var(--border)" }}
                        >
                          {(modalData.columns || []).map((c, j) => {
                            const key = typeof c === "object" ? c.name : c;
                            return (
                              <td
                                key={j}
                                style={{
                                  padding: "5px 10px",
                                  whiteSpace: "nowrap",
                                }}
                              >
                                {row[key] != null ? String(row[key]) : ""}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* ── SCHEMA ── */}
              {modal === "schema" && modalData && !modalLoading && (
                <div>
                  <div style={{ fontSize: 13, marginBottom: 10 }}>
                    <strong>
                      {modalData.file_name || modalData.table_name}
                    </strong>{" "}
                    — {modalData.num_rows} rows × {modalData.num_cols} cols
                  </div>
                  <table
                    style={{
                      width: "100%",
                      borderCollapse: "collapse",
                      fontSize: 12,
                    }}
                  >
                    <thead>
                      <tr>
                        <th
                          style={{
                            padding: "6px 10px",
                            borderBottom: "2px solid var(--border)",
                            textAlign: "left",
                          }}
                        >
                          Column
                        </th>
                        <th
                          style={{
                            padding: "6px 10px",
                            borderBottom: "2px solid var(--border)",
                            textAlign: "left",
                          }}
                        >
                          Type
                        </th>
                        <th
                          style={{
                            padding: "6px 10px",
                            borderBottom: "2px solid var(--border)",
                            textAlign: "right",
                          }}
                        >
                          Info
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {modalData.columns?.map((c, i) => (
                        <tr
                          key={i}
                          style={{ borderBottom: "1px solid var(--border)" }}
                        >
                          <td style={{ padding: "5px 10px", fontWeight: 500 }}>
                            {c.name}
                          </td>
                          <td
                            style={{
                              padding: "5px 10px",
                              color: "var(--text-3)",
                            }}
                          >
                            {c.dtype || c.type}
                          </td>
                          <td
                            style={{
                              padding: "5px 10px",
                              textAlign: "right",
                              color: "var(--text-3)",
                            }}
                          >
                            {c.min != null
                              ? `${c.min} / ${c.max} / ${c.mean}`
                              : c.sample_values?.join(", ") ||
                                (c.nullable ? "nullable" : "not null")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* ── DATABASE FULL SCHEMA ── */}
              {modal === "db-schema" && dbSchema && !modalLoading && (
                <div>
                  <div style={{ fontSize: 13, marginBottom: 16 }}>
                    <strong>{dbSchema.database}</strong> ({dbSchema.db_type}) —{" "}
                    {dbSchema.total_tables} tables,{" "}
                    {dbSchema.total_relationships} relationships
                  </div>

                  {dbSchema.tables.map((t) => (
                    <div
                      key={t.name}
                      className="rag-block"
                      style={{ marginBottom: 12 }}
                    >
                      <div className="rag-block-header">
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                          }}
                        >
                          <span className="rag-block-tag">🗄️ {t.name}</span>
                          <span
                            style={{ fontSize: 11, color: "var(--text-3)" }}
                          >
                            {t.row_count} rows
                          </span>
                        </div>
                      </div>
                      <table
                        style={{
                          width: "100%",
                          borderCollapse: "collapse",
                          fontSize: 12,
                          marginTop: 8,
                        }}
                      >
                        <thead>
                          <tr>
                            <th
                              style={{
                                padding: "4px 8px",
                                borderBottom: "1px solid var(--border)",
                                textAlign: "left",
                              }}
                            >
                              Column
                            </th>
                            <th
                              style={{
                                padding: "4px 8px",
                                borderBottom: "1px solid var(--border)",
                                textAlign: "left",
                              }}
                            >
                              Type
                            </th>
                            <th
                              style={{
                                padding: "4px 8px",
                                borderBottom: "1px solid var(--border)",
                                textAlign: "center",
                              }}
                            >
                              PK
                            </th>
                            <th
                              style={{
                                padding: "4px 8px",
                                borderBottom: "1px solid var(--border)",
                                textAlign: "center",
                              }}
                            >
                              Nullable
                            </th>
                            <th
                              style={{
                                padding: "4px 8px",
                                borderBottom: "1px solid var(--border)",
                                textAlign: "left",
                              }}
                            >
                              FK →
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {t.columns.map((c) => {
                            const fk = dbSchema.relationships.find(
                              (r) =>
                                r.from_table === t.name &&
                                r.from_column === c.name,
                            );
                            return (
                              <tr
                                key={c.name}
                                style={{
                                  borderBottom: "1px solid var(--border)",
                                }}
                              >
                                <td
                                  style={{
                                    padding: "3px 8px",
                                    fontWeight: c.primary_key ? 600 : 400,
                                  }}
                                >
                                  {c.primary_key ? "🔑 " : ""}
                                  {c.name}
                                </td>
                                <td
                                  style={{
                                    padding: "3px 8px",
                                    color: "var(--text-3)",
                                  }}
                                >
                                  {c.type}
                                </td>
                                <td
                                  style={{
                                    padding: "3px 8px",
                                    textAlign: "center",
                                  }}
                                >
                                  {c.primary_key ? "✓" : ""}
                                </td>
                                <td
                                  style={{
                                    padding: "3px 8px",
                                    textAlign: "center",
                                  }}
                                >
                                  {c.nullable ? "✓" : ""}
                                </td>
                                <td
                                  style={{
                                    padding: "3px 8px",
                                    color: "var(--blue)",
                                  }}
                                >
                                  {fk ? `→ ${fk.to_table}.${fk.to_column}` : ""}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ))}

                  {dbSchema.relationships.length > 0 && (
                    <div style={{ marginTop: 20 }}>
                      <div
                        style={{
                          fontSize: 14,
                          fontWeight: 600,
                          marginBottom: 10,
                        }}
                      >
                        Relationships
                      </div>
                      {dbSchema.relationships.map((r, i) => (
                        <div
                          key={i}
                          style={{
                            fontSize: 12,
                            padding: "6px 0",
                            borderBottom: "1px solid var(--border)",
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                          }}
                        >
                          <span style={{ fontWeight: 500 }}>
                            {r.from_table}
                          </span>
                          <span style={{ color: "var(--text-3)" }}>
                            .{r.from_column}
                          </span>
                          <span style={{ color: "var(--blue)" }}>→</span>
                          <span style={{ fontWeight: 500 }}>{r.to_table}</span>
                          <span style={{ color: "var(--text-3)" }}>
                            .{r.to_column}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DataAgentPage;
