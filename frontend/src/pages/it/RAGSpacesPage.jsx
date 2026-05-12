import React, { useState, useEffect, useRef } from "react";
import {
  listSpaces,
  createSpace,
  deleteSpace,
  listDocuments,
  uploadDocument,
  deleteDocument,
  queryRAG,
} from "../../services/ragApi";
import { listDepartments } from "../../services/usersApi";
import "../../styles/it/rag.css";

const RAGSpacesPage = () => {
  const [spaces, setSpaces] = useState([]);
  const [selected, setSelected] = useState(null);
  const [docs, setDocs] = useState([]);
  const [depts, setDepts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Create modal
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newDeptId, setNewDeptId] = useState("");

  // Upload
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  // Chat
  const [question, setQuestion] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [querying, setQuerying] = useState(false);

  useEffect(() => {
    loadSpaces();
    loadDepts();
  }, []);

  const loadSpaces = async () => {
    setLoading(true);
    try {
      const data = await listSpaces();
      setSpaces(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const loadDepts = async () => {
    try {
      const data = await listDepartments();
      setDepts(data);
    } catch (e) {
      console.error("Failed to load departments:", e);
    }
  };

  const selectSpace = async (space) => {
    setSelected(space);
    setChatHistory([]);
    try {
      const data = await listDocuments(space.id);
      setDocs(data);
    } catch (e) {
      setError(e.message);
    }
  };

  // Format markdown
  const formatAnswer = (text) => {
    if (!text) return "";
    return text
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/^## (.+)$/gm, '<div class="rag-md-h2">$1</div>')
      .replace(/^### (.+)$/gm, '<div class="rag-md-h3">$1</div>')
      .replace(/^[•\-\*] (.+)$/gm, '<div class="rag-md-li">$1</div>')
      .replace(
        /^(\d+)\. (.+)$/gm,
        '<div class="rag-md-li"><span class="rag-md-num">$1.</span> $2</div>',
      )
      .replace(/\n/g, "<br>");
  };

  // ── Create space with department ──
  const handleCreate = async () => {
    if (!newName.trim() || !newDeptId) return;
    setLoading(true);
    try {
      await createSpace({
        name: newName,
        description: newDesc,
        department_id: newDeptId,
      });
      setNewName("");
      setNewDesc("");
      setNewDeptId("");
      setShowCreate(false);
      await loadSpaces();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSpace = async (id) => {
    if (!confirm("Delete this RAG space and all its documents?")) return;
    try {
      await deleteSpace(id);
      if (selected?.id === id) {
        setSelected(null);
        setDocs([]);
      }
      await loadSpaces();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || !selected) return;
    setUploading(true);
    setError("");
    try {
      await uploadDocument(selected.id, file);
      const data = await listDocuments(selected.id);
      setDocs(data);
      await loadSpaces();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      fileRef.current.value = "";
    }
  };

  const handleDeleteDoc = async (docId) => {
    try {
      await deleteDocument(selected.id, docId);
      setDocs(docs.filter((d) => d.id !== docId));
    } catch (e) {
      setError(e.message);
    }
  };

  const handleQuery = async () => {
    if (!question.trim() || !selected) return;
    const q = question;
    setQuestion("");
    setChatHistory((prev) => [...prev, { role: "user", content: q }]);
    setQuerying(true);
    try {
      const res = await queryRAG(selected.id, q);
      setChatHistory((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, sources: res.sources },
      ]);
    } catch (e) {
      setChatHistory((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${e.message}` },
      ]);
    } finally {
      setQuerying(false);
    }
  };

  return (
    <div className="rag-page">
      <h1 className="rag-title">RAG Spaces</h1>
      <p className="rag-sub">
        Build and configure RAG pipelines for your departments
      </p>

      {error && (
        <div className="rag-error">
          {error}{" "}
          <span
            onClick={() => setError("")}
            style={{ cursor: "pointer", marginLeft: 8 }}
          >
            x
          </span>
        </div>
      )}

      <div className="rag-layout">
        {/* ── Left: spaces list ── */}
        <div className="rag-sidebar">
          <div className="rag-sidebar-header">
            <span className="rag-sidebar-title">Spaces</span>
            <button className="rag-btn-sm" onClick={() => setShowCreate(true)}>
              + New
            </button>
          </div>

          {spaces.length === 0 && <p className="rag-empty">No spaces yet</p>}

          {spaces.map((s) => (
            <div
              key={s.id}
              className={`rag-space-item ${selected?.id === s.id ? "active" : ""}`}
              onClick={() => selectSpace(s)}
            >
              <div className="rag-space-name">{s.name}</div>
              <div className="rag-space-meta">
                {s.num_documents} doc(s)
                {s.department_name && (
                  <span
                    style={{
                      marginLeft: 6,
                      fontSize: 10,
                      fontWeight: 500,
                      padding: "1px 5px",
                      borderRadius: 4,
                      background: "#EFF6FF",
                      color: "#1D4ED8",
                      border: "1px solid #BFDBFE",
                    }}
                  >
                    {s.department_name}
                  </span>
                )}
              </div>
              <button
                className="rag-space-del"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteSpace(s.id);
                }}
              >
                x
              </button>
            </div>
          ))}
        </div>

        {/* ── Right: detail + chat ── */}
        <div className="rag-main">
          {!selected ? (
            <div className="rag-placeholder">
              <p>Select a RAG space or create a new one</p>
            </div>
          ) : (
            <>
              {/* Header */}
              <div className="rag-detail-header">
                <div>
                  <h2 className="rag-detail-title">{selected.name}</h2>
                  <p className="rag-detail-desc">
                    {selected.description || "No description"}
                    {selected.department_name && (
                      <span
                        style={{
                          marginLeft: 8,
                          fontSize: 11,
                          fontWeight: 500,
                          padding: "2px 8px",
                          borderRadius: 4,
                          background: "#EFF6FF",
                          color: "#1D4ED8",
                          border: "1px solid #BFDBFE",
                        }}
                      >
                        {selected.department_name}
                      </span>
                    )}
                  </p>
                </div>
                <div className="rag-config-pills">
                  <span className="rag-pill">
                    Chunks: {selected.chunk_size}
                  </span>
                  <span className="rag-pill">Top-K: {selected.top_k}</span>
                  <span className="rag-pill">{selected.chunk_strategy}</span>
                </div>
              </div>

              {/* Documents */}
              <div className="rag-section">
                <div className="rag-section-header">
                  <span className="rag-section-title">
                    Documents ({docs.length})
                  </span>
                  <button
                    className="rag-btn-sm"
                    onClick={() => fileRef.current.click()}
                    disabled={uploading}
                  >
                    {uploading ? "Uploading..." : "Upload PDF"}
                  </button>
                  <input
                    type="file"
                    ref={fileRef}
                    accept=".pdf"
                    onChange={handleUpload}
                    style={{ display: "none" }}
                  />
                </div>

                {docs.length === 0 && (
                  <p className="rag-empty">No documents uploaded yet</p>
                )}

                {docs.map((d) => (
                  <div key={d.id} className="rag-doc-item">
                    <div className="rag-doc-icon">PDF</div>
                    <div className="rag-doc-info">
                      <div className="rag-doc-name">{d.file_name}</div>
                      <div className="rag-doc-meta">
                        {d.num_chunks} chunks — {d.status}
                      </div>
                    </div>
                    <button
                      className="rag-space-del"
                      onClick={() => handleDeleteDoc(d.id)}
                    >
                      x
                    </button>
                  </div>
                ))}
              </div>

              {/* Chat */}
              <div className="rag-section">
                <div className="rag-section-title" style={{ marginBottom: 12 }}>
                  Chat with your documents
                </div>

                <div className="rag-chat-box">
                  {chatHistory.length === 0 && (
                    <div className="rag-chat-empty">
                      Ask a question about your uploaded documents
                    </div>
                  )}
                  {chatHistory.map((msg, i) => (
                    <div key={i} className={`rag-chat-msg ${msg.role}`}>
                      <div className="rag-chat-bubble">
                        <div
                          className="rag-md"
                          dangerouslySetInnerHTML={{
                            __html: formatAnswer(msg.content),
                          }}
                        />
                        {msg.sources && msg.sources.length > 0 && (
                          <div className="rag-sources">
                            <div className="rag-sources-label">Sources:</div>
                            {msg.sources.map((s, j) => (
                              <div key={j} className="rag-source-item">
                                {s.document} — page {s.page} (score: {s.score})
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  {querying && (
                    <div className="rag-chat-msg assistant">
                      <div className="rag-chat-bubble rag-typing">
                        Thinking...
                      </div>
                    </div>
                  )}
                </div>

                <div className="rag-chat-input">
                  <input
                    type="text"
                    placeholder="Ask a question..."
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleQuery()}
                    disabled={querying}
                  />
                  <button
                    onClick={handleQuery}
                    disabled={querying || !question.trim()}
                  >
                    Send
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Create modal with department selector ── */}
      {showCreate && (
        <div className="rag-overlay" onClick={() => setShowCreate(false)}>
          <div className="rag-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="rag-modal-title">Create RAG space</h3>
            <div className="field">
              <label>Name</label>
              <input
                type="text"
                placeholder="e.g. HR Documents"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                autoFocus
              />
            </div>
            <div className="field">
              <label>Description</label>
              <input
                type="text"
                placeholder="Optional description"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
              />
            </div>
            <div className="field">
              <label>Department</label>
              <select
                value={newDeptId}
                onChange={(e) => setNewDeptId(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: 8,
                  border: "1px solid #E5E7EB",
                  fontSize: 13,
                  color: newDeptId ? "#1F2937" : "#9CA3AF",
                }}
              >
                <option value="">Select a department</option>
                {depts.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
              {depts.length === 0 && (
                <span
                  style={{
                    fontSize: 11,
                    color: "#DC2626",
                    marginTop: 4,
                    display: "block",
                  }}
                >
                  No departments available — ask Admin to create one
                </span>
              )}
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              <button
                className="rag-btn-cancel"
                onClick={() => setShowCreate(false)}
              >
                Cancel
              </button>
              <button
                className="rag-btn-primary"
                onClick={handleCreate}
                disabled={loading || !newName.trim() || !newDeptId}
              >
                {loading ? "Creating..." : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RAGSpacesPage;
