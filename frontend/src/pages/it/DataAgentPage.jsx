import React, { useState, useEffect, useRef } from "react";
import "../../styles/it/rag.css";
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
    setModal("chat");
    setChatHistory([]);
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
      (h) => [
        ...h,
        {
          role: "assistant",
          content: res.answer,
          data: res.data,
          type: res.type,
          chart: res.chart,
        },
      ];
    } catch (e) {
      setChatHistory((h) => [
        ...h,
        { role: "assistant", content: `Error: ${e.message}`, type: "error" },
      ]);
    } finally {
      setQuerying(setChatHistoryfalse);
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
  // PAGE 1: Space cards
  // ═══════════════════════════════════════
  if (!activeSpace)
    return (
      <div className="rag-page" style={{ display: "block" }}>
        <div className="rag-main">
          {error && <div className="rag-toast rag-toast-error">{error}</div>}
          {success && (
            <div className="rag-toast rag-toast-success">{success}</div>
          )}
          <div className="rag-header">
            <div>
              <div className="rag-header-title">Data Agent</div>
              <div className="rag-header-desc">
                Query structured data with natural language
              </div>
            </div>
            <button
              className="rag-btn rag-btn-blue"
              onClick={() => setShowCreate(true)}
            >
              + New Space
            </button>
          </div>

          {showCreate && (
            <div className="rag-create-card" style={{ maxWidth: 400 }}>
              <div className="rag-create-title">New Data Space</div>
              <div className="rag-create-label">Department</div>
              <select
                className="rag-create-input"
                value={createDept}
                onChange={(e) => setCreateDept(e.target.value)}
              >
                <option value="">Select…</option>
                {depts.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
              <input
                className="rag-create-input"
                placeholder="Space name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
              <input
                className="rag-create-input"
                placeholder="Description"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
              />
              <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                <button className="rag-btn rag-btn-blue" onClick={handleCreate}>
                  Create
                </button>
                <button
                  className="rag-btn"
                  onClick={() => setShowCreate(false)}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div className="rag-grid">
            {depts.map((dept) => {
              const ds = spaces.filter((s) => s.department_id === dept.id);
              if (!ds.length) return null;
              return (
                <div key={dept.id} className="rag-dept-section">
                  <div className="rag-dept-label">{dept.name}</div>
                  <div className="rag-cards">
                    {ds.map((s) => (
                      <div
                        key={s.id}
                        className="rag-space-card"
                        onClick={() => openSpace(s)}
                      >
                        <div className="rag-space-card-badge">DATA</div>
                        <div className="rag-space-card-name">{s.name}</div>
                        <div className="rag-space-card-desc">
                          {s.description || "No description"}
                        </div>
                        <div className="rag-space-card-footer">
                          <span>📊 {s.num_files || 0} files</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
            {spaces.length === 0 && !showCreate && (
              <div className="rag-empty-state">
                No data spaces yet. Create one to get started.
              </div>
            )}
          </div>
        </div>
      </div>
    );

  // ═══════════════════════════════════════
  // PAGE 2: Inside space
  // ═══════════════════════════════════════
  return (
    <div className="rag-page" style={{ display: "block" }}>
      <div className="rag-main">
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
              <div className="rag-header-title">{activeSpace.name}</div>
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

        {/* Tab switcher */}
        <div
          style={{
            display: "flex",
            gap: 4,
            marginBottom: 16,
            background: "var(--bg-2)",
            padding: 4,
            borderRadius: 10,
            width: "fit-content",
          }}
        >
          <button
            onClick={() => setTab("files")}
            style={{
              padding: "8px 20px",
              borderRadius: 8,
              border: "none",
              cursor: "pointer",
              fontWeight: 500,
              fontSize: 13,
              background: tab === "files" ? "var(--card)" : "transparent",
              color: tab === "files" ? "var(--text)" : "var(--text-3)",
              boxShadow: tab === "files" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
            }}
          >
            📊 Files
          </button>
          <button
            onClick={() => setTab("database")}
            style={{
              padding: "8px 20px",
              borderRadius: 8,
              border: "none",
              cursor: "pointer",
              fontWeight: 500,
              fontSize: 13,
              background: tab === "database" ? "var(--card)" : "transparent",
              color: tab === "database" ? "var(--text)" : "var(--text-3)",
              boxShadow:
                tab === "database" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
            }}
          >
            🗄️ Database
          </button>
        </div>

        {/* ═══ FILES TAB ═══ */}
        {tab === "files" && (
          <>
            <div className="rag-upload-bar">
              <input
                type="file"
                ref={fileRef}
                onChange={handleUpload}
                style={{ display: "none" }}
                accept=".csv,.xlsx,.xls"
              />
              <button
                className="rag-btn rag-btn-dark"
                onClick={() => fileRef.current.click()}
                disabled={uploading}
              >
                {uploading ? "Uploading…" : "📊 Upload CSV / Excel"}
              </button>
              {files.length > 0 && (
                <button
                  className="rag-btn rag-btn-blue rag-btn-sm"
                  onClick={() => openChat("files")}
                >
                  💬 Chat with files
                </button>
              )}
            </div>
            <div className="rag-docs-list">
              {files.length === 0 && (
                <div className="rag-empty-state">
                  No files yet. Upload a CSV or Excel file.
                </div>
              )}
              {files.map((f) => (
                <div key={f.id} className="rag-doc-card">
                  <div className="rag-doc-icon">{f.file_type}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="rag-doc-name">{f.file_name}</div>
                    <div className="rag-doc-meta">
                      {f.num_rows} rows × {f.num_cols} cols ·{" "}
                      {(f.file_size / 1024).toFixed(1)} KB
                    </div>
                    <div className="rag-doc-btns">
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
                    className="rag-doc-del"
                    onClick={() => handleDeleteFile(f.id)}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </>
        )}

        {/* ═══ DATABASE TAB ═══ */}
        {tab === "database" && (
          <>
            {!dbInfo ? (
              <div
                style={{
                  background: "var(--card)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  padding: 24,
                  maxWidth: 500,
                }}
              >
                <div
                  style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}
                >
                  Connect to Database
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
                {/* Connected header */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: 16,
                  }}
                >
                  <div
                    style={{ display: "flex", alignItems: "center", gap: 12 }}
                  >
                    <div
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: "50%",
                        background: "#22C55E",
                      }}
                    />
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>
                        {dbInfo.db_type}://{dbInfo.host}:{dbInfo.port}/
                        {dbInfo.database}
                      </div>
                      <div style={{ fontSize: 12, color: "var(--text-3)" }}>
                        {dbInfo.tables?.length || 0} tables
                      </div>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      className="rag-btn rag-btn-sm"
                      onClick={handleShowFullSchema}
                    >
                      📋 Schema & Relations
                    </button>
                    <button
                      className="rag-btn rag-btn-blue rag-btn-sm"
                      onClick={() => openChat("database")}
                    >
                      💬 Chat with database
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
                    <div key={t} className="rag-doc-card">
                      <div className="rag-doc-icon">TBL</div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="rag-doc-name">{t}</div>
                        <div className="rag-doc-btns">
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
                {modal === "chat" && `Chat with ${chatSource}`}
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

              {/* ── CHAT ── */}
              {modal === "chat" && (
                <div className="rag-chat-body">
                  <div className="rag-chat-messages">
                    {chatHistory.length === 0 && (
                      <div className="rag-empty-state" style={{ padding: 40 }}>
                        <div style={{ fontSize: 28, marginBottom: 12 }}>
                          {chatSource === "database" ? "🗄️" : "💬"}
                        </div>
                        <div style={{ marginBottom: 8 }}>
                          Ask about your{" "}
                          {chatSource === "database" ? "database" : "data"}
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
                                    {Object.keys(m.data[0] || {}).map(
                                      (k, j) => (
                                        <th
                                          key={j}
                                          style={{
                                            padding: "4px 8px",
                                            borderBottom:
                                              "2px solid var(--border)",
                                            textAlign: "left",
                                            fontWeight: 600,
                                          }}
                                        >
                                          {k}
                                        </th>
                                      ),
                                    )}
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
                                        <td
                                          key={vi}
                                          style={{ padding: "3px 8px" }}
                                        >
                                          {v != null ? String(v) : ""}
                                        </td>
                                      ))}
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}
                          {m.chart && m.type === "chart" && (
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
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DataAgentPage;
