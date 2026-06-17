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
  const [activeFile, setActiveFile] = useState(null);
  const [modal, setModal] = useState(null);
  const [modalData, setModalData] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [question, setQuestion] = useState("");
  const [querying, setQuerying] = useState(false);
  const fileRef = useRef(null);
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
    try {
      setFiles(await listDataFiles(s.id));
    } catch (e) {
      setError(e.message);
    }
  };
  const goBack = () => {
    setActiveSpace(null);
    setFiles([]);
    setModal(null);
    setChatHistory([]);
  };

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

  const handleDeleteSpace = async (id) => {
    if (!confirm("Delete this space and all files?")) return;
    try {
      await deleteDataSpace(id);
      goBack();
      await loadData();
    } catch (e) {
      setError(e.message);
    }
  };

  const openPreview = async (f) => {
    setModalLoading(true);
    setModal("preview");
    try {
      setModalData(await previewDataFile(activeSpace.id, f.id));
    } catch (e) {
      setError(e.message);
      setModal(null);
    } finally {
      setModalLoading(false);
    }
  };
  const openSchema = async (f) => {
    setModalLoading(true);
    setModal("schema");
    try {
      setModalData(await getFileSchema(activeSpace.id, f.id));
    } catch (e) {
      setError(e.message);
      setModal(null);
    } finally {
      setModalLoading(false);
    }
  };
  const openChat = () => {
    setModal("chat");
  };
  const closeModal = () => {
    setModal(null);
    setModalData(null);
  };

  const handleQuery = async () => {
    if (!question.trim() || !activeSpace) return;
    const q = question;
    setQuestion("");
    setChatHistory((h) => [...h, { role: "user", content: q }]);
    setQuerying(true);
    try {
      const res = await queryData(activeSpace.id, q);
      setChatHistory((h) => [
        ...h,
        {
          role: "assistant",
          content: res.answer,
          data: res.data,
          type: res.type,
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
        <div className="rag-empty-state">Loading...</div>
      </div>
    );

  // ═══ PAGE 1: Space cards ═══
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

  // ═══ PAGE 2: Inside space ═══
  return (
    <div className="rag-page" style={{ display: "block" }}>
      <div className="rag-main">
        {error && <div className="rag-toast rag-toast-error">{error}</div>}
        {success && (
          <div className="rag-toast rag-toast-success">{success}</div>
        )}

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
            <span className="rag-config-tag">{files.length} files</span>
            <button
              className="rag-btn rag-btn-blue rag-btn-sm"
              onClick={openChat}
            >
              💬 Chat
            </button>
            <button
              className="rag-btn rag-btn-sm rag-btn-red"
              onClick={() => handleDeleteSpace(activeSpace.id)}
            >
              Delete
            </button>
          </div>
        </div>

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
                    onClick={() => openPreview(f)}
                  >
                    Preview
                  </button>
                  <button
                    className="rag-btn rag-btn-xs"
                    onClick={() => openSchema(f)}
                  >
                    Schema
                  </button>
                </div>
              </div>
              <button
                className="rag-doc-del"
                style={{ opacity: 1 }}
                onClick={() => handleDeleteFile(f.id)}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* ═══ MODAL ═══ */}
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
                {modal === "chat" && "Chat with data"}
              </div>
              <button className="rag-btn rag-btn-sm" onClick={closeModal}>
                ✕ Close
              </button>
            </div>
            <div className="rag-modal-body">
              {modalLoading && <div className="rag-empty-state">Loading…</div>}

              {/* Preview */}
              {modal === "preview" && modalData && !modalLoading && (
                <div style={{ overflowX: "auto" }}>
                  <div style={{ fontSize: 13, marginBottom: 10 }}>
                    <strong>{modalData.file_name}</strong> —{" "}
                    {modalData.num_rows} rows × {modalData.num_cols} cols
                    (showing first 10)
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
                        {modalData.columns.map((c, i) => (
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
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {modalData.preview.map((row, i) => (
                        <tr
                          key={i}
                          style={{ borderBottom: "1px solid var(--border)" }}
                        >
                          {modalData.columns.map((c, j) => (
                            <td
                              key={j}
                              style={{
                                padding: "5px 10px",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {row[c] != null ? String(row[c]) : ""}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Schema */}
              {modal === "schema" && modalData && !modalLoading && (
                <div>
                  <div style={{ fontSize: 13, marginBottom: 10 }}>
                    <strong>{modalData.file_name}</strong> —{" "}
                    {modalData.num_rows} rows × {modalData.num_cols} cols
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
                          Non-null
                        </th>
                        <th
                          style={{
                            padding: "6px 10px",
                            borderBottom: "2px solid var(--border)",
                            textAlign: "right",
                          }}
                        >
                          Unique
                        </th>
                        <th
                          style={{
                            padding: "6px 10px",
                            borderBottom: "2px solid var(--border)",
                            textAlign: "right",
                          }}
                        >
                          Stats
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {modalData.columns.map((c, i) => (
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
                            {c.dtype}
                          </td>
                          <td
                            style={{ padding: "5px 10px", textAlign: "right" }}
                          >
                            {c.non_null}
                          </td>
                          <td
                            style={{ padding: "5px 10px", textAlign: "right" }}
                          >
                            {c.unique}
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
                              : c.sample_values?.join(", ") || ""}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Chat */}
              {modal === "chat" && (
                <div className="rag-chat-body">
                  <div className="rag-chat-messages">
                    {chatHistory.length === 0 && (
                      <div className="rag-empty-state" style={{ padding: 40 }}>
                        <div style={{ fontSize: 28, marginBottom: 12 }}>💬</div>
                        <div style={{ marginBottom: 8 }}>
                          Ask about your data
                        </div>
                        <div
                          style={{
                            fontSize: 12,
                            color: "var(--text-3)",
                            lineHeight: 1.8,
                          }}
                        >
                          "What is the average salary?"
                          <br />
                          "Top 5 products by revenue"
                          <br />
                          "How many rows have status = active?"
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
                        </div>
                      </div>
                    ))}
                    {querying && (
                      <div className="rag-chat-msg rag-chat-msg-ai">
                        <div className="rag-chat-typing">Querying data...</div>
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
                      placeholder="Ask about your data..."
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
