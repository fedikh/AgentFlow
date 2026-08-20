import React, { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import {
  crawlWebsite, deleteDocument, getChunkingCatalog, getExtractedContent,
  getLoadedContent, getSpace, ingestRss, ingestSitemap, listChunks,
  listDocuments, loadAndParseAll, loadAndParseDocument, parseAllDocuments,
  parseDocument, parseRawHtml, processAllDocuments, processDocument, scrapeUrl,
  setDocumentChunking, setDocumentExtractImages, updateSpace, uploadDocument,
  uploadFromDrive,
} from "../../../services/ragApi";
import { ensureKnowledgeSpace } from "../../../services/dataAgentApi";
import UploadsPanel from "../rag/UploadsPanel";
import ChunkingConfig from "../rag/ChunkingConfig";
import DocModal from "../rag/DocModal";
import { ink } from "../../dashboard/tokens";

/*
 * DocumentsPanel — the agent's business documents.
 *
 * NO ingestion code lives here. An agent's documents are a hidden RAG space,
 * so this panel renders the RAG components against the RAG endpoints:
 *
 *   UploadsPanel    upload · load+parse · view loaded / parsed · delete
 *   ChunkingConfig  the FULL per-format strategy catalog + indexing
 *   DocModal        the loaded-text, parsed-document and chunks viewers
 *
 * One implementation, one behaviour, one place to fix.
 */
const noop = () => {};

/* The only formats a knowledge base accepts. Shown to the user, given to the
   file picker, and enforced on upload (drag-drop / "All files" can bypass the
   picker filter). */
const ACCEPTED = [
  { label: "PDF (.pdf)", ext: ["pdf"] },
  { label: "Word (.docx)", ext: ["docx"] },
  { label: "Text (.txt)", ext: ["txt"] },
  { label: "Markdown (.md)", ext: ["md", "markdown"] },
  { label: "CSV (.csv)", ext: ["csv"] },
  { label: "HTML · Web pages", ext: ["html", "htm"] },
];
const ACCEPT_ATTR = ACCEPTED.flatMap((f) => f.ext.map((e) => `.${e}`)).join(",");
const ALLOWED_EXT = new Set(ACCEPTED.flatMap((f) => f.ext));
const extOf = (name) => (name || "").split(".").pop().toLowerCase();

export default function DocumentsPanel({ source, setError }) {
  const [spaceId, setSpaceId] = useState(source.knowledge_space_id || null);
  const [space, setSpace] = useState(null);
  const [cfg, setCfg] = useState(null);          // the space's chunking config
  const [docs, setDocs] = useState([]);
  const [catalog, setCatalog] = useState(null);  // full chunking catalog
  const [busy, setBusy] = useState("");
  const fileRef = useRef(null);
  const folderRef = useRef(null);

  /* modal state — the same shape the RAG page uses */
  const [modal, setModal] = useState(null);
  const [modalData, setModalData] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [showJson, setShowJson] = useState(false);

  const refresh = async (sid = spaceId) => {
    if (!sid) return;
    try {
      const [d, s] = await Promise.all([listDocuments(sid), getSpace(sid)]);
      setDocs(d);
      setSpace(s);
      setCfg((c) => c || { ...s });
    } catch (e) { setError(e.message); }
  };

  useEffect(() => {
    (async () => {
      try {
        const { space_id: sid } = await ensureKnowledgeSpace(source.id);
        setSpaceId(sid);
        await refresh(sid);
        getChunkingCatalog().then(setCatalog).catch(() => {});
      } catch (e) { setError(e.message); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source.id]);

  /* ── handlers: the RAG endpoints, nothing else ── */
  // Refresh in `finally`: a partial batch (some files rejected) must still show
  // the ones that went through.
  const run = (flag, fn) => async (...args) => {
    setBusy(flag);
    setError("");
    try { await fn(...args); }
    catch (e) { setError(e.message); }
    finally { await refresh(); setBusy(""); }
  };

  const handleUpload = run("uploading", async (e) => {
    const picked = Array.from(e.target.files || []);
    e.target.value = "";
    const ok = picked.filter((f) => ALLOWED_EXT.has(extOf(f.name)));
    const bad = picked.filter((f) => !ALLOWED_EXT.has(extOf(f.name)));
    for (const f of ok) await uploadDocument(spaceId, f);
    if (bad.length)
      throw new Error(
        `Not supported here: ${bad.map((f) => f.name).join(", ")} — ` +
        `this knowledge base accepts PDF, Word, Text, Markdown, CSV and HTML only.`,
      );
  });

  const handleDriveUpload = run("uploading", (fileId, token) =>
    uploadFromDrive(spaceId, fileId, token));

  /* web pages — the same five ingest modes as a RAG space */
  const handleWebIngest = run("scraping", async (mode, p) => {
    if (mode === "url") await scrapeUrl(spaceId, p.url, p.extract_images);
    else if (mode === "html") await parseRawHtml(spaceId, p.html, p.name, p.extract_images);
    else if (mode === "crawl") await crawlWebsite(spaceId, p);
    else if (mode === "sitemap") await ingestSitemap(spaceId, p);
    else if (mode === "rss") await ingestRss(spaceId, p);
  });

  const handleLoadParse = run("parsing", (id) => loadAndParseDocument(spaceId, id));
  const handleLoadParseAll = run("parsing", () => loadAndParseAll(spaceId));
  const handleParse = run("parsing", (id) => parseDocument(spaceId, id));
  const handleParseAll = run("parsing", () => parseAllDocuments(spaceId));
  const handleDeleteDoc = run("", (id) => deleteDocument(spaceId, id));
  const handleSetExtractImages = run("", (id, on) =>
    setDocumentExtractImages(spaceId, id, on));

  /* chunking config lives on the space — persist before indexing */
  const setC = (key, value) => setCfg((c) => ({ ...c, [key]: value }));

  const persistChunkCfg = async (extra = {}) => {
    const payload = {
      chunk_mode: cfg?.chunk_mode,
      chunk_strategy: cfg?.chunk_strategy,
      chunk_params: cfg?.chunk_params,
      chunk_format_map: cfg?.chunk_format_map,
      ...extra,
    };
    await updateSpace(spaceId, payload);
  };

  const handleChunkModeChange = async (mode) => {
    setC("chunk_mode", mode);
    try { await persistChunkCfg({ chunk_mode: mode }); await refresh(); }
    catch (e) { setError(e.message); }
  };

  const handleSetDocChunking = async (docId, strategy, params) => {
    setDocs((p) => p.map((d) => (d.id === docId
      ? { ...d, chunk_strategy: strategy || null, chunk_params: params || {} }
      : d)));
    try { await setDocumentChunking(spaceId, docId, strategy, params); }
    catch (e) { setError(e.message); }
  };

  const handleProcess = run("processing", async (id) => {
    await persistChunkCfg();
    await processDocument(spaceId, id);
  });
  const handleProcessAll = run("processing", async () => {
    await persistChunkCfg();
    await processAllDocuments(spaceId);
  });

  const openModal = async (type, doc) => {
    setModalLoading(true);
    setModal(type);
    setShowJson(false);
    try {
      if (type === "loaded") setModalData(await getLoadedContent(spaceId, doc.id));
      else if (type === "parsed") setModalData(await getExtractedContent(spaceId, doc.id));
      else if (type === "chunks") setModalData(await listChunks(spaceId, doc.id));
    } catch (e) {
      setError(e.message);
      setModal(null);
    } finally {
      setModalLoading(false);
    }
  };

  if (!spaceId || !cfg) {
    return (
      <div className="rag-cfg-hint" style={{ display: "flex", alignItems: "center", gap: 7 }}>
        <Loader2 size={13} className="spin" /> Preparing the knowledge base…
      </div>
    );
  }

  const counts = {
    uploadingCount: docs.filter((d) => d.status === "UPLOADING").length,
    loadedCount: docs.filter((d) => d.status === "LOADED").length,
    extractedCount: docs.filter((d) => d.status === "EXTRACTED").length,
  };
  const parsedDocs = docs.filter((d) => d.has_extracted_content);

  return (
    <div style={{ display: "grid", gap: 14 }}>
      <div style={{ background: "#F8FAFC", border: `1px solid ${ink.line}`,
                    borderRadius: 9, padding: "9px 11px" }}>
        <div style={{ fontSize: 11.5, color: ink.muted, marginBottom: 6 }}>
          <strong style={{ color: ink.primary }}>Accepted formats only</strong> —
          each file is loaded, parsed, chunked with the strategy you pick for its
          format, then indexed. Same pipeline as a RAG space.
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
          {ACCEPTED.map((f) => (
            <span key={f.label} style={{ fontSize: 10.5, color: ink.primary,
                                         background: "#fff", borderRadius: 5,
                                         border: `1px solid ${ink.line}`,
                                         padding: "2px 7px" }}>{f.label}</span>
          ))}
        </div>
      </div>

      {/* upload · load+parse · view loaded/parsed · delete */}
      <UploadsPanel
        docs={docs}
        fileRef={fileRef}
        folderRef={folderRef}
        uploading={busy === "uploading"}
        scraping={busy === "scraping"}
        parsing={busy === "parsing"}
        accept={ACCEPT_ATTR}
        handleUpload={handleUpload}
        handleFolderUpload={handleUpload}
        handleDriveUpload={handleDriveUpload}
        handleWebIngest={handleWebIngest}
        handleLoadParse={handleLoadParse}
        handleLoadParseAll={handleLoadParseAll}
        handleParse={handleParse}
        handleParseAll={handleParseAll}
        handleDeleteDoc={handleDeleteDoc}
        openModal={openModal}
        counts={counts}
        handleSetExtractImages={handleSetExtractImages}
        spaceId={spaceId}
        isOwner
        editable
      />

      {/* the RAG chunking panel: full per-format strategy catalog + indexing.
          Wrapped so its fragment stays one block inside the grid. */}
      <div style={{ border: `1px solid ${ink.line}`, borderRadius: 10,
                    padding: "12px 13px 14px" }}>
        <ChunkingConfig
          cfg={cfg}
          setC={setC}
          catalog={catalog}
          parsedDocs={parsedDocs}
          extractedCount={counts.extractedCount}
          handleSetDocChunking={handleSetDocChunking}
          handleChunkModeChange={handleChunkModeChange}
          handleProcess={handleProcess}
          handleProcessAll={handleProcessAll}
          processing={busy === "processing"}
          openModal={openModal}
          canBuild
          onGoEmbed={null}
        />
      </div>

      {space?.num_chunks > 0 && (
        <div className="rag-cfg-hint" style={{ margin: 0 }}>
          <strong>{space.num_chunks} chunks</strong> indexed across{" "}
          {docs.filter((d) => d.status === "INDEXED").length} document(s) — these
          are searched with the same hybrid retrieval as your RAG spaces.
        </div>
      )}

      {/* loaded text · parsed document · chunks — the RAG viewers (read-only) */}
      <DocModal
        modal={modal}
        modalData={modalData}
        modalLoading={modalLoading}
        closeModal={() => { setModal(null); setModalData(null); }}
        showJson={showJson}
        setShowJson={setShowJson}
        editMode={false}
        editDoc={null}
        savingEdit={false}
        removeBlock={noop}
        spaceId={spaceId}
        canEdit={false}
      />
    </div>
  );
}
