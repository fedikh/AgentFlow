import React, { useState, useEffect, useRef } from "react";
import {
  listSpaces,
  createSpace,
  deleteSpace,
  listDocuments,
  uploadDocument,
  deleteDocument,
  scrapeUrl,
  getExtractedContent,
  processDocument,
  processAllDocuments,
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
  const [success, setSuccess] = useState("");

  const [activeDept, setActiveDept] = useState(null);
  const [activeSpace, setActiveSpace] = useState(null);
  const [activeTab, setActiveTab] = useState("documents");

  const [docs, setDocs] = useState([]);
  const [activeDoc, setActiveDoc] = useState(null);
  const [extractedData, setExtractedData] = useState(null);
  const [chunks, setChunks] = useState([]);
  const [loadingExtract, setLoadingExtract] = useState(false);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [processing, setProcessing] = useState(false);

  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [scrapeUrlValue, setScrapeUrlValue] = useState("");
  const [scraping, setScraping] = useState(false);

  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");

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
      const userDeptIds = currentUser?.department_ids || [];
      const myDepts =
        currentUser?.role === "ADMIN"
          ? d
          : d.filter((dept) => userDeptIds.includes(dept.id));
      setDepts(myDepts);
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
    setExtractedData(null);
    setChunks([]);
    setChatHistory([]);
    try {
      setDocs(await listDocuments(space.id));
    } catch (e) {
      setError(e.message);
    }
  };

  const handleCreate = async () => {
    if (!newName.trim() || !activeDept) return;
    try {
      await createSpace({
        name: newName,
        description: newDesc,
        department_id: activeDept.id,
      });
      setNewName("");
      setNewDesc("");
      setShowCreate(false);
      await loadData();
    } catch (e) {
      setError(e.message);
    }
  };

  // ── Upload local file ──
  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || !activeSpace) return;
    setUploading(true);
    setError("");
    try {
      await uploadDocument(activeSpace.id, file);
      setSuccess(`"${file.name}" uploaded and text extracted`);
      setDocs(await listDocuments(activeSpace.id));
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      fileRef.current.value = "";
    }
  };

  // ── Scrape URL ──
  const handleScrape = async () => {
    if (!scrapeUrlValue.trim() || !activeSpace) return;
    setScraping(true);
    setError("");
    try {
      await scrapeUrl(activeSpace.id, scrapeUrlValue);
      setSuccess(`URL scraped and text extracted`);
      setScrapeUrlValue("");
      setDocs(await listDocuments(activeSpace.id));
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setScraping(false);
    }
  };

  // ── View extracted text ──
  const viewExtracted = async (doc) => {
    setActiveDoc(doc);
    setLoadingExtract(true);
    try {
      const data = await getExtractedContent(activeSpace.id, doc.id);
      setExtractedData(data);
      setActiveTab("extracted");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingExtract(false);
    }
  };

  // ── Process one document ──
  const handleProcess = async (docId) => {
    setProcessing(true);
    setError("");
    try {
      await processDocument(activeSpace.id, docId);
      setSuccess("Document processed — chunks created");
      setDocs(await listDocuments(activeSpace.id));
      await loadData();
    } catch (e) {
      setError(e.message);
    } finally {
      setProcessing(false);
    }
  };

  // ── Process all ──
  const handleProcessAll = async () => {
    setProcessing(true);
    setError("");
    try {
      const result = await processAllDocuments(activeSpace.id);
      setSuccess(`${result.processed} document(s) processed`);
      setDocs(await listDocuments(activeSpace.id));
      await loadData();
    } catch (e) {
      setError(e.message);
    } finally {
      setProcessing(false);
    }
  };

  // ── View chunks ──
  const viewChunks = async (doc) => {
    setActiveDoc(doc);
    setLoadingChunks(true);
    try {
      setChunks(await listChunks(activeSpace.id, doc.id));
      setActiveTab("chunks");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingChunks(false);
    }
  };

  const handleDeleteDoc = async (docId) => {
    try {
      await deleteDocument(activeSpace.id, docId);
      setDocs(docs.filter((d) => d.id !== docId));
      if (activeDoc?.id === docId) {
        setActiveDoc(null);
        setExtractedData(null);
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
      await loadData();
    } catch (e) {
      setError(e.message);
    }
  };

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

  const formatAnswer = (t) =>
    t
      ? t
          .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
          .replace(
            /^## (.+)$/gm,
            '<div style="font-weight:600;margin:8px 0 4px">$1</div>',
          )
          .replace(
            /^[•\-\*] (.+)$/gm,
            '<div style="padding-left:12px">• $1</div>',
          )
          .replace(/\n/g, "<br>")
      : "";

  const chunkStats =
    chunks.length > 0
      ? {
          total: chunks.length,
          text: chunks.filter((c) => c.type === "text").length,
          table: chunks.filter((c) => c.type === "table").length,
          avg: Math.round(
            chunks.reduce((a, c) => a + c.char_count, 0) / chunks.length,
          ),
        }
      : null;

  const extractedDocsCount = docs.filter(
    (d) => d.status === "EXTRACTED",
  ).length;

  const Banners = () => (
    <>
      {error && (
        <div
          style={{
            padding: "10px 14px",
            borderRadius: 8,
            background: "#FEF2F2",
            color: "#991B1B",
            fontSize: 12,
            marginBottom: 12,
            display: "flex",
            justifyContent: "space-between",
          }}
        >
          {error}
          <span onClick={() => setError("")} style={{ cursor: "pointer" }}>
            ✕
          </span>
        </div>
      )}
      {success && (
        <div
          style={{
            padding: "10px 14px",
            borderRadius: 8,
            background: "#ECFDF5",
            color: "#065F46",
            fontSize: 12,
            marginBottom: 12,
            display: "flex",
            justifyContent: "space-between",
          }}
        >
          {success}
          <span onClick={() => setSuccess("")} style={{ cursor: "pointer" }}>
            ✕
          </span>
        </div>
      )}
    </>
  );

  const statusBadge = (status) => {
    const colors = {
      UPLOADING: { bg: "#FEF3C7", color: "#92400E" },
      EXTRACTED: { bg: "#EFF6FF", color: "#1E40AF" },
      PROCESSING: { bg: "#FEF3C7", color: "#92400E" },
      INDEXED: { bg: "#ECFDF5", color: "#065F46" },
      ERROR: { bg: "#FEF2F2", color: "#991B1B" },
    };
    const c = colors[status] || colors.UPLOADING;
    return (
      <span
        style={{
          fontSize: 10,
          fontWeight: 500,
          padding: "2px 8px",
          borderRadius: 100,
          background: c.bg,
          color: c.color,
        }}
      >
        {status}
      </span>
    );
  };

  // ══════════ VIEW 1: DEPARTMENTS ══════════
  if (!activeDept) {
    return (
      <div className="rag-page">
        <h1 className="rag-title">RAG Spaces</h1>
        <p className="rag-sub">Select a department to manage its RAG spaces</p>
        <Banners />
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
                {spaceCountByDept(d.id)} space
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

  // ══════════ VIEW 2: SPACES LIST ══════════
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
        <Banners />
        {deptSpaces.length === 0 && (
          <div style={{ padding: 60, textAlign: "center", color: "#6B7280" }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>🤖</div>
            <div style={{ fontSize: 16, fontWeight: 600, color: "#374151" }}>
              No RAG spaces yet
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
                  }}
                >
                  {s.chunk_strategy}
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
                  }}
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
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
                width: 420,
                maxWidth: "90vw",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 20 }}>
                New RAG space in {activeDept.name}
              </h3>
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
              <div style={{ marginBottom: 16 }}>
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
                  placeholder="Optional"
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
              <div
                style={{
                  padding: 12,
                  background: "#F9FAFB",
                  borderRadius: 8,
                  marginBottom: 16,
                  fontSize: 12,
                  color: "#6B7280",
                  lineHeight: 1.6,
                }}
              >
                Next step: upload your documents, review the extracted text,
                then configure and process.
              </div>
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
                  Create
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ══════════ VIEW 3: SPACE DETAIL ══════════
  return (
    <div className="rag-page">
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
            setExtractedData(null);
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
          <p className="rag-sub" style={{ marginTop: 2 }}>
            {activeSpace.description || "No description"}
          </p>
        </div>
      </div>
      <Banners />

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
            key: "extracted",
            label: `Extracted text${activeDoc ? ` — ${activeDoc.file_name}` : ""}`,
          },
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
              padding: "10px 16px",
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

      {/* ═══ TAB: Documents ═══ */}
      {activeTab === "documents" && (
        <div>
          {/* Upload sources */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: 10,
              marginBottom: 16,
            }}
          >
            {/* Local upload */}
            <div
              onClick={() => fileRef.current.click()}
              style={{
                padding: "16px",
                borderRadius: 10,
                border: "2px dashed #E5E7EB",
                cursor: "pointer",
                textAlign: "center",
                transition: "all 0.2s",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.borderColor = "#2563EB")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.borderColor = "#E5E7EB")
              }
            >
              <div style={{ fontSize: 24, marginBottom: 6 }}>💻</div>
              <div style={{ fontSize: 13, fontWeight: 500, color: "#1F2937" }}>
                {uploading ? "Uploading..." : "Local file"}
              </div>
              <div style={{ fontSize: 10, color: "#6B7280", marginTop: 2 }}>
                PDF, DOCX, TXT, CSV, Excel, MD, HTML
              </div>
            </div>
            <input
              type="file"
              ref={fileRef}
              accept=".pdf,.docx,.doc,.txt,.csv,.xlsx,.xls,.md,.html,.htm"
              onChange={handleUpload}
              style={{ display: "none" }}
            />

            {/* Google Drive */}
            <div
              style={{
                padding: "16px",
                borderRadius: 10,
                border: "1px solid #E5E7EB",
                textAlign: "center",
                opacity: 0.5,
                cursor: "not-allowed",
              }}
            >
              <div style={{ fontSize: 24, marginBottom: 6 }}>📁</div>
              <div style={{ fontSize: 13, fontWeight: 500, color: "#1F2937" }}>
                Google Drive
              </div>
              <div style={{ fontSize: 10, color: "#9CA3AF", marginTop: 2 }}>
                Coming soon
              </div>
            </div>

            {/* OneDrive */}
            <div
              style={{
                padding: "16px",
                borderRadius: 10,
                border: "1px solid #E5E7EB",
                textAlign: "center",
                opacity: 0.5,
                cursor: "not-allowed",
              }}
            >
              <div style={{ fontSize: 24, marginBottom: 6 }}>☁️</div>
              <div style={{ fontSize: 13, fontWeight: 500, color: "#1F2937" }}>
                OneDrive
              </div>
              <div style={{ fontSize: 10, color: "#9CA3AF", marginTop: 2 }}>
                Coming soon
              </div>
            </div>
          </div>

          {/* URL input */}
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <div
              style={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "8px 12px",
                borderRadius: 8,
                border: "1px solid #E5E7EB",
                background: "#fff",
              }}
            >
              <span style={{ fontSize: 14 }}>🌐</span>
              <input
                type="text"
                placeholder="Paste a URL to scrape (https://...)"
                value={scrapeUrlValue}
                onChange={(e) => setScrapeUrlValue(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleScrape()}
                style={{
                  flex: 1,
                  border: "none",
                  outline: "none",
                  fontSize: 13,
                }}
              />
            </div>
            <button
              onClick={handleScrape}
              disabled={scraping || !scrapeUrlValue.trim()}
              style={{
                background: "#2563EB",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                padding: "8px 16px",
                fontSize: 12,
                fontWeight: 500,
                cursor: "pointer",
                opacity: scraping || !scrapeUrlValue.trim() ? 0.5 : 1,
                whiteSpace: "nowrap",
              }}
            >
              {scraping ? "Scraping..." : "Scrape"}
            </button>
          </div>

          {/* Process all button */}
          {extractedDocsCount > 0 && (
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                marginBottom: 12,
              }}
            >
              <button
                onClick={handleProcessAll}
                disabled={processing}
                style={{
                  background: "#059669",
                  color: "#fff",
                  border: "none",
                  borderRadius: 8,
                  padding: "8px 16px",
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: "pointer",
                  opacity: processing ? 0.5 : 1,
                }}
              >
                {processing
                  ? "Processing..."
                  : `Process all (${extractedDocsCount} ready)`}
              </button>
            </div>
          )}

          {/* Documents list */}
          {docs.length === 0 && (
            <p
              style={{
                color: "#9CA3AF",
                fontSize: 13,
                textAlign: "center",
                padding: 30,
              }}
            >
              No documents yet — upload a file or paste a URL
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
                {d.source_type === "url"
                  ? "URL"
                  : d.file_type?.toUpperCase() || "?"}
              </div>
              <div style={{ flex: 1 }}>
                <div
                  style={{ fontSize: 13, fontWeight: 500, color: "#1F2937" }}
                >
                  {d.file_name}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: "#6B7280",
                    display: "flex",
                    gap: 6,
                    alignItems: "center",
                    marginTop: 2,
                  }}
                >
                  {statusBadge(d.status)}
                  {d.num_chunks > 0 && <span>{d.num_chunks} chunks</span>}
                  {d.status === "ERROR" && d.error_msg && (
                    <span style={{ color: "#DC2626" }}>{d.error_msg}</span>
                  )}
                </div>
              </div>
              {/* Action buttons based on status */}
              {d.status === "EXTRACTED" && (
                <>
                  <button
                    onClick={() => viewExtracted(d)}
                    style={{
                      background: "#EFF6FF",
                      border: "none",
                      borderRadius: 6,
                      padding: "6px 12px",
                      fontSize: 11,
                      fontWeight: 500,
                      color: "#1D4ED8",
                      cursor: "pointer",
                    }}
                  >
                    Review text
                  </button>
                  <button
                    onClick={() => handleProcess(d.id)}
                    disabled={processing}
                    style={{
                      background: "#059669",
                      border: "none",
                      borderRadius: 6,
                      padding: "6px 12px",
                      fontSize: 11,
                      fontWeight: 500,
                      color: "#fff",
                      cursor: "pointer",
                      opacity: processing ? 0.5 : 1,
                    }}
                  >
                    Process
                  </button>
                </>
              )}
              {d.status === "INDEXED" && (
                <>
                  <button
                    onClick={() => viewExtracted(d)}
                    style={{
                      background: "#F3F4F6",
                      border: "none",
                      borderRadius: 6,
                      padding: "6px 10px",
                      fontSize: 11,
                      fontWeight: 500,
                      color: "#374151",
                      cursor: "pointer",
                    }}
                  >
                    Text
                  </button>
                  <button
                    onClick={() => viewChunks(d)}
                    style={{
                      background: "#F3F4F6",
                      border: "none",
                      borderRadius: 6,
                      padding: "6px 10px",
                      fontSize: 11,
                      fontWeight: 500,
                      color: "#374151",
                      cursor: "pointer",
                    }}
                  >
                    Chunks
                  </button>
                </>
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

      {/* ═══ TAB: Extracted text ═══ */}
      {activeTab === "extracted" && (
        <div>
          {!extractedData && (
            <p
              style={{
                color: "#9CA3AF",
                fontSize: 13,
                textAlign: "center",
                padding: 40,
              }}
            >
              Select a document and click "Review text"
            </p>
          )}
          {loadingExtract && (
            <p style={{ color: "#9CA3AF", fontSize: 13 }}>
              Loading extracted text...
            </p>
          )}
          {extractedData && (
            <>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(4,1fr)",
                  gap: 8,
                  marginBottom: 16,
                }}
              >
                {[
                  {
                    label: "Total blocks",
                    value: extractedData.total_blocks,
                    bg: "#EFF6FF",
                    color: "#1D4ED8",
                  },
                  {
                    label: "Text blocks",
                    value: extractedData.text_blocks,
                    bg: "#F0FDF4",
                    color: "#166534",
                  },
                  {
                    label: "Table blocks",
                    value: extractedData.table_blocks,
                    bg: "#FEF3C7",
                    color: "#92400E",
                  },
                  {
                    label: "Total chars",
                    value: extractedData.total_chars?.toLocaleString(),
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
                      style={{ fontSize: 18, fontWeight: 700, color: s.color }}
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
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "#1F2937",
                  marginBottom: 8,
                }}
              >
                Extracted content from "{extractedData.file_name}" —{" "}
                {extractedData.status}
              </div>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  maxHeight: "55vh",
                  overflowY: "auto",
                }}
              >
                {extractedData.blocks.map((block, i) => (
                  <div
                    key={i}
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
                          #{i + 1}
                        </span>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 500,
                            padding: "2px 8px",
                            borderRadius: 4,
                            background:
                              block.type === "table" ? "#FEF3C7" : "#EFF6FF",
                            color:
                              block.type === "table" ? "#92400E" : "#1D4ED8",
                          }}
                        >
                          {block.type}
                        </span>
                        <span style={{ fontSize: 10, color: "#6B7280" }}>
                          page {block.page}
                        </span>
                      </div>
                      <span style={{ fontSize: 10, color: "#6B7280" }}>
                        {block.content.length} chars
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
                        background: "#F9FAFB",
                        padding: "8px 10px",
                        borderRadius: 6,
                        fontFamily: "'Courier New',monospace",
                      }}
                    >
                      {block.content}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* ═══ TAB: Chunks ═══ */}
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
              Select a document and click "Chunks"
            </p>
          )}
          {activeDoc && (
            <>
              {chunkStats && (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(4,1fr)",
                    gap: 8,
                    marginBottom: 16,
                  }}
                >
                  {[
                    {
                      label: "Total",
                      value: chunkStats.total,
                      bg: "#EFF6FF",
                      color: "#1D4ED8",
                    },
                    {
                      label: "Text",
                      value: chunkStats.text,
                      bg: "#F0FDF4",
                      color: "#166534",
                    },
                    {
                      label: "Tables",
                      value: chunkStats.table,
                      bg: "#FEF3C7",
                      color: "#92400E",
                    },
                    {
                      label: "Avg size",
                      value: chunkStats.avg,
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
              {loadingChunks && (
                <p style={{ color: "#9CA3AF", fontSize: 13 }}>Loading...</p>
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
                        background: "#F9FAFB",
                        padding: "8px 10px",
                        borderRadius: 6,
                        fontFamily: "'Courier New',monospace",
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

      {/* ═══ TAB: Chat ═══ */}
      {activeTab === "chat" && (
        <div>
          <div
            style={{
              minHeight: 300,
              maxHeight: "50vh",
              overflowY: "auto",
              marginBottom: 12,
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
                  {msg.sources?.length > 0 && (
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
              <div style={{ display: "flex", marginBottom: 8 }}>
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
