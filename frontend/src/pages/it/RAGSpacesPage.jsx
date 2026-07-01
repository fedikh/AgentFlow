import React, { useState, useEffect, useRef } from "react";
import "../../styles/it/rag.css";
import "../../styles/it/ragside.css";
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
  updateExtractedContent,
  processDocument,
  processAllDocuments,
  listChunks,
  queryRAG,
  listDepartments,
  uploadFromDrive,
  loadAndParseDocument,
  loadAndParseAll,
  getEmbeddingModels,
  getLLMModels,
  setDocumentStrategy,
} from "../../services/ragApi";
import { openGooglePicker } from "../../services/useGooglePicker";
import { useParams, useNavigate } from "react-router-dom";
import SpacesGrid from "../../components/it/rag/SpacesGrid";
import RightSidebar from "../../components/it/rag/RightSidebar";
import FlowPanel from "../../components/it/rag/FlowPanel";
import UploadsPanel from "../../components/it/rag/UploadsPanel";
import ConfigPanel from "../../components/it/rag/ConfigPanel";
import DocModal from "../../components/it/rag/DocModal";

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
  const [editMode, setEditMode] = useState(false);
  const [editDoc, setEditDoc] = useState(null);
  const [savingEdit, setSavingEdit] = useState(false);

  const [panel, setPanel] = useState("uploads");
  const [cfg, setCfg] = useState(null);
  const [savingCfg, setSavingCfg] = useState(false);
  const [embedModels, setEmbedModels] = useState([]);
  const [llmModels, setLlmModels] = useState([]);
  const [llmState, setLlmState] = useState({ available: true, error: "" });
  const [loadingLlm, setLoadingLlm] = useState(false);

  const { spaceId } = useParams();
  const navigate = useNavigate();

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

  useEffect(() => {
    getEmbeddingModels()
      .then((r) => setEmbedModels(r.models || []))
      .catch(() => setEmbedModels([]));
  }, []);
  useEffect(() => {
    if (!cfg) return;
    const provider = cfg.llm_provider || "GROQ";
    setLoadingLlm(true);
    getLLMModels(provider)
      .then((r) => {
        setLlmModels(r.models || []);
        setLlmState({ available: r.available, error: r.error || "" });
      })
      .catch(() => {
        setLlmModels([]);
        setLlmState({ available: false, error: "Loading error" });
      })
      .finally(() => setLoadingLlm(false));
  }, [cfg?.llm_provider]);

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
    if (s) {
      setActiveSpace(s);
      setCfg({ ...s });
    }
  };

  const uploadingCount = docs.filter((d) => d.status === "UPLOADING").length;
  const loadedCount = docs.filter((d) => d.status === "LOADED").length;
  const extractedCount = docs.filter((d) => d.status === "EXTRACTED").length;

  const openSpace = async (s) => {
    setActiveSpace(s);
    setCfg({ ...s });
    setPanel("uploads");
    setChatHistory([]);
    navigate(`/it/rag/${s.id}`);
    try {
      setDocs(await listDocuments(s.id));
    } catch (e) {
      setError(e.message);
    }
  };

  // Restore the space from the URL on load / refresh
  useEffect(() => {
    if (spaceId && spaces.length > 0 && !activeSpace) {
      const s = spaces.find((x) => x.id === spaceId);
      if (s) openSpace(s);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spaceId, spaces]);
  const goBack = () => {
    setActiveSpace(null);
    setDocs([]);
    setModal(null);
    setCfg(null);
    navigate("/it/rag");
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

  const setC = (f, v) => setCfg((c) => ({ ...c, [f]: v }));
  const saveCfg = async () => {
    setSavingCfg(true);
    try {
      const payload = {
        chunk_mode: cfg.chunk_mode,
        chunk_strategy: cfg.chunk_strategy,
        chunk_size: parseInt(cfg.chunk_size),
        chunk_overlap: parseInt(cfg.chunk_overlap),
        embedding_provider: cfg.embedding_provider,
        embedding_model: cfg.embedding_model,
        llm_provider: cfg.llm_provider,
        llm_model: cfg.llm_model,
        llm_temperature: parseFloat(cfg.llm_temperature),
        top_k: parseInt(cfg.top_k),
        semantic_weight: parseFloat(cfg.semantic_weight),
        reranking_enabled: !!cfg.reranking_enabled,
        system_prompt: cfg.system_prompt || null,
        // ── LLM source (new) ──
        llm_provider_id: cfg.llm_provider_id || null,
        llm_base_url: cfg.llm_base_url || null,
      };
      // Only send the key if the IT typed a new one (it's write-only)
      if (cfg.llm_api_key) payload.llm_api_key = cfg.llm_api_key;

      await updateSpace(activeSpace.id, payload);
      setSuccess("Configuration saved");

      // clear the typed key from local state after saving
      setCfg((c) => ({ ...c, llm_api_key: "" }));

      const u = await listSpaces();
      const s = u.find((x) => x.id === activeSpace.id);
      if (s) {
        setActiveSpace(s);
        setCfg((c) => ({ ...s, llm_api_key: "" }));
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingCfg(false);
    }
  };

  const handleUpload = async (e) => {
    const files = Array.from(e.target.files);
    if (!files.length || !activeSpace) return;
    setUploading(true);
    setError("");
    try {
      for (const f of files) await uploadDocument(activeSpace.id, f);
      setSuccess(`${files.length} file(s) uploaded`);
      await refreshDocs();
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
      fileRef.current.value = "";
    }
  };
  const handleDriveUpload = async () => {
    const files = await openGooglePicker();
    if (!files || !files.length) return;
    setUploading(true);
    try {
      for (const f of files)
        await uploadFromDrive(activeSpace.id, f.fileId, f.accessToken);
      setSuccess(`${files.length} file(s) imported from Drive`);
      await refreshDocs();
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
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
  const handleLoadParse = async (docId) => {
    setParsing(true);
    setError("");
    try {
      await loadAndParseDocument(activeSpace.id, docId);
      setSuccess("Loaded & parsed");
      await refreshDocs();
    } catch (e) {
      setError(e.message);
    } finally {
      setParsing(false);
    }
  };
  const handleLoadParseAll = async () => {
    setParsing(true);
    setError("");
    try {
      const r = await loadAndParseAll(activeSpace.id);
      setSuccess(`${r.processed} loaded & parsed`);
      await refreshDocs();
    } catch (e) {
      setError(e.message);
    } finally {
      setParsing(false);
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
  const handleSetDocStrategy = async (docId, strategy) => {
    try {
      await setDocumentStrategy(activeSpace.id, docId, strategy);
      setDocs((p) =>
        p.map((d) => (d.id === docId ? { ...d, chunk_strategy: strategy } : d)),
      );
    } catch (e) {
      setError(e.message);
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
    setEditMode(false);
    setEditDoc(null);
  };

  const startEdit = () => {
    setEditDoc({
      id: modalData.document_id,
      parsed_document: JSON.parse(JSON.stringify(modalData.parsed_document)),
    });
    setEditMode(true);
    setShowJson(false);
  };
  const cancelEdit = () => {
    setEditMode(false);
    setEditDoc(null);
  };
  const editField = (kind, i, field, value) => {
    setEditDoc((prev) => {
      const next = { ...prev, parsed_document: { ...prev.parsed_document } };
      const arr = [...next.parsed_document[kind]];
      arr[i] = { ...arr[i], [field]: value };
      next.parsed_document[kind] = arr;
      return next;
    });
  };
  const removeBlock = (kind, i) => {
    setEditDoc((prev) => {
      const next = { ...prev, parsed_document: { ...prev.parsed_document } };
      next.parsed_document[kind] = next.parsed_document[kind].filter(
        (_, idx) => idx !== i,
      );
      return next;
    });
  };
  const addSection = () => {
    setEditDoc((prev) => {
      const next = { ...prev, parsed_document: { ...prev.parsed_document } };
      next.parsed_document.sections = [
        ...(next.parsed_document.sections || []),
        { heading: "", content: "", level: 1, page: 1, font_size: null },
      ];
      return next;
    });
  };
  const saveEdit = async () => {
    setSavingEdit(true);
    try {
      const pd = editDoc.parsed_document;
      const payload = {
        title: pd.title || "",
        sections: pd.sections || [],
        tables: pd.tables || [],
        images: pd.images || [],
        metadata: pd.metadata || {},
      };
      const updated = await updateExtractedContent(
        activeSpace.id,
        editDoc.id,
        payload,
      );
      setModalData(updated);
      setEditMode(false);
      setEditDoc(null);
      setSuccess("Parsed content updated. Re-process to rebuild chunks.");
      await refreshDocs();
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingEdit(false);
    }
  };

  const deptName = (id) => depts.find((x) => x.id === id)?.name || "";

  if (loading)
    return (
      <div className="rag-page">
        <div className="rag-empty-state">Loading…</div>
      </div>
    );

  // PAGE 1 : cards grid
  if (!activeSpace)
    return (
      <div className="rag-page">
        {error && <div className="rag-toast rag-toast-error">{error}</div>}
        {success && (
          <div className="rag-toast rag-toast-success">{success}</div>
        )}
        <SpacesGrid
          depts={depts}
          spaces={spaces}
          openSpace={openSpace}
          showCreate={showCreate}
          setShowCreate={setShowCreate}
          createDept={createDept}
          setCreateDept={setCreateDept}
          newName={newName}
          setNewName={setNewName}
          newDesc={newDesc}
          setNewDesc={setNewDesc}
          handleCreate={handleCreate}
        />
      </div>
    );

  // PAGE 2 : space interior
  return (
    <div className="rag-page">
      <div className="rag-space-layout">
        <div className="rag-space-content">
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
                className="rag-btn rag-btn-sm rag-btn-red"
                onClick={() => handleDeleteSpace(activeSpace.id)}
              >
                Delete
              </button>
            </div>
          </div>

          {panel === "uploads" && (
            <UploadsPanel
              docs={docs}
              fileRef={fileRef}
              uploading={uploading}
              scraping={scraping}
              parsing={parsing}
              processing={processing}
              urlInput={urlInput}
              setUrlInput={setUrlInput}
              handleUpload={handleUpload}
              handleDriveUpload={handleDriveUpload}
              handleScrape={handleScrape}
              handleLoadParse={handleLoadParse}
              handleLoadParseAll={handleLoadParseAll}
              handleParse={handleParse}
              handleParseAll={handleParseAll}
              handleProcess={handleProcess}
              handleProcessAll={handleProcessAll}
              handleDeleteDoc={handleDeleteDoc}
              openModal={openModal}
              counts={{ uploadingCount, loadedCount, extractedCount }}
              chunkMode={activeSpace.chunk_mode || "FIXED_ALL"}
              handleSetDocStrategy={handleSetDocStrategy}
            />
          )}

          {panel === "flow" && <FlowPanel space={activeSpace} />}

          {panel !== "uploads" && panel !== "flow" && (
            <ConfigPanel
              panel={panel}
              cfg={cfg}
              setC={setC}
              saveCfg={saveCfg}
              savingCfg={savingCfg}
              embedModels={embedModels}
              llmModels={llmModels}
              llmState={llmState}
              loadingLlm={loadingLlm}
            />
          )}
        </div>

        <RightSidebar panel={panel} setPanel={setPanel} />
      </div>

      <DocModal
        modal={modal}
        modalData={modalData}
        modalLoading={modalLoading}
        closeModal={closeModal}
        showJson={showJson}
        setShowJson={setShowJson}
        editMode={editMode}
        editDoc={editDoc}
        setEditDoc={setEditDoc}
        savingEdit={savingEdit}
        startEdit={startEdit}
        cancelEdit={cancelEdit}
        saveEdit={saveEdit}
        editField={editField}
        removeBlock={removeBlock}
        addSection={addSection}
        chatHistory={chatHistory}
        chatEndRef={chatEndRef}
        question={question}
        setQuestion={setQuestion}
        querying={querying}
        handleQuery={handleQuery}
      />
    </div>
  );
};

export default RAGSpacesPage;
