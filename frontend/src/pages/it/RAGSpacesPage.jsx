import React, { useState, useEffect, useRef } from "react";
import "../../styles/it/rag.css";
import {
  createSpace,
  listSpaces,
  deleteSpace,
  updateSpace,
  listDocuments,
  deleteDocument,
  uploadDocument,
  scrapeUrl,
  getLoadedContent,
  parseDocument,
  parseAllDocuments,
  getExtractedContent,
  processDocument,
  processAllDocuments,
  listChunks,
  queryRAG,
  listDepartments,
} from "../../services/ragApi";

const RAGSpacesPage = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [depts, setDepts] = useState([]);
  const [spaces, setSpaces] = useState([]);
  const [activeSpace, setActiveSpace] = useState(null);
  const [docs, setDocs] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [createDept, setCreateDept] = useState("");
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [scraping, setScraping] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const fileRef = useRef(null);
  const [modal, setModal] = useState(null);
  const [modalData, setModalData] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [showJson, setShowJson] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [question, setQuestion] = useState("");
  const [querying, setQuerying] = useState(false);
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
      const [d, s] = await Promise.all([listDepartments(), listSpaces()]);
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
  const refreshDocs = async () => {
    if (!activeSpace) return;
    setDocs(await listDocuments(activeSpace.id));
    const u = await listSpaces();
    setSpaces(u);
    const s = u.find((x) => x.id === activeSpace.id);
    if (s) setActiveSpace(s);
  };
  const loadedCount = docs.filter((d) => d.status === "LOADED").length;
  const extractedCount = docs.filter((d) => d.status === "EXTRACTED").length;
  const openSpace = async (s) => {
    setActiveSpace(s);
    setChatHistory([]);
    setShowSettings(false);
    try {
      setDocs(await listDocuments(s.id));
    } catch (e) {
      setError(e.message);
    }
  };
  const goBack = () => {
    setActiveSpace(null);
    setDocs([]);
    setModal(null);
    setShowSettings(false);
  };
  const handleCreate = async () => {
    if (!newName.trim() || !createDept) return;
    try {
      await createSpace({
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
  const handleSave = async () => {
    if (!activeSpace) return;
    try {
      await updateSpace(activeSpace.id, {
        chunk_strategy: activeSpace.chunk_strategy,
        chunk_size: parseInt(activeSpace.chunk_size),
        chunk_overlap: parseInt(activeSpace.chunk_overlap),
        top_k: parseInt(activeSpace.top_k),
      });
      setSuccess("Saved");
      setShowSettings(false);
      await loadData();
      const u = await listSpaces();
      const s = u.find((x) => x.id === activeSpace.id);
      if (s) setActiveSpace(s);
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
      await uploadDocument(activeSpace.id, f);
      setSuccess(`"${f.name}" loaded`);
      await refreshDocs();
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
      fileRef.current.value = "";
    }
  };
  const handleScrape = async () => {
    if (!urlInput.trim() || !activeSpace) return;
    setScraping(true);
    setError("");
    try {
      await scrapeUrl(activeSpace.id, urlInput);
      setSuccess("Scraped");
      setUrlInput("");
      await refreshDocs();
    } catch (e) {
      setError(e.message);
    } finally {
      setScraping(false);
    }
  };
  const handleParse = async (id) => {
    setParsing(true);
    setError("");
    try {
      await parseDocument(activeSpace.id, id);
      setSuccess("Parsed");
      await refreshDocs();
    } catch (e) {
      setError(e.message);
    } finally {
      setParsing(false);
    }
  };
  const handleParseAll = async () => {
    setParsing(true);
    try {
      const r = await parseAllDocuments(activeSpace.id);
      setSuccess(`${r.parsed} parsed`);
      await refreshDocs();
    } catch (e) {
      setError(e.message);
    } finally {
      setParsing(false);
    }
  };
  const handleProcess = async (id) => {
    setProcessing(true);
    try {
      await processDocument(activeSpace.id, id);
      setSuccess("Indexed");
      await refreshDocs();
    } catch (e) {
      setError(e.message);
    } finally {
      setProcessing(false);
    }
  };
  const handleProcessAll = async () => {
    setProcessing(true);
    try {
      const r = await processAllDocuments(activeSpace.id);
      setSuccess(`${r.processed} processed`);
      await refreshDocs();
    } catch (e) {
      setError(e.message);
    } finally {
      setProcessing(false);
    }
  };
  const handleDeleteDoc = async (id) => {
    try {
      await deleteDocument(activeSpace.id, id);
      setDocs((p) => p.filter((d) => d.id !== id));
    } catch (e) {
      setError(e.message);
    }
  };
  const handleDeleteSpace = async (id) => {
    if (!confirm("Delete?")) return;
    try {
      await deleteSpace(id);
      goBack();
      await loadData();
    } catch (e) {
      setError(e.message);
    }
  };
  const handleQuery = async () => {
    if (!question.trim()) return;
    const q = question;
    setQuestion("");
    setChatHistory((h) => [...h, { role: "user", content: q }]);
    setQuerying(true);
    try {
      const r = await queryRAG(activeSpace.id, q);
      setChatHistory((h) => [
        ...h,
        { role: "assistant", content: r.answer, sources: r.sources },
      ]);
    } catch (e) {
      setChatHistory((h) => [
        ...h,
        { role: "assistant", content: `Error: ${e.message}` },
      ]);
    } finally {
      setQuerying(false);
    }
  };

  const openModal = async (type, doc) => {
    setModalLoading(true);
    setModal(type);
    setShowJson(false);
    try {
      if (type === "loaded")
        setModalData(await getLoadedContent(activeSpace.id, doc.id));
      else if (type === "parsed")
        setModalData(await getExtractedContent(activeSpace.id, doc.id));
      else if (type === "chunks")
        setModalData(await listChunks(activeSpace.id, doc.id));
    } catch (e) {
      setError(e.message);
      setModal(null);
    } finally {
      setModalLoading(false);
    }
  };
  const openChat = () => {
    setModal("chat");
    setModalData(null);
  };
  const closeModal = () => {
    setModal(null);
    setModalData(null);
  };

  const SL = {
    UPLOADING: "Uploading",
    LOADED: "Loaded",
    EXTRACTED: "Parsed",
    PROCESSING: "Processing",
    INDEXED: "Indexed",
    ERROR: "Error",
  };
  const SB = {
    LOADED: "rag-badge-loaded",
    EXTRACTED: "rag-badge-parsed",
    INDEXED: "rag-badge-indexed",
    ERROR: "rag-badge-error",
  };
  const fmt = (t) =>
    t
      ? t
          .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
          .replace(/\n/g, "<br>")
      : "";
  const deptName = (id) => depts.find((x) => x.id === id)?.name || "";

  if (loading)
    return (
      <div className="rag-page">
        <div className="rag-empty-state">Loading…</div>
      </div>
    );

  /* ════════════════════════════════
     PAGE 1: Space cards grid
     ════════════════════════════════ */
  if (!activeSpace)
    return (
      <div className="rag-page">
        <div className="rag-main">
          {error && <div className="rag-toast rag-toast-error">{error}</div>}
          {success && (
            <div className="rag-toast rag-toast-success">{success}</div>
          )}

          <div className="rag-header">
            <div>
              <div className="rag-header-title">RAG Spaces</div>
              <div className="rag-header-desc">
                Build and configure RAG pipelines
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
              <div className="rag-create-title">New Space</div>
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
                placeholder="Description (optional)"
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
                        <div className="rag-space-card-badge">
                          {s.chunk_strategy}
                        </div>
                        <div className="rag-space-card-name">{s.name}</div>
                        <div className="rag-space-card-desc">
                          {s.description || "No description"}
                        </div>
                        <div className="rag-space-card-footer">
                          <span>📄 {s.num_documents || 0} docs</span>
                          <span>🧩 {s.num_chunks || 0} chunks</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
            {spaces.length === 0 && (
              <div className="rag-empty-state">No spaces yet</div>
            )}
          </div>
        </div>
      </div>
    );

  /* ════════════════════════════════
     PAGE 2: Inside a space
     ════════════════════════════════ */
  return (
    <div className="rag-page">
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
            <span className="rag-config-tag">
              {activeSpace.chunk_strategy} · {activeSpace.chunk_size}
            </span>
            <span className="rag-config-tag">
              {activeSpace.num_chunks} chunks
            </span>
            <button
              className="rag-btn rag-btn-blue rag-btn-sm"
              onClick={openChat}
            >
              💬 Chat
            </button>
            <button
              className="rag-btn rag-btn-sm"
              onClick={() => setShowSettings(!showSettings)}
            >
              ⚙ Settings
            </button>
            <button
              className="rag-btn rag-btn-sm rag-btn-red"
              onClick={() => handleDeleteSpace(activeSpace.id)}
            >
              Delete
            </button>
          </div>
        </div>

        {showSettings && (
          <div className="rag-create-card" style={{ marginBottom: 16 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 14,
              }}
            >
              <div className="rag-create-title" style={{ margin: 0 }}>
                Configuration
              </div>
              <button
                className="rag-btn rag-btn-sm"
                onClick={() => setShowSettings(false)}
              >
                ✕
              </button>
            </div>
            <div className="rag-create-label">Chunking Strategy</div>
            <div className="rag-strategy-cards">
              {[
                { k: "FIXED", n: "Fixed", d: "Cut every N characters" },
                { k: "SEMANTIC", n: "Semantic", d: "Cut when topic changes" },
                {
                  k: "HIERARCHICAL",
                  n: "Hierarchical",
                  d: "Parent + child chunks",
                },
              ].map((s) => (
                <button
                  key={s.k}
                  className={`rag-strategy-card ${activeSpace.chunk_strategy === s.k ? "active" : ""}`}
                  onClick={() =>
                    setActiveSpace({ ...activeSpace, chunk_strategy: s.k })
                  }
                >
                  <div className="rag-strategy-name">{s.n}</div>
                  <div className="rag-strategy-desc">{s.d}</div>
                </button>
              ))}
            </div>
            <div className="rag-settings-row">
              <div className="rag-settings-col">
                <div className="rag-create-label">Chunk size</div>
                <input
                  className="rag-create-input"
                  type="number"
                  value={activeSpace.chunk_size}
                  onChange={(e) =>
                    setActiveSpace({
                      ...activeSpace,
                      chunk_size: e.target.value,
                    })
                  }
                  style={{ marginBottom: 0 }}
                />
                <div className="rag-settings-hint">256–1024</div>
              </div>
              <div className="rag-settings-col">
                <div className="rag-create-label">Overlap</div>
                <input
                  className="rag-create-input"
                  type="number"
                  value={activeSpace.chunk_overlap}
                  onChange={(e) =>
                    setActiveSpace({
                      ...activeSpace,
                      chunk_overlap: e.target.value,
                    })
                  }
                  style={{ marginBottom: 0 }}
                />
                <div className="rag-settings-hint">20–100</div>
              </div>
              <div className="rag-settings-col">
                <div className="rag-create-label">Top-K</div>
                <input
                  className="rag-create-input"
                  type="number"
                  value={activeSpace.top_k}
                  onChange={(e) =>
                    setActiveSpace({ ...activeSpace, top_k: e.target.value })
                  }
                  style={{ marginBottom: 0 }}
                />
                <div className="rag-settings-hint">Results per query</div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="rag-btn rag-btn-blue" onClick={handleSave}>
                Save
              </button>
              <button
                className="rag-btn"
                onClick={() => setShowSettings(false)}
              >
                Cancel
              </button>
            </div>
            <div className="rag-settings-note">
              Changes apply to new documents only.
            </div>
          </div>
        )}

        <div className="rag-upload-bar">
          <input
            type="file"
            ref={fileRef}
            onChange={handleUpload}
            style={{ display: "none" }}
            accept=".pdf,.docx,.txt,.md,.csv,.xlsx,.xls,.html,.htm,.json,.xml,.pptx"
          />
          <button
            className="rag-btn rag-btn-dark"
            onClick={() => fileRef.current.click()}
            disabled={uploading}
          >
            {uploading ? "Uploading…" : "📁 Upload"}
          </button>
          <input
            className="rag-url-input"
            placeholder="Paste a URL to scrape…"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleScrape()}
          />
          <button
            className="rag-btn"
            onClick={handleScrape}
            disabled={scraping}
          >
            {scraping ? "…" : "🔗 Scrape"}
          </button>
          {loadedCount > 0 && (
            <button
              className="rag-btn rag-btn-sm"
              onClick={handleParseAll}
              disabled={parsing}
            >
              {parsing ? "…" : `Parse all (${loadedCount})`}
            </button>
          )}
          {extractedCount > 0 && (
            <button
              className="rag-btn rag-btn-dark rag-btn-sm"
              onClick={handleProcessAll}
              disabled={processing}
            >
              {processing ? "…" : `Process all (${extractedCount})`}
            </button>
          )}
        </div>

        <div className="rag-docs-list">
          {docs.length === 0 && (
            <div className="rag-empty-state">
              No documents yet — upload a file or scrape a URL
            </div>
          )}
          {docs.map((d) => (
            <div key={d.id} className="rag-doc-card">
              <div className="rag-doc-icon">
                {d.source_type === "url"
                  ? "URL"
                  : (d.file_type || "?").toUpperCase()}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="rag-doc-name">{d.file_name}</div>
                <div className="rag-doc-meta">
                  {d.file_size ? `${(d.file_size / 1024).toFixed(1)} KB` : ""}
                  {d.num_chunks > 0 && ` · ${d.num_chunks} chunks`}
                </div>
                <div className="rag-doc-btns">
                  {d.has_loaded_content && (
                    <button
                      className="rag-btn rag-btn-xs"
                      onClick={() => openModal("loaded", d)}
                    >
                      View loaded
                    </button>
                  )}
                  {d.status === "LOADED" && (
                    <button
                      className="rag-btn rag-btn-xs rag-btn-blue"
                      onClick={() => handleParse(d.id)}
                      disabled={parsing}
                    >
                      Parse
                    </button>
                  )}
                  {d.has_extracted_content && (
                    <button
                      className="rag-btn rag-btn-xs"
                      onClick={() => openModal("parsed", d)}
                    >
                      View parsed
                    </button>
                  )}
                  {d.status === "EXTRACTED" && (
                    <button
                      className="rag-btn rag-btn-xs rag-btn-dark"
                      onClick={() => handleProcess(d.id)}
                      disabled={processing}
                    >
                      Process
                    </button>
                  )}
                  {d.status === "INDEXED" && (
                    <button
                      className="rag-btn rag-btn-xs"
                      onClick={() => openModal("chunks", d)}
                    >
                      View chunks
                    </button>
                  )}
                </div>
              </div>
              <span className={`rag-badge ${SB[d.status] || ""}`}>
                {SL[d.status] || d.status}
              </span>
              <button
                className="rag-doc-del"
                onClick={() => handleDeleteDoc(d.id)}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* ════════ MODAL ════════ */}
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
                {modal === "loaded" && "Loaded Text"}
                {modal === "parsed" && "Parsed Document"}
                {modal === "chunks" && "Chunks"}
                {modal === "chat" && "Chat with documents"}
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                {modal === "parsed" && (
                  <button
                    className={`rag-btn rag-btn-sm ${showJson ? "rag-btn-dark" : ""}`}
                    onClick={() => setShowJson(!showJson)}
                  >
                    {showJson ? "Blocks" : "JSON"}
                  </button>
                )}
                <button className="rag-btn rag-btn-sm" onClick={closeModal}>
                  ✕ Close
                </button>
              </div>
            </div>
            <div className="rag-modal-body">
              {modalLoading && <div className="rag-empty-state">Loading…</div>}

              {/* LOADED */}
              {modal === "loaded" && modalData && !modalLoading && (
                <>
                  <div className="rag-stats rag-stats-4">
                    {[
                      { l: "Type", v: modalData.file_type },
                      { l: "Category", v: modalData.category },
                      { l: "Pages", v: modalData.num_pages },
                      {
                        l: "Characters",
                        v: modalData.total_chars?.toLocaleString(),
                      },
                    ].map((s, i) => (
                      <div key={i} className="rag-stat">
                        <div className="rag-stat-label">{s.l}</div>
                        <div className="rag-stat-value">{s.v}</div>
                      </div>
                    ))}
                  </div>
                  <div className="rag-raw-text">
                    {modalData.raw_text || "Empty"}
                  </div>
                </>
              )}

              {/* PARSED */}
              {modal === "parsed" && modalData && !modalLoading && (
                <>
                  <div className="rag-stats rag-stats-4">
                    {[
                      { l: "Sections", v: modalData.total_sections },
                      { l: "Tables", v: modalData.total_tables },
                      {
                        l: "Characters",
                        v: modalData.total_chars?.toLocaleString(),
                      },
                      { l: "OCR", v: modalData.ocr_quality },
                    ].map((s, i) => (
                      <div key={i} className="rag-stat">
                        <div className="rag-stat-label">{s.l}</div>
                        <div className="rag-stat-value">{s.v}</div>
                      </div>
                    ))}
                  </div>
                  {modalData.ocr_issues?.length > 0 && (
                    <div className="rag-ocr-warn">
                      {modalData.ocr_issues.join(" · ")}
                    </div>
                  )}
                  {showJson ? (
                    <div className="rag-json">
                      <pre>
                        {JSON.stringify(modalData.parsed_document, null, 2)}
                      </pre>
                    </div>
                  ) : (
                    <>
                      {modalData.parsed_document?.sections?.map((sec, i) => (
                        <div key={`s${i}`} className="rag-block">
                          <div className="rag-block-header">
                            <div className="rag-heading-tag">
                              <span className="rag-block-tag">
                                Section {i + 1}
                              </span>
                              {sec.heading && (
                                <span style={{ fontSize: 13, fontWeight: 600 }}>
                                  {sec.heading}
                                </span>
                              )}
                              <span className="rag-h-level">H{sec.level}</span>
                            </div>
                            <span className="rag-block-meta">
                              p.{sec.page} · {sec.content?.length}c
                            </span>
                          </div>
                          <pre className="rag-block-content">{sec.content}</pre>
                        </div>
                      ))}
                      {modalData.parsed_document?.tables?.map((tab, i) => (
                        <div
                          key={`t${i}`}
                          className="rag-block rag-block-table"
                        >
                          <div className="rag-block-header">
                            <span
                              className="rag-block-tag"
                              style={{
                                background: "#FEF3C7",
                                color: "#92400E",
                              }}
                            >
                              Table {i + 1} — {tab.num_rows}×{tab.num_cols}
                            </span>
                            <span className="rag-block-meta">p.{tab.page}</span>
                          </div>
                          {tab.headers?.length > 0 && (
                            <div
                              style={{
                                fontSize: 11,
                                color: "#92400E",
                                marginBottom: 6,
                              }}
                            >
                              {tab.headers.join(", ")}
                            </div>
                          )}
                          <pre className="rag-block-content rag-block-content-mono">
                            {tab.content}
                          </pre>
                        </div>
                      ))}
                      {modalData.parsed_document?.images?.map((img, i) => (
                        <div key={`i${i}`} className="rag-block">
                          <div className="rag-block-header">
                            <span className="rag-block-tag">Image {i + 1}</span>
                            <span className="rag-block-meta">p.{img.page}</span>
                          </div>
                          {img.caption && (
                            <div style={{ fontSize: 13 }}>{img.caption}</div>
                          )}
                          {img.ocr_text && (
                            <div style={{ fontSize: 12, color: "#525252" }}>
                              OCR: {img.ocr_text}
                            </div>
                          )}
                        </div>
                      ))}
                    </>
                  )}
                </>
              )}

              {/* CHUNKS */}
              {modal === "chunks" && modalData && !modalLoading && (
                <>
                  <div className="rag-stats rag-stats-3">
                    {[
                      { l: "Chunks", v: modalData.length },
                      {
                        l: "Avg length",
                        v: Math.round(
                          modalData.reduce((s, c) => s + c.content.length, 0) /
                            (modalData.length || 1),
                        ),
                      },
                      {
                        l: "Total chars",
                        v: modalData
                          .reduce((s, c) => s + c.content.length, 0)
                          .toLocaleString(),
                      },
                    ].map((s, i) => (
                      <div key={i} className="rag-stat">
                        <div className="rag-stat-label">{s.l}</div>
                        <div className="rag-stat-value">{s.v}</div>
                      </div>
                    ))}
                  </div>
                  {modalData.map((c) => (
                    <div key={c.id} className="rag-block">
                      <div className="rag-block-header">
                        <span className="rag-block-tag">
                          Chunk {c.chunk_index + 1}
                        </span>
                        <span className="rag-block-meta">
                          p.{c.page} · {c.content.length}c
                        </span>
                      </div>
                      <pre className="rag-block-content">{c.content}</pre>
                    </div>
                  ))}
                </>
              )}

              {/* CHAT */}
              {modal === "chat" && (
                <div className="rag-chat-body">
                  <div className="rag-chat-messages">
                    {chatHistory.length === 0 && (
                      <div className="rag-empty-state">
                        Ask a question about your documents
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
                          {m.role === "user" ? (
                            m.content
                          ) : (
                            <div
                              dangerouslySetInnerHTML={{
                                __html: fmt(m.content),
                              }}
                            />
                          )}
                          {m.sources?.length > 0 && (
                            <div className="rag-chat-sources">
                              {m.sources.map((s, j) => (
                                <div key={j}>
                                  📄 {s.document} (p.{s.page}, {s.score})
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                    {querying && (
                      <div className="rag-chat-msg rag-chat-msg-ai">
                        <div className="rag-chat-typing">Thinking…</div>
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
                      placeholder="Ask a question…"
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

export default RAGSpacesPage;
