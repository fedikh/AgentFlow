import React, { useState, useEffect, useRef } from "react";
import {
  listSpaces,
  createSpace,
  deleteSpace,
  listDocuments,
  uploadDocument,
  deleteDocument,
  listChunks,
  queryRAG,
} from "../../services/ragApi";
import { listDepartments } from "../../services/usersApi";
import { getUser } from "../../services/authApi";
import "../../styles/it/rag.css";

const RAGSpacesPage = () => {
  const currentUser = getUser();
  const [depts, setDepts] = useState([]);
  const [spaces, setSpaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Navigation
  const [activeDept, setActiveDept] = useState(null);
  const [activeSpace, setActiveSpace] = useState(null);
  const [activeTab, setActiveTab] = useState("documents");

  // Documents & chunks
  const [docs, setDocs] = useState([]);
  const [activeDoc, setActiveDoc] = useState(null);
  const [chunks, setChunks] = useState([]);
  const [loadingChunks, setLoadingChunks] = useState(false);

  // Upload
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  // Create modal
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newStrategy, setNewStrategy] = useState("FIXED");
  const [newChunkSize, setNewChunkSize] = useState(512);
  const [newOverlap, setNewOverlap] = useState(50);
  const [newTopK, setNewTopK] = useState(5);

  // Chat
  const [question, setQuestion] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [querying, setQuerying] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [d, s] = await Promise.all([listDepartments(), listSpaces()]);
      setDepts(d);
      setSpaces(s);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const deptSpaces = activeDept
    ? spaces.filter((s) => s.department_id === activeDept.id)
    : [];

  const spaceCountByDept = (deptId) =>
    spaces.filter((s) => s.department_id === deptId).length;

  const selectSpace = async (space) => {
    setActiveSpace(space);
    setActiveTab("documents");
    setActiveDoc(null);
    setChunks([]);
    setChatHistory([]);
    try {
      const d = await listDocuments(space.id);
      setDocs(d);
    } catch (e) {
      setError(e.message);
    }
  };

  const loadChunks = async (doc) => {
    setActiveDoc(doc);
    setLoadingChunks(true);
    try {
      const c = await listChunks(activeSpace.id, doc.id);
      setChunks(c);
      setActiveTab("chunks");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingChunks(false);
    }
  };

  // ── Create space ──
  const handleCreate = async () => {
    if (!newName.trim() || !activeDept) return;
    try {
      await createSpace({
        name: newName,
        description: newDesc,
        department_id: activeDept.id,
        chunk_strategy: newStrategy,
        chunk_size: newChunkSize,
        chunk_overlap: newOverlap,
        top_k: newTopK,
      });
      setNewName("");
      setNewDesc("");
      setNewStrategy("FIXED");
      setNewChunkSize(512);
      setNewOverlap(50);
      setNewTopK(5);
      setShowCreate(false);
      await loadData();
    } catch (e) {
      setError(e.message);
    }
  };

  // ── Upload ──
  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || !activeSpace) return;
    setUploading(true);
    setError("");
    try {
      await uploadDocument(activeSpace.id, file);
      const d = await listDocuments(activeSpace.id);
      setDocs(d);
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      fileRef.current.value = "";
    }
  };

  const handleDeleteDoc = async (docId) => {
    try {
      await deleteDocument(activeSpace.id, docId);
      setDocs(docs.filter((d) => d.id !== docId));
      if (activeDoc?.id === docId) {
        setActiveDoc(null);
        setChunks([]);
      }
    } catch (e) {
      setError(e.message);
    }
  };

  const handleDeleteSpace = async (id) => {
    if (!confirm("Delete this RAG space and all its documents?")) return;
    try {
      await deleteSpace(id);
      setActiveSpace(null);
      setDocs([]);
      setChunks([]);
      await loadData();
    } catch (e) {
      setError(e.message);
    }
  };

  // ── Chat ──
  const handleQuery = async () => {
    if (!question.trim() || !activeSpace) return;
    const q = question;
    setQuestion("");
    setChatHistory((prev) => [...prev, { role: "user", content: q }]);
    setQuerying(true);
    try {
      const res = await queryRAG(activeSpace.id, q);
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

  const formatAnswer = (text) => {
    if (!text) return "";
    return text
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(
        /^## (.+)$/gm,
        '<div style="font-weight:600;font-size:14px;margin:8px 0 4px">$1</div>',
      )
      .replace(/^[•\-\*] (.+)$/gm, '<div style="padding-left:12px">• $1</div>')
      .replace(/\n/g, "<br>");
  };

  // ── Chunk stats ──
  const chunkStats =
    chunks.length > 0
      ? {
          total: chunks.length,
          textCount: chunks.filter((c) => c.type === "text").length,
          tableCount: chunks.filter((c) => c.type === "table").length,
          avgSize: Math.round(
            chunks.reduce((a, c) => a + c.char_count, 0) / chunks.length,
          ),
          minSize: Math.min(...chunks.map((c) => c.char_count)),
          maxSize: Math.max(...chunks.map((c) => c.char_count)),
        }
      : null;

  // ══════════════════════════════════════════════════
  // VIEW 1: DEPARTMENT GRID
  // ══════════════════════════════════════════════════
  if (!activeDept) {
    return (
      <div className="rag-page">
        <h1 className="rag-title">RAG Spaces</h1>
        <p className="rag-sub">Select a department to manage its RAG spaces</p>
        {error && (
          <div className="rag-error">
            {error}{" "}
            <span
              onClick={() => setError("")}
              style={{ cursor: "pointer", marginLeft: 8 }}
            >
              ✕
            </span>
          </div>
        )}
        {loading && (
          <p style={{ color: "#9CA3AF", fontSize: 13 }}>Loading...</p>
        )}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))",
            gap: 12,
            marginTop: 20,
          }}
        >
          {depts.map((d) => (
            <div
              key={d.id}
              onClick={() => setActiveDept(d)}
              style={{
                padding: "20px 16px",
                borderRadius: 12,
                border: "1px solid #E5E7EB",
                cursor: "pointer",
                background: "#fff",
                transition: "all 0.2s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "#2563EB";
                e.currentTarget.style.boxShadow =
                  "0 2px 8px rgba(37,99,235,0.1)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "#E5E7EB";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              <div style={{ fontSize: 28, marginBottom: 10 }}>📁</div>
              <div style={{ fontSize: 15, fontWeight: 600, color: "#1F2937" }}>
                {d.name}
              </div>
              <div style={{ fontSize: 12, color: "#6B7280", marginTop: 4 }}>
                {spaceCountByDept(d.id)} RAG space
                {spaceCountByDept(d.id) !== 1 ? "s" : ""}
              </div>
            </div>
          ))}
          {depts.length === 0 && !loading && (
            <div
              style={{
                padding: 40,
                textAlign: "center",
                color: "#6B7280",
                gridColumn: "1/-1",
              }}
            >
              <div style={{ fontSize: 40, marginBottom: 12 }}>📁</div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>
                No departments assigned
              </div>
              <div style={{ fontSize: 12, marginTop: 4 }}>
                Ask your Admin to assign you to a department
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ══════════════════════════════════════════════════
  // VIEW 2: SPACES LIST
  // ══════════════════════════════════════════════════
  if (!activeSpace) {
    return (
      <div className="rag-page">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginBottom: 20,
          }}
        >
          <button
            onClick={() => setActiveDept(null)}
            style={{
              background: "none",
              border: "1px solid #E5E7EB",
              borderRadius: 8,
              padding: "6px 12px",
              cursor: "pointer",
              fontSize: 13,
              color: "#374151",
            }}
          >
            ← Back
          </button>
          <div style={{ flex: 1 }}>
            <h1 className="rag-title" style={{ marginBottom: 0 }}>
              {activeDept.name}
            </h1>
            <p className="rag-sub">
              {deptSpaces.length} RAG space{deptSpaces.length !== 1 ? "s" : ""}
            </p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            style={{
              background: "#2563EB",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              padding: "8px 16px",
              fontSize: 13,
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            + New RAG space
          </button>
        </div>

        {error && (
          <div className="rag-error">
            {error}{" "}
            <span
              onClick={() => setError("")}
              style={{ cursor: "pointer", marginLeft: 8 }}
            >
              ✕
            </span>
          </div>
        )}

        {deptSpaces.length === 0 && (
          <div style={{ padding: 60, textAlign: "center", color: "#6B7280" }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>🤖</div>
            <div style={{ fontSize: 16, fontWeight: 600, color: "#374151" }}>
              No RAG spaces yet
            </div>
            <div style={{ fontSize: 13, marginTop: 4 }}>
              Create your first RAG space for {activeDept.name}
            </div>
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {deptSpaces.map((s) => (
            <div
              key={s.id}
              onClick={() => selectSpace(s)}
              style={{
                padding: "14px 16px",
                borderRadius: 10,
                border: "1px solid #E5E7EB",
                cursor: "pointer",
                background: "#fff",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                transition: "all 0.2s",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.borderColor = "#2563EB")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.borderColor = "#E5E7EB")
              }
            >
              <div>
                <div
                  style={{ fontSize: 14, fontWeight: 600, color: "#1F2937" }}
                >
                  {s.name}
                </div>
                <div style={{ fontSize: 12, color: "#6B7280", marginTop: 2 }}>
                  {s.num_documents} doc(s) · {s.num_chunks} chunks
                </div>
              </div>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 500,
                    padding: "2px 8px",
                    borderRadius: 4,
                    background: "#FEF3C7",
                    color: "#92400E",
                    border: "1px solid #FCD34D",
                  }}
                >
                  {s.chunk_strategy}
                </span>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 500,
                    padding: "2px 8px",
                    borderRadius: 4,
                    background: "#EFF6FF",
                    color: "#1D4ED8",
                    border: "1px solid #BFDBFE",
                  }}
                >
                  {s.embedding_provider}
                </span>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 500,
                    padding: "2px 8px",
                    borderRadius: 4,
                    background: "#F0FDF4",
                    color: "#166534",
                    border: "1px solid #BBF7D0",
                  }}
                >
                  {s.llm_provider}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteSpace(s.id);
                  }}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#DC2626",
                    cursor: "pointer",
                    fontSize: 14,
                    padding: "0 4px",
                  }}
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* ═══ CREATE MODAL ═══ */}
        {showCreate && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 100,
            }}
            onClick={() => setShowCreate(false)}
          >
            <div
              style={{
                background: "#fff",
                borderRadius: 16,
                padding: 24,
                width: 520,
                maxWidth: "90vw",
                maxHeight: "85vh",
                overflowY: "auto",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 20 }}>
                New RAG space in {activeDept.name}
              </h3>

              {/* Name */}
              <div style={{ marginBottom: 14 }}>
                <label
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color: "#374151",
                    display: "block",
                    marginBottom: 4,
                  }}
                >
                  Name *
                </label>
                <input
                  type="text"
                  placeholder="e.g. HR Policy Documents"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  autoFocus
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: 8,
                    border: "1px solid #E5E7EB",
                    fontSize: 13,
                  }}
                />
              </div>

              {/* Description */}
              <div style={{ marginBottom: 14 }}>
                <label
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color: "#374151",
                    display: "block",
                    marginBottom: 4,
                  }}
                >
                  Description
                </label>
                <input
                  type="text"
                  placeholder="Optional description"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: 8,
                    border: "1px solid #E5E7EB",
                    fontSize: 13,
                  }}
                />
              </div>

              {/* Chunking strategy */}
              <div style={{ marginBottom: 14 }}>
                <label
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color: "#374151",
                    display: "block",
                    marginBottom: 8,
                  }}
                >
                  Chunking strategy
                </label>
                <div style={{ display: "flex", gap: 8 }}>
                  {[
                    {
                      value: "FIXED",
                      label: "Fixed",
                      desc: "Coupe tous les N caractères avec overlap",
                      icon: "✂️",
                    },
                    {
                      value: "SEMANTIC",
                      label: "Semantic",
                      desc: "Coupe par changement de sujet (IA)",
                      icon: "🧠",
                    },
                    {
                      value: "HIERARCHICAL",
                      label: "Hierarchical",
                      desc: "Parent-child (2 niveaux)",
                      icon: "🏗️",
                    },
                  ].map((s) => (
                    <div
                      key={s.value}
                      onClick={() => setNewStrategy(s.value)}
                      style={{
                        flex: 1,
                        padding: "12px 10px",
                        borderRadius: 10,
                        cursor: "pointer",
                        textAlign: "center",
                        border:
                          newStrategy === s.value
                            ? "2px solid #2563EB"
                            : "1px solid #E5E7EB",
                        background:
                          newStrategy === s.value ? "#EFF6FF" : "#fff",
                        transition: "all 0.2s",
                      }}
                    >
                      <div style={{ fontSize: 20, marginBottom: 4 }}>
                        {s.icon}
                      </div>
                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: newStrategy === s.value ? 600 : 400,
                          color:
                            newStrategy === s.value ? "#1D4ED8" : "#374151",
                        }}
                      >
                        {s.label}
                      </div>
                      <div
                        style={{
                          fontSize: 10,
                          color: "#6B7280",
                          marginTop: 2,
                          lineHeight: 1.4,
                        }}
                      >
                        {s.desc}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Chunk size slider */}
              <div style={{ marginBottom: 14 }}>
                <label
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color: "#374151",
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: 4,
                  }}
                >
                  <span>Chunk size</span>
                  <span style={{ color: "#2563EB", fontWeight: 600 }}>
                    {newChunkSize} chars
                  </span>
                </label>
                <input
                  type="range"
                  min={100}
                  max={2000}
                  step={50}
                  value={newChunkSize}
                  onChange={(e) => setNewChunkSize(parseInt(e.target.value))}
                  style={{ width: "100%", accentColor: "#2563EB" }}
                />
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: 10,
                    color: "#9CA3AF",
                  }}
                >
                  <span>100 (précis)</span>
                  <span>2000 (contexte riche)</span>
                </div>
              </div>

              {/* Overlap slider */}
              <div style={{ marginBottom: 14 }}>
                <label
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color: "#374151",
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: 4,
                  }}
                >
                  <span>Overlap</span>
                  <span style={{ color: "#2563EB", fontWeight: 600 }}>
                    {newOverlap} chars
                  </span>
                </label>
                <input
                  type="range"
                  min={0}
                  max={200}
                  step={10}
                  value={newOverlap}
                  onChange={(e) => setNewOverlap(parseInt(e.target.value))}
                  style={{ width: "100%", accentColor: "#2563EB" }}
                />
              </div>

              {/* Top-K */}
              <div style={{ marginBottom: 20 }}>
                <label
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color: "#374151",
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: 4,
                  }}
                >
                  <span>Top-K results</span>
                  <span style={{ color: "#2563EB", fontWeight: 600 }}>
                    {newTopK}
                  </span>
                </label>
                <input
                  type="range"
                  min={1}
                  max={15}
                  step={1}
                  value={newTopK}
                  onChange={(e) => setNewTopK(parseInt(e.target.value))}
                  style={{ width: "100%", accentColor: "#2563EB" }}
                />
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: 10,
                    color: "#9CA3AF",
                  }}
                >
                  <span>1 (très précis)</span>
                  <span>15 (plus de contexte)</span>
                </div>
              </div>

              {/* Buttons */}
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={() => setShowCreate(false)}
                  style={{
                    flex: 1,
                    padding: "10px",
                    borderRadius: 8,
                    border: "1px solid #E5E7EB",
                    background: "#fff",
                    cursor: "pointer",
                    fontSize: 13,
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreate}
                  disabled={!newName.trim()}
                  style={{
                    flex: 1,
                    padding: "10px",
                    borderRadius: 8,
                    border: "none",
                    background: "#2563EB",
                    color: "#fff",
                    cursor: "pointer",
                    fontSize: 13,
                    fontWeight: 500,
                    opacity: newName.trim() ? "1" : "0.5",
                  }}
                >
                  Create RAG space
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ══════════════════════════════════════════════════
  // VIEW 3: SPACE DETAIL (tabs)
  // ══════════════════════════════════════════════════
  return (
    <div className="rag-page">
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          marginBottom: 16,
        }}
      >
        <button
          onClick={() => {
            setActiveSpace(null);
            setDocs([]);
            setChunks([]);
            setActiveDoc(null);
          }}
          style={{
            background: "none",
            border: "1px solid #E5E7EB",
            borderRadius: 8,
            padding: "6px 12px",
            cursor: "pointer",
            fontSize: 13,
            color: "#374151",
          }}
        >
          ← Back
        </button>
        <div style={{ flex: 1 }}>
          <h1 className="rag-title" style={{ marginBottom: 0 }}>
            {activeSpace.name}
          </h1>
          <div
            style={{ display: "flex", gap: 6, marginTop: 4, flexWrap: "wrap" }}
          >
            {activeSpace.department_name && (
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 500,
                  padding: "2px 8px",
                  borderRadius: 4,
                  background: "#EFF6FF",
                  color: "#1D4ED8",
                  border: "1px solid #BFDBFE",
                }}
              >
                {activeSpace.department_name}
              </span>
            )}
            <span
              style={{
                fontSize: 10,
                fontWeight: 500,
                padding: "2px 8px",
                borderRadius: 4,
                background: "#FEF3C7",
                color: "#92400E",
                border: "1px solid #FCD34D",
              }}
            >
              {activeSpace.chunk_strategy}
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 500,
                padding: "2px 8px",
                borderRadius: 4,
                background: "#F3F4F6",
                color: "#374151",
              }}
            >
              Size: {activeSpace.chunk_size}
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 500,
                padding: "2px 8px",
                borderRadius: 4,
                background: "#F3F4F6",
                color: "#374151",
              }}
            >
              Overlap: {activeSpace.chunk_overlap}
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 500,
                padding: "2px 8px",
                borderRadius: 4,
                background: "#F3F4F6",
                color: "#374151",
              }}
            >
              Top-K: {activeSpace.top_k}
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 500,
                padding: "2px 8px",
                borderRadius: 4,
                background: "#EFF6FF",
                color: "#1D4ED8",
              }}
            >
              {activeSpace.embedding_provider}
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 500,
                padding: "2px 8px",
                borderRadius: 4,
                background: "#F0FDF4",
                color: "#166534",
              }}
            >
              {activeSpace.llm_provider}
            </span>
          </div>
        </div>
      </div>

      {error && (
        <div className="rag-error">
          {error}{" "}
          <span
            onClick={() => setError("")}
            style={{ cursor: "pointer", marginLeft: 8 }}
          >
            ✕
          </span>
        </div>
      )}

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: 0,
          borderBottom: "1px solid #E5E7EB",
          marginBottom: 16,
        }}
      >
        {[
          { key: "documents", label: `Documents (${docs.length})` },
          {
            key: "chunks",
            label: `Chunks${activeDoc ? ` — ${activeDoc.file_name}` : ""}`,
          },
          { key: "chat", label: "Chat" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: "10px 20px",
              fontSize: 13,
              fontWeight: activeTab === tab.key ? 500 : 400,
              color: activeTab === tab.key ? "#2563EB" : "#6B7280",
              background: "none",
              border: "none",
              borderBottom:
                activeTab === tab.key
                  ? "2px solid #2563EB"
                  : "2px solid transparent",
              cursor: "pointer",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── TAB: Documents ── */}
      {activeTab === "documents" && (
        <div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 12,
            }}
          >
            <span style={{ fontSize: 14, fontWeight: 600, color: "#1F2937" }}>
              Uploaded documents
            </span>
            <button
              onClick={() => fileRef.current.click()}
              disabled={uploading}
              style={{
                background: "#2563EB",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                padding: "8px 16px",
                fontSize: 12,
                fontWeight: 500,
                cursor: "pointer",
                opacity: uploading ? 0.6 : 1,
              }}
            >
              {uploading ? "Uploading..." : "Upload document"}
            </button>
            <input
              type="file"
              ref={fileRef}
              accept=".pdf,.docx,.doc,.txt,.csv,.xlsx,.xls"
              onChange={handleUpload}
              style={{ display: "none" }}
            />
          </div>

          {docs.length === 0 && (
            <p
              style={{
                color: "#9CA3AF",
                fontSize: 13,
                textAlign: "center",
                padding: 40,
              }}
            >
              No documents yet — upload one!
            </p>
          )}

          {docs.map((d) => (
            <div
              key={d.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "10px 14px",
                borderRadius: 8,
                border: "1px solid #E5E7EB",
                marginBottom: 6,
                background: "#fff",
              }}
            >
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 8,
                  background: "#EFF6FF",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 11,
                  fontWeight: 700,
                  color: "#2563EB",
                }}
              >
                {d.file_type?.toUpperCase() || "?"}
              </div>
              <div style={{ flex: 1 }}>
                <div
                  style={{ fontSize: 13, fontWeight: 500, color: "#1F2937" }}
                >
                  {d.file_name}
                </div>
                <div style={{ fontSize: 11, color: "#6B7280" }}>
                  {d.num_chunks} chunks · {d.status}
                  {d.status === "ERROR" && d.error_msg && (
                    <span style={{ color: "#DC2626" }}> — {d.error_msg}</span>
                  )}
                </div>
              </div>
              {d.status === "INDEXED" && (
                <button
                  onClick={() => loadChunks(d)}
                  style={{
                    background: "#F3F4F6",
                    border: "none",
                    borderRadius: 6,
                    padding: "6px 12px",
                    fontSize: 11,
                    fontWeight: 500,
                    color: "#374151",
                    cursor: "pointer",
                  }}
                >
                  View chunks
                </button>
              )}
              <button
                onClick={() => handleDeleteDoc(d.id)}
                style={{
                  background: "none",
                  border: "none",
                  color: "#DC2626",
                  cursor: "pointer",
                  fontSize: 14,
                }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {/* ── TAB: Chunks ── */}
      {activeTab === "chunks" && (
        <div>
          {!activeDoc && (
            <p
              style={{
                color: "#9CA3AF",
                fontSize: 13,
                textAlign: "center",
                padding: 40,
              }}
            >
              Go to the Documents tab and click "View chunks" on a document
            </p>
          )}

          {activeDoc && (
            <>
              {/* Stats bar */}
              {chunkStats && (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(6,1fr)",
                    gap: 8,
                    marginBottom: 16,
                  }}
                >
                  {[
                    {
                      label: "Total chunks",
                      value: chunkStats.total,
                      bg: "#EFF6FF",
                      color: "#1D4ED8",
                    },
                    {
                      label: "Text",
                      value: chunkStats.textCount,
                      bg: "#F0FDF4",
                      color: "#166534",
                    },
                    {
                      label: "Tables",
                      value: chunkStats.tableCount,
                      bg: "#FEF3C7",
                      color: "#92400E",
                    },
                    {
                      label: "Avg size",
                      value: `${chunkStats.avgSize}`,
                      bg: "#F3F4F6",
                      color: "#374151",
                    },
                    {
                      label: "Min",
                      value: `${chunkStats.minSize}`,
                      bg: "#F3F4F6",
                      color: "#374151",
                    },
                    {
                      label: "Max",
                      value: `${chunkStats.maxSize}`,
                      bg: "#F3F4F6",
                      color: "#374151",
                    },
                  ].map((s, i) => (
                    <div
                      key={i}
                      style={{
                        padding: "10px 12px",
                        borderRadius: 8,
                        background: s.bg,
                        textAlign: "center",
                      }}
                    >
                      <div
                        style={{
                          fontSize: 18,
                          fontWeight: 700,
                          color: s.color,
                        }}
                      >
                        {s.value}
                      </div>
                      <div
                        style={{ fontSize: 10, color: "#6B7280", marginTop: 2 }}
                      >
                        {s.label}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "#1F2937",
                  marginBottom: 8,
                }}
              >
                Chunks from "{activeDoc.file_name}" — strategy:{" "}
                {activeSpace.chunk_strategy}
              </div>

              {loadingChunks && (
                <p style={{ color: "#9CA3AF", fontSize: 13 }}>
                  Loading chunks...
                </p>
              )}

              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  maxHeight: "55vh",
                  overflowY: "auto",
                }}
              >
                {chunks.map((c, i) => (
                  <div
                    key={c.id || i}
                    style={{
                      padding: "12px 14px",
                      borderRadius: 8,
                      border: "1px solid #E5E7EB",
                      background: "#fff",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        marginBottom: 6,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          gap: 6,
                          alignItems: "center",
                        }}
                      >
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 600,
                            padding: "2px 8px",
                            borderRadius: 4,
                            background: "#F3F4F6",
                            color: "#374151",
                          }}
                        >
                          #{c.chunk_index}
                        </span>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 500,
                            padding: "2px 8px",
                            borderRadius: 4,
                            background:
                              c.type === "table" ? "#FEF3C7" : "#EFF6FF",
                            color: c.type === "table" ? "#92400E" : "#1D4ED8",
                          }}
                        >
                          {c.type}
                        </span>
                        <span style={{ fontSize: 10, color: "#6B7280" }}>
                          page {c.page}
                        </span>
                      </div>
                      <span style={{ fontSize: 10, color: "#6B7280" }}>
                        {c.char_count} chars
                      </span>
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: "#374151",
                        lineHeight: 1.6,
                        whiteSpace: "pre-wrap",
                        maxHeight: 200,
                        overflowY: "auto",
                        fontFamily: "'Courier New',monospace",
                        background: "#F9FAFB",
                        padding: "8px 10px",
                        borderRadius: 6,
                      }}
                    >
                      {c.content}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── TAB: Chat ── */}
      {activeTab === "chat" && (
        <div>
          <div
            style={{
              minHeight: 300,
              maxHeight: "50vh",
              overflowY: "auto",
              marginBottom: 12,
              padding: "8px 0",
            }}
          >
            {chatHistory.length === 0 && (
              <div
                style={{
                  textAlign: "center",
                  padding: 40,
                  color: "#6B7280",
                  fontSize: 13,
                }}
              >
                Ask a question about your documents
              </div>
            )}
            {chatHistory.map((msg, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent:
                    msg.role === "user" ? "flex-end" : "flex-start",
                  marginBottom: 8,
                }}
              >
                <div
                  style={{
                    maxWidth: "80%",
                    padding: "10px 14px",
                    borderRadius: 12,
                    background: msg.role === "user" ? "#2563EB" : "#F3F4F6",
                    color: msg.role === "user" ? "#fff" : "#1F2937",
                    fontSize: 13,
                    lineHeight: 1.6,
                  }}
                >
                  <div
                    dangerouslySetInnerHTML={{
                      __html: formatAnswer(msg.content),
                    }}
                  />
                  {msg.sources && msg.sources.length > 0 && (
                    <div
                      style={{
                        marginTop: 8,
                        paddingTop: 6,
                        borderTop: "1px solid rgba(0,0,0,0.1)",
                        fontSize: 11,
                        color:
                          msg.role === "user"
                            ? "rgba(255,255,255,0.7)"
                            : "#6B7280",
                      }}
                    >
                      📄{" "}
                      {msg.sources
                        .map((s) => `${s.document} p.${s.page}`)
                        .join(" · ")}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {querying && (
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-start",
                  marginBottom: 8,
                }}
              >
                <div
                  style={{
                    padding: "10px 14px",
                    borderRadius: 12,
                    background: "#F3F4F6",
                    color: "#6B7280",
                    fontSize: 13,
                  }}
                >
                  Thinking...
                </div>
              </div>
            )}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              type="text"
              placeholder="Ask a question..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleQuery()}
              disabled={querying}
              style={{
                flex: 1,
                padding: "10px 14px",
                borderRadius: 10,
                border: "1px solid #E5E7EB",
                fontSize: 13,
              }}
            />
            <button
              onClick={handleQuery}
              disabled={querying || !question.trim()}
              style={{
                background: "#2563EB",
                color: "#fff",
                border: "none",
                borderRadius: 10,
                padding: "10px 20px",
                fontSize: 13,
                fontWeight: 500,
                cursor: "pointer",
                opacity: querying || !question.trim() ? 0.5 : 1,
              }}
            >
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default RAGSpacesPage;
