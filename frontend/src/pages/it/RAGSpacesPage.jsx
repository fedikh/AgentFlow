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
  parseRawHtml,
  crawlWebsite,
  ingestSitemap,
  ingestRss,
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
  getChunkingCatalog,
  setDocumentChunking,
  setDocumentExtractImages,
  uploadDocumentImage,
  listDepartmentUsers,
  listVersions,
  saveVersion,
  applyVersion,
  deployVersion,
  deleteVersion,
  deployCurrent,
  pauseDeployment,
} from "../../services/ragApi";
import { openGooglePicker } from "../../services/useGooglePicker";
import { useParams, useNavigate } from "react-router-dom";
import SpacesGrid from "../../components/it/rag/SpacesGrid";
import RightSidebar from "../../components/it/rag/RightSidebar";
import FlowPanel from "../../components/it/rag/FlowPanel";
import UploadsPanel from "../../components/it/rag/UploadsPanel";
import ConfigPanel from "../../components/it/rag/ConfigPanel";
import EvaluationPanel from "../../components/it/rag/EvaluationPanel";
import DocModal from "../../components/it/rag/DocModal";
import VersionsPanel from "../../components/it/rag/VersionsPanel";
import ApiAccessPanel from "../../components/it/rag/ApiAccessPanel";
import DeployModal from "../../components/it/rag/DeployModal";
import { buildMatrix, matrixToCells, matrixToPositional, normCell } from "../../components/it/rag/tableModel";

// Lifecycle pill: Draft / Deployed·Live / Deployed·Private / Editing
const StatusPill = ({ space }) => {
  const status = space?.status || "DRAFT";
  let bg = "#f3f4f6", color = "#6b7280", label = "Draft";
  if (status === "EDITING") {
    bg = "#fde68a"; color = "#92400e"; label = "Editing";
  } else if (status === "ACTIVE" && !space.is_private) {
    bg = "#dcfce7"; color = "#166534"; label = "Deployed · Live";
  } else if (status === "ACTIVE" && space.is_private) {
    bg = "#fef3c7"; color = "#92400e"; label = "Deployed · Private";
  }
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: 0.3,
        textTransform: "uppercase",
        padding: "2px 8px",
        borderRadius: 999,
        background: bg,
        color,
      }}
    >
      {label}
    </span>
  );
};

// ── Which editor a parsed document needs (mirror of DocModal.docKind) ──
const _TREE_TYPES = ["json_object", "json_array", "json_key_value", "json_null", "xml_element"];
function kindOf(pd) {
  const els = pd?.elements || [];
  const st = (pd?.metadata?.source_type || pd?.metadata?.file_type || "").toLowerCase();
  if (st === "csv" || st === "xlsx" || st === "xls" ||
      els.some((e) => e.type === "workbook" || e.type === "sheet") ||
      els.some((e) => e.type === "table" && Array.isArray(e.content?.columns) && e.content.columns.length))
    return "tabular";
  if (st === "json" || st === "xml" || els.some((e) => _TREE_TYPES.includes(e.type)))
    return "tree";
  return "doc";
}

// ── Table grid <-> content helpers (shared by document tables and CSV/Excel) ──
function mdTableToGrid(md) {
  const out = [];
  for (const raw of (md || "").split("\n")) {
    const line = raw.trim();
    if (!line || line.indexOf("|") === -1) continue;
    const noPipes = line.replace(/\|/g, "").trim();
    if (noPipes && /^[:\-\s]+$/.test(noPipes)) continue; // separator row
    let cells = line.split("|");
    if (cells.length && cells[0].trim() === "") cells = cells.slice(1);
    if (cells.length && cells[cells.length - 1].trim() === "") cells = cells.slice(0, -1);
    out.push(cells.map((c) => c.trim()));
  }
  return out;
}
// ── Table cell model (colspan + rowspan) ─────────────────────────────────────
// A table has a fixed column count. `grid` is an array of rows of cells
// { t, cs, rs } (colspan, rowspan). The tableModel engine keeps everything
// consistent; converters below persist `cells` (authoritative) plus a plain
// positional `rows` + `markdown` for display / chunking backward-compat.
function posToMarkdown(headers, pos) {
  const ncols = Math.max(headers.length, ...pos.map((r) => r.length), 1);
  const h = Array.from({ length: ncols }, (_, i) => headers[i] ?? "");
  const lines = ["| " + h.join(" | ") + " |", "|" + Array(ncols).fill("---").join("|") + "|"];
  for (const r of pos) lines.push("| " + Array.from({ length: ncols }, (_, i) => r[i] ?? "").join(" | ") + " |");
  return lines.join("\n");
}
// element table content → editable grid of cells [{t,cs,rs}]
function tableContentToGrid(c) {
  const headers = (c.headers || []).map((h) => (h == null ? "" : String(h)));
  if (Array.isArray(c.cells) && c.cells.length) {
    return { headers, grid: c.cells.map((row) => (Array.isArray(row) ? row : []).map(normCell)) };
  }
  if (Array.isArray(c.rows) && c.rows.length) {
    const grid = c.rows.map((r) => {
      if (Array.isArray(r)) return r.map((v) => normCell({ t: v }));
      if (r && typeof r === "object") {
        const pk = Object.keys(r).filter((k) => /^\d+$/.test(k)).map(Number);
        if (pk.length) { const n = Math.max(...pk) + 1; return Array.from({ length: n }, (_, i) => normCell({ t: r[String(i)] ?? "" })); }
        return Object.values(r).map((v) => normCell({ t: v }));
      }
      return [normCell({ t: r })];
    });
    return { headers, grid };
  }
  const g = mdTableToGrid(c.markdown || "");
  if (g.length) return { headers: g[0], grid: g.slice(1).map((row) => row.map((v) => normCell({ t: v }))) };
  return { headers, grid: [] };
}
// editable grid of cells → element table content (cells + positional rows + md)
function gridToTableContent(headers, grid) {
  const M = buildMatrix(grid);
  const cells = matrixToCells(M);
  const pos = matrixToPositional(M);
  const ncols = M.length ? M[0].length : Math.max(headers.length, 1);
  const H = Array.from({ length: ncols }, (_, i) => headers[i] ?? "");
  const rows = pos.map((r) => { const o = {}; for (let i = 0; i < ncols; i++) o[String(i)] = r[i] ?? ""; return o; });
  return { markdown: posToMarkdown(H, pos), headers: H, cells, rows };
}
// CSV/Excel table element {columns, rows{index,values}} → grid of cells (span 1)
function csvContentToGrid(c) {
  const headers = (c.columns || []).map((col) => String(col?.name ?? ""));
  const grid = (c.rows || []).map((r) => {
    const vals = r && r.values ? r.values : r || {};
    return headers.map((h) => normCell({ t: vals[h] }));
  });
  return { headers, grid };
}
// grid of cells → CSV/Excel content (flattened to columns; merges expand to the
// first column + empties, since CSV/Excel are rectangular).
function gridToCsvContent(prev, headers, grid) {
  const pos = matrixToPositional(buildMatrix(grid));
  const columns = headers.map((h, i) => { const p = (prev.columns || [])[i] || {}; return { name: h, type: p.type || "string", nullable: p.nullable ?? true }; });
  const rows = pos.map((r, ri) => ({ index: ri + 1, values: Object.fromEntries(headers.map((h, ci) => [h, r[ci] ?? ""])) }));
  return { ...prev, columns, rows };
}

// ── Parsed-document editor: convert between the reading-ordered elements[] and
//    the editor "blocks" — ONE block per element (no collapsing) so headings,
//    every paragraph/list item, tables and images survive an edit round-trip
//    intact. Losslessness is the whole point: editing must never merge or drop
//    elements the way the old section-grouping converter did. ──
function blocksFromElements(elements) {
  const els = [...(elements || [])].sort(
    (a, b) => (a.metadata?.reading_order || 0) - (b.metadata?.reading_order || 0),
  );
  return els.map((el) => {
    const t = el.type;
    const c = el.content || {};
    const page = el.location?.page || 1;
    if (t === "heading")
      return { kind: "heading", text: c.text || "", level: el.level || 1, page };
    if (t === "table") {
      const { headers, grid } = tableContentToGrid(c);
      return { kind: "table", page, headers, grid };
    }
    if (t === "image")
      return { kind: "image", page, image_path: c.image_path || "", src: c.src || "", caption: c.caption || "", text_for_embedding: c.text_for_embedding || "", ocr_text: c.ocr_text || "" };
    if (t === "code")
      return { kind: "code", page, text: c.text || "", language: c.language || "" };
    // paragraph / list_item / quote → a text block that REMEMBERS its element
    // type + list level, so saving re-emits the same element type.
    return { kind: "text", elType: t || "paragraph", text: c.text || "", page, listLevel: el.metadata?.list_level || null };
  });
}

// Legacy docs (no elements[]) → one heading block + one text block per section,
// then tables/images. Still 1:1 so nothing is collapsed on save.
function blocksFromLegacy(pd) {
  const blocks = [];
  for (const s of pd.sections || []) {
    if ((s.heading || "").trim())
      blocks.push({ kind: "heading", text: s.heading, level: s.level || 1, page: s.page || 1 });
    if ((s.content || "").trim())
      blocks.push({ kind: "text", elType: "paragraph", text: s.content, page: s.page || 1, listLevel: null });
  }
  for (const t of pd.tables || []) {
    const { headers, grid } = tableContentToGrid(t);
    blocks.push({ kind: "table", page: t.page || 1, headers, grid });
  }
  for (const im of pd.images || [])
    blocks.push({ kind: "image", page: im.page || 1, image_path: im.image_path || "", src: "", caption: im.caption || "", text_for_embedding: im.text_for_embedding || "", ocr_text: im.ocr_text || "" });
  return blocks;
}

// Derive the legacy sections/tables/images from blocks — sent ALONGSIDE elements
// so the save also works on an older backend that only understands those lists.
// Consecutive heading/text blocks fold back into one section here (this list is
// display-only fallback; the authoritative payload is elements[]).
function legacyFromBlocks(blocks) {
  const sections = [], tables = [], images = [];
  let cur = null;
  const flush = () => {
    if (cur && (cur.heading || cur.content)) sections.push(cur);
    cur = null;
  };
  for (const b of blocks || []) {
    if (b.kind === "heading") {
      flush();
      cur = { heading: b.text || "", content: "", level: b.level || 1, page: b.page || 1, font_size: null };
    } else if (b.kind === "text") {
      if (!cur) cur = { heading: "", content: "", level: 1, page: b.page || 1, font_size: null };
      cur.content += (cur.content ? "\n" : "") + (b.elType === "list_item" ? "• " : "") + (b.text || "");
    } else if (b.kind === "code") {
      flush();
      sections.push({ heading: "", content: b.text || "", level: 1, page: b.page || 1, font_size: null });
    } else if (b.kind === "table") {
      flush();
      const tc = gridToTableContent(b.headers || [], b.grid || []);
      tables.push({ content: tc.markdown, headers: tc.headers, rows: tc.rows, num_rows: tc.rows.length, num_cols: tc.headers.length, page: b.page || 1 });
    } else if (b.kind === "image") {
      flush();
      images.push({ caption: b.caption || "", ocr_text: b.ocr_text || "", image_path: b.image_path || "", page: b.page || 1, bbox: [], text_for_embedding: b.text_for_embedding || "" });
    } else if (b.kind === "section") {
      flush();
      sections.push({ heading: b.heading || "", content: b.content || "", level: b.level || 1, page: b.page || 1, font_size: null });
    }
  }
  flush();
  return { sections, tables, images };
}

function elementsFromBlocks(blocks) {
  const els = [];
  let ro = 0;
  const push = (type, content, page, opts = {}) => {
    ro += 1;
    const meta = { reading_order: ro };
    if (opts.listLevel) meta.list_level = opts.listLevel;
    const el = { id: `e${ro}`, type, content, location: { page: page || 1, bbox: [] }, metadata: meta };
    if (opts.level != null) el.level = opts.level;
    els.push(el);
  };
  for (const b of blocks || []) {
    if (b.kind === "heading") {
      push("heading", { text: b.text || "" }, b.page, { level: b.level || 1 });
    } else if (b.kind === "text") {
      push(b.elType || "paragraph", { text: b.text || "" }, b.page, { listLevel: b.listLevel });
    } else if (b.kind === "table") {
      push("table", gridToTableContent(b.headers || [], b.grid || []), b.page);
    } else if (b.kind === "image") {
      push("image", { image_path: b.image_path || "", src: b.src || "", caption: b.caption || "", text_for_embedding: b.text_for_embedding || "", ocr_text: b.ocr_text || "" }, b.page);
    } else if (b.kind === "code") {
      push("code", { text: b.text || "", language: b.language || "" }, b.page);
    } else if (b.kind === "section") {
      // legacy block shape (heading + grouped content)
      if ((b.heading || "").trim()) push("heading", { text: b.heading }, b.page, { level: b.level || 1 });
      if ((b.content || "").trim()) push("paragraph", { text: b.content }, b.page);
    }
  }
  return els;
}

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
  const folderRef = useRef(null);
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
  const [chunkCatalog, setChunkCatalog] = useState(null);
  const [embedModels, setEmbedModels] = useState([]);
  const [llmModels, setLlmModels] = useState([]);
  const [llmState, setLlmState] = useState({ available: true, error: "" });
  const [loadingLlm, setLoadingLlm] = useState(false);

  // ── Access control (Batch 1) ──
  const [deptUsers, setDeptUsers] = useState([]);
  const [loadingDeptUsers, setLoadingDeptUsers] = useState(false);
  // create-modal access picker
  const [createDeptUsers, setCreateDeptUsers] = useState([]);
  const [loadingCreateUsers, setLoadingCreateUsers] = useState(false);
  const [createUserIds, setCreateUserIds] = useState([]);
  // create-modal visibility
  const [createPrivate, setCreatePrivate] = useState(true);

  // ── Versioning + deploy ──
  const [versions, setVersions] = useState([]);
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [deployModal, setDeployModal] = useState(null); // null | {mode, version}
  const [deploying, setDeploying] = useState(false);
  const [pausing, setPausing] = useState(false);


  const { spaceId } = useParams();
  const navigate = useNavigate();

  // A deployed (live) space is LOCKED. To change docs/config/versions the owner
  // must "Stop to edit" (pause) first. editable = can build AND not live.
  const live = activeSpace?.status === "ACTIVE";
  const editable = activeSpace?.can_build !== false && !live;

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
  // Per-format chunking catalog (strategies + params) — loaded once for the UI.
  useEffect(() => {
    getChunkingCatalog()
      .then((c) => setChunkCatalog(c))
      .catch(() => setChunkCatalog(null));
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

  // Load the department's USER-role members for the Access panel
  useEffect(() => {
    const deptId = activeSpace?.department_id;
    if (!deptId) {
      setDeptUsers([]);
      return;
    }
    setLoadingDeptUsers(true);
    listDepartmentUsers(deptId)
      .then((u) => setDeptUsers(u || []))
      .catch(() => setDeptUsers([]))
      .finally(() => setLoadingDeptUsers(false));
  }, [activeSpace?.department_id]);

  // Load the department's users for the CREATE modal access picker
  useEffect(() => {
    if (!createDept) {
      setCreateDeptUsers([]);
      setCreateUserIds([]);
      return;
    }
    setLoadingCreateUsers(true);
    setCreateUserIds([]);
    listDepartmentUsers(createDept)
      .then((u) => setCreateDeptUsers(u || []))
      .catch(() => setCreateDeptUsers([]))
      .finally(() => setLoadingCreateUsers(false));
  }, [createDept]);

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
        // Private → just the owner + IT team; Department → intended for end users
        is_private: createPrivate,
        // Department-member allow-list (only meaningful for a department space).
        // empty = everyone in the department can access once deployed.
        allowed_user_ids: createPrivate ? [] : createUserIds,
      });
      setNewName("");
      setNewDesc("");
      setCreateUserIds([]);
      setCreatePrivate(true);
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
        chunk_params: cfg.chunk_params || {},
        chunk_format_map: cfg.chunk_format_map || {},
        chunk_size: parseInt(cfg.chunk_size),
        chunk_overlap: parseInt(cfg.chunk_overlap),
        embedding_provider: cfg.embedding_provider,
        embedding_model: cfg.embedding_model,
        // ── Embedding source (Batch 6) ──
        embedding_provider_id: cfg.embedding_provider_id || null,
        embedding_base_url: cfg.embedding_base_url || null,
        llm_provider: cfg.llm_provider,
        llm_model: cfg.llm_model,
        llm_temperature: Number.isFinite(parseFloat(cfg.llm_temperature))
          ? parseFloat(cfg.llm_temperature)
          : 0.2,
        llm_max_tokens: parseInt(cfg.llm_max_tokens) || 1024,
        top_k: parseInt(cfg.top_k),
        system_prompt: cfg.system_prompt || null,
        // ── Retrieval engine settings (search mode, reranker, rrf_k…) ──
        retrieval_params: cfg.retrieval_params || {},
        // ── LLM source (new) ──
        llm_provider_id: cfg.llm_provider_id || null,
        llm_base_url: cfg.llm_base_url || null,
        // ── Access control (Batch 1) ──
        allowed_user_ids: cfg.allowed_user_ids || [],
      };
      // Only send keys if the IT typed a new one (they're write-only)
      if (cfg.llm_api_key) payload.llm_api_key = cfg.llm_api_key;
      if (cfg.embedding_api_key) payload.embedding_api_key = cfg.embedding_api_key;
      if (cfg.reranker_api_key) payload.reranker_api_key = cfg.reranker_api_key;

      await updateSpace(activeSpace.id, payload);
      setSuccess("Configuration saved");

      // clear the typed keys from local state after saving
      setCfg((c) => ({ ...c, llm_api_key: "", embedding_api_key: "", reranker_api_key: "" }));

      const u = await listSpaces();
      const s = u.find((x) => x.id === activeSpace.id);
      if (s) {
        setActiveSpace(s);
        setCfg(() => ({ ...s, llm_api_key: "", embedding_api_key: "", reranker_api_key: "" }));
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingCfg(false);
    }
  };

  // ── Sync a space dict returned by the API into local state ──
  // ── Edit a space's name/description from the card's ✎ button ──
  const handleEditSpace = async (spaceId, payload) => {
    try {
      const s = await updateSpace(spaceId, payload);
      setSpaces((list) => list.map((x) => (x.id === spaceId ? { ...x, ...s } : x)));
      setSuccess("Space updated");
    } catch (e) {
      setError(e.message);
      throw e;                 // keep the modal open on failure
    }
  };

  const syncSpace = (s) => {
    if (!s) return;
    setActiveSpace(s);
    setCfg({ ...s, llm_api_key: "", embedding_api_key: "", reranker_api_key: "" });
    setSpaces((list) => list.map((x) => (x.id === s.id ? s : x)));
  };

  // ── Versions ──
  const refreshVersions = async (id) => {
    const sid = id || activeSpace?.id;
    if (!sid) return;
    setLoadingVersions(true);
    try {
      setVersions(await listVersions(sid));
    } catch {
      /* non-fatal — versions just won't render */
    } finally {
      setLoadingVersions(false);
    }
  };
  // Load versions whenever the open space changes
  useEffect(() => {
    if (activeSpace?.id) refreshVersions(activeSpace.id);
    else setVersions([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSpace?.id]);

  const handleSaveVersion = async ({ label, notes }) => {
    try {
      await saveCfg(); // persist the working config so the snapshot matches
      await saveVersion(activeSpace.id, { label, notes });
      setSuccess(`Saved ${label}`);
      await refreshVersions();
    } catch (e) {
      setError(e.message);
    }
  };
  const handleApplyVersion = async (v) => {
    try {
      const r = await applyVersion(activeSpace.id, v.id);
      syncSpace(r.space);
      setSuccess(`Loaded ${v.label} — re-index to apply it to answers`);
      await refreshVersions();
    } catch (e) {
      setError(e.message);
    }
  };
  const handleDeleteVersion = async (v) => {
    if (!confirm(`Delete ${v.label}?`)) return;
    try {
      await deleteVersion(activeSpace.id, v.id);
      await refreshVersions();
    } catch (e) {
      setError(e.message);
    }
  };
  const confirmDeploy = async ({ label, notes, publish }) => {
    setDeploying(true);
    try {
      let r;
      if (deployModal.mode === "version") {
        r = await deployVersion(activeSpace.id, deployModal.version.id, publish);
      } else {
        await saveCfg(); // persist working config before snapshotting it
        r = await deployCurrent(activeSpace.id, { label, notes, publish });
      }
      syncSpace(r.space);
      setSuccess(
        publish
          ? "Deployed & published to end users"
          : "Deployed privately (only you & collaborators)",
      );
      setDeployModal(null);
      await refreshVersions();
    } catch (e) {
      setError(e.message);
    } finally {
      setDeploying(false);
    }
  };

  const handlePause = async () => {
    setPausing(true);
    try {
      const s = await pauseDeployment(activeSpace.id);
      syncSpace(s);
      setSuccess("Deployment paused — add docs & tweak the config, then Re-deploy.");
    } catch (e) {
      setError(e.message);
    } finally {
      setPausing(false);
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
  // Upload every SUPPORTED file inside a chosen folder (recursively). The folder
  // input returns all files; we skip anything that isn't an indexable document.
  const SUPPORTED_UPLOAD_EXTS = [
    "pdf", "docx", "doc", "pptx", "ppt", "txt", "md", "markdown",
    "csv", "xlsx", "xls", "json", "xml", "html", "htm",
  ];
  const handleFolderUpload = async (e) => {
    const all = Array.from(e.target.files || []);
    const files = all.filter((f) =>
      SUPPORTED_UPLOAD_EXTS.includes((f.name.split(".").pop() || "").toLowerCase()),
    );
    if (folderRef.current) folderRef.current.value = "";
    if (!activeSpace) return;
    if (!files.length) {
      setError("No supported documents found in that folder.");
      return;
    }
    setUploading(true);
    setError("");
    try {
      let ok = 0;
      for (const f of files) {
        try {
          await uploadDocument(activeSpace.id, f);
          ok++;
        } catch (err) {
          console.warn("upload failed", f.name, err);
        }
      }
      setSuccess(
        `${ok}/${files.length} file(s) uploaded from folder` +
          (all.length > files.length ? ` (${all.length - files.length} unsupported skipped)` : ""),
      );
      await refreshDocs();
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
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
  const handleWebIngest = async (mode, payload) => {
    if (!activeSpace) return;
    setScraping(true);
    setError("");
    try {
      if (mode === "url") {
        await scrapeUrl(activeSpace.id, payload.url, payload.extract_images);
        setSuccess("Scraped");
      } else if (mode === "html") {
        await parseRawHtml(activeSpace.id, payload.html, payload.name, payload.extract_images);
        setSuccess("HTML added");
      } else if (mode === "crawl") {
        const r = await crawlWebsite(activeSpace.id, payload);
        setSuccess(`Crawled ${r.count}/${r.total} pages`);
      } else if (mode === "sitemap") {
        const r = await ingestSitemap(activeSpace.id, payload);
        setSuccess(`Imported ${r.count}/${r.total} pages`);
      } else if (mode === "rss") {
        const r = await ingestRss(activeSpace.id, payload);
        setSuccess(`Imported ${r.count} articles`);
      }
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
  // Persist the current chunking config (mode + per-format map + params) so that
  // Process/Re-index always uses what's on screen — no separate Save needed.
  // `override` lets a caller persist a value it just set (React state is async).
  const persistChunkCfg = async (override = {}) => {
    if (!activeSpace || !cfg || !editable) return; // locked while deployed
    try {
      const updated = await updateSpace(activeSpace.id, {
        chunk_mode: cfg.chunk_mode,
        chunk_strategy: cfg.chunk_strategy,
        chunk_params: cfg.chunk_params || {},
        chunk_format_map: cfg.chunk_format_map || {},
        ...override,
      });
      setActiveSpace((s) => (s ? { ...s, ...updated } : s));
    } catch (e) {
      console.warn("chunk config save failed", e);   // non-fatal
    }
  };
  // Switching Single ↔ Per-document saves immediately, so the mode actually
  // takes effect on the next Process without a separate Save click.
  const handleChunkModeChange = (mode) => {
    if (!editable) return;
    setC("chunk_mode", mode);
    persistChunkCfg({ chunk_mode: mode });
  };
  const handleProcess = async (id) => {
    setProcessing(true);
    try {
      await persistChunkCfg();
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
      await persistChunkCfg();
      const r = await processAllDocuments(activeSpace.id);
      setSuccess(`${r.processed} processed`);
      await refreshDocs();
    } catch (e) {
      setError(e.message);
    } finally {
      setProcessing(false);
    }
  };
  const handleSetDocChunking = async (docId, strategy, params) => {
    if (!editable) return; // locked while deployed
    // Optimistic and authoritative — the local value stays put. (Merging the
    // server response here caused a race that reverted the dropdown mid-edit.)
    setDocs((p) =>
      p.map((d) =>
        d.id === docId
          ? { ...d, chunk_strategy: strategy || null, chunk_params: params || {} }
          : d,
      ),
    );
    try {
      await setDocumentChunking(activeSpace.id, docId, strategy, params);
    } catch (e) {
      setError(e.message);
    }
  };
  const handleSetExtractImages = async (docId, enabled) => {
    // optimistic
    setDocs((p) =>
      p.map((d) => (d.id === docId ? { ...d, extract_images: enabled } : d)),
    );
    try {
      await setDocumentExtractImages(activeSpace.id, docId, enabled);
    } catch (e) {
      setError(e.message);
      await refreshDocs();
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

  const handleQuery = async (preset) => {
    const q = (typeof preset === "string" ? preset : question).trim();
    if (!q || querying) return;
    setQuestion("");
    setChatHistory((h) => [...h, { role: "user", content: q }]);
    setQuerying(true);
    try {
      const r = await queryRAG(activeSpace.id, q);
      setChatHistory((h) => [
        ...h,
        { role: "assistant", content: r.answer, sources: r.sources,
          timings: r.timings },
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
  const closeModal = () => {
    setModal(null);
    setModalData(null);
    setEditMode(false);
    setEditDoc(null);
  };

  // The editor adapts to the format:
  //   doc      → reading-ordered blocks (headings/text/tables/images inline)
  //   tabular  → one editable grid per CSV/Excel table
  //   tree     → raw JSON/XML source (re-parsed on save)
  const startEdit = async () => {
    const pd = modalData.parsed_document || {};
    const kind = kindOf(pd);
    if (kind === "tabular") {
      const tables = [];
      (pd.elements || []).forEach((el, i) => {
        if (el.type === "table" && Array.isArray(el.content?.columns)) {
          const { headers, grid } = csvContentToGrid(el.content || {});
          tables.push({
            elIndex: i,
            name: el.content.table_name || el.location?.sheet || `Table ${tables.length + 1}`,
            headers,
            grid,
          });
        }
      });
      setEditDoc({ kind: "tabular", id: modalData.document_id, title: pd.title || "", elements: pd.elements || [], tables });
      setEditMode(true);
      setShowJson(false);
      return;
    }
    if (kind === "tree") {
      try {
        const loaded = await getLoadedContent(activeSpace.id, modalData.document_id);
        setEditDoc({
          kind: "tree",
          id: modalData.document_id,
          rawSource: loaded.raw_text || "",
          sourceType: (pd.metadata?.source_type || pd.metadata?.file_type || "json").toLowerCase(),
        });
        setEditMode(true);
        setShowJson(false);
      } catch (e) {
        setError(e.message);
      }
      return;
    }
    const blocks =
      pd.elements && pd.elements.length
        ? blocksFromElements(pd.elements)
        : blocksFromLegacy(pd);
    setEditDoc({ kind: "doc", id: modalData.document_id, title: pd.title || "", blocks });
    setEditMode(true);
    setShowJson(false);
  };
  const cancelEdit = () => {
    setEditMode(false);
    setEditDoc(null);
  };
  const setEditTitle = (v) => setEditDoc((prev) => ({ ...prev, title: v }));
  const editBlock = (i, field, value) => {
    setEditDoc((prev) => {
      const blocks = [...prev.blocks];
      blocks[i] = { ...blocks[i], [field]: value };
      return { ...prev, blocks };
    });
  };
  const removeBlock = (i) => {
    setEditDoc((prev) => ({ ...prev, blocks: prev.blocks.filter((_, idx) => idx !== i) }));
  };
  // Move a block up/down in the reading order (dir = -1 up, +1 down).
  const moveBlock = (i, dir) => {
    setEditDoc((prev) => {
      const blocks = [...prev.blocks];
      const j = i + dir;
      if (j < 0 || j >= blocks.length) return prev;
      [blocks[i], blocks[j]] = [blocks[j], blocks[i]];
      return { ...prev, blocks };
    });
  };
  const addHeading = () =>
    setEditDoc((prev) => ({
      ...prev,
      blocks: [...prev.blocks, { kind: "heading", text: "", level: 1, page: 1 }],
    }));
  const addText = () =>
    setEditDoc((prev) => ({
      ...prev,
      blocks: [...prev.blocks, { kind: "text", elType: "paragraph", text: "", page: 1, listLevel: null }],
    }));
  const addTable = () =>
    setEditDoc((prev) => ({
      ...prev,
      blocks: [
        ...prev.blocks,
        { kind: "table", page: 1, headers: ["Column 1", "Column 2"], grid: [[{ t: "", cs: 1, rs: 1 }, { t: "", cs: 1, rs: 1 }]] },
      ],
    }));
  // Merge a patch into a doc block (used by the table grid editor).
  const updateBlock = (i, patch) =>
    setEditDoc((prev) => {
      const blocks = [...prev.blocks];
      blocks[i] = { ...blocks[i], ...patch };
      return { ...prev, blocks };
    });
  // ── Tabular (CSV/Excel) + tree (JSON/XML) editor handlers ──
  const updateTable = (ti, patch) =>
    setEditDoc((prev) => {
      const tables = [...prev.tables];
      tables[ti] = { ...tables[ti], ...patch };
      return { ...prev, tables };
    });
  const setRawSource = (v) => setEditDoc((prev) => ({ ...prev, rawSource: v }));
  // Upload an image file, then append it as a new image block in the editor.
  const [uploadingImage, setUploadingImage] = useState(false);
  const addImage = async (file) => {
    if (!file || !editDoc) return;
    setUploadingImage(true);
    try {
      const { image_path } = await uploadDocumentImage(activeSpace.id, editDoc.id, file);
      setEditDoc((prev) => ({
        ...prev,
        blocks: [
          ...prev.blocks,
          { kind: "image", page: 1, image_path, src: "", caption: "", text_for_embedding: "", ocr_text: "" },
        ],
      }));
    } catch (e) {
      setError(e.message);
    } finally {
      setUploadingImage(false);
    }
  };
  const saveEdit = async () => {
    setSavingEdit(true);
    try {
      let payload;
      if (editDoc.kind === "tabular") {
        // rebuild each edited table element's columns/rows, leave the rest as-is
        const elements = (editDoc.elements || []).map((el, i) => {
          const t = editDoc.tables.find((x) => x.elIndex === i);
          if (!t) return el;
          return { ...el, content: gridToCsvContent(el.content || {}, t.headers, t.grid) };
        });
        payload = { title: editDoc.title || "", elements };
      } else if (editDoc.kind === "tree") {
        payload = { raw_source: editDoc.rawSource || "" };
      } else {
        payload = {
          title: editDoc.title || "",
          elements: elementsFromBlocks(editDoc.blocks),
          ...legacyFromBlocks(editDoc.blocks), // fallback for older backend
        };
      }
      const updated = await updateExtractedContent(activeSpace.id, editDoc.id, payload);
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
          onEditSpace={handleEditSpace}
          showCreate={showCreate}
          setShowCreate={setShowCreate}
          createDept={createDept}
          setCreateDept={setCreateDept}
          newName={newName}
          setNewName={setNewName}
          newDesc={newDesc}
          setNewDesc={setNewDesc}
          handleCreate={handleCreate}
          createDeptUsers={createDeptUsers}
          loadingCreateUsers={loadingCreateUsers}
          createUserIds={createUserIds}
          setCreateUserIds={setCreateUserIds}
          createPrivate={createPrivate}
          setCreatePrivate={setCreatePrivate}
        />
      </div>
    );

  // PAGE 2 : space interior
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
                <div
                  style={{ display: "flex", alignItems: "center", gap: 8 }}
                >
                  <div className="rag-header-title">{activeSpace.name}</div>
                  <StatusPill space={activeSpace} />
                </div>
                <div className="rag-header-desc">
                  {deptName(activeSpace.department_id)}
                  {activeSpace.is_owner === false && " · Shared with you"}
                </div>
              </div>
            </div>
            <div className="rag-header-actions">
              <span className="rag-config-tag">
                {activeSpace.num_chunks} chunks
              </span>
              <button
                className={`rag-btn rag-btn-sm ${panel === "access" ? "rag-btn-dark" : ""}`}
                onClick={() => setPanel("access")}
              >
                🔒 Access
              </button>
              {activeSpace.is_owner !== false &&
                activeSpace.status === "ACTIVE" && (
                  <button
                    className="rag-btn rag-btn-sm"
                    onClick={handlePause}
                    disabled={pausing}
                    title="Take the agent offline to add docs / change config"
                  >
                    {pausing ? "Pausing…" : "⏸ Stop to edit"}
                  </button>
                )}
              {activeSpace.is_owner !== false &&
                activeSpace.status !== "ACTIVE" && (
                  <button
                    className="rag-btn rag-btn-sm rag-btn-blue"
                    onClick={() =>
                      setDeployModal({ mode: "current", version: null })
                    }
                  >
                    🚀 {activeSpace.status === "EDITING" ? "Re-deploy" : "Deploy"}
                  </button>
                )}
              {activeSpace.is_owner !== false && (
                <button
                  className="rag-btn rag-btn-sm rag-btn-red"
                  onClick={() => handleDeleteSpace(activeSpace.id)}
                >
                  Delete
                </button>
              )}
            </div>
          </div>

          {error && <div className="rag-toast rag-toast-error">{error}</div>}
          {success && (
            <div className="rag-toast rag-toast-success">{success}</div>
          )}

          {activeSpace.can_build === false && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "9px 12px",
                margin: "0 0 12px",
                borderRadius: 10,
                fontSize: 12.5,
                background: "rgba(100,116,139,.1)",
                border: "1px solid rgba(100,116,139,.3)",
                color: "#475569",
              }}
            >
              <span>👁️</span>
              <div style={{ flex: 1 }}>
                <strong>Read-only.</strong> This space belongs to another IT in
                your department — you can view its configuration but not edit,
                configure, version, or deploy it.
              </div>
            </div>
          )}

          {/* Deployed & live → locked. The owner must Stop to edit to change it. */}
          {live && activeSpace.can_build !== false && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "9px 12px",
                margin: "0 0 12px",
                borderRadius: 10,
                fontSize: 12.5,
                background: "rgba(22,163,74,.08)",
                border: "1px solid rgba(22,163,74,.3)",
                color: "#166534",
              }}
            >
              <span>🔒</span>
              <div style={{ flex: 1 }}>
                <strong>Deployed &amp; live.</strong> This space is locked while
                deployed. Click <strong>Stop to edit</strong> to change documents,
                configuration or versions, then re-deploy.
              </div>
              {activeSpace.is_owner !== false && (
                <button
                  className="rag-btn rag-btn-sm"
                  onClick={handlePause}
                  disabled={pausing}
                >
                  {pausing ? "Pausing…" : "⏸ Stop to edit"}
                </button>
              )}
            </div>
          )}

          {activeSpace.reindex_required && editable && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "9px 12px",
                margin: "0 0 12px",
                borderRadius: 10,
                fontSize: 12.5,
                background: "rgba(245,158,11,.1)",
                border: "1px solid rgba(245,158,11,.35)",
                color: "#92400e",
              }}
            >
              <span>⚠️</span>
              <div style={{ flex: 1 }}>
                <strong>Re-index needed.</strong> Chunking/embedding settings
                changed — your documents are still indexed with the old settings,
                so answers won't reflect the new config until you rebuild them.
              </div>
              <button
                className="rag-btn rag-btn-sm"
                onClick={handleProcessAll}
                disabled={processing}
              >
                {processing ? "Re-indexing…" : "Re-index now"}
              </button>
            </div>
          )}

          {panel === "uploads" && (
            <div className="rag-cfg-panel">
              <div className="rag-cfg-head">
                <div>
                  <div className="rag-cfg-title">Uploads</div>
                  <div className="rag-cfg-sub">
                    Add, parse and manage the documents this space answers from.
                  </div>
                </div>
              </div>
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
              handleFolderUpload={handleFolderUpload}
              folderRef={folderRef}
              handleDriveUpload={handleDriveUpload}
              handleScrape={handleScrape}
              handleWebIngest={handleWebIngest}
              handleLoadParse={handleLoadParse}
              handleLoadParseAll={handleLoadParseAll}
              handleParse={handleParse}
              handleParseAll={handleParseAll}
              handleProcess={handleProcess}
              handleProcessAll={handleProcessAll}
              handleDeleteDoc={handleDeleteDoc}
              openModal={openModal}
              counts={{ uploadingCount, loadedCount, extractedCount }}
              handleSetExtractImages={handleSetExtractImages}
              spaceId={activeSpace.id}
              isOwner={activeSpace.is_owner !== false}
              editable={editable}
              />
            </div>
          )}

          {panel === "flow" && <FlowPanel space={activeSpace} />}

          {panel === "eval" && (
            <EvaluationPanel
              chatHistory={chatHistory}
              chatEndRef={chatEndRef}
              question={question}
              setQuestion={setQuestion}
              querying={querying}
              handleQuery={handleQuery}
              spaceId={activeSpace.id}
              space={activeSpace}
              editable={activeSpace.can_build !== false}
            />
          )}

          {panel === "versions" && (
            <>
              <VersionsPanel
                space={activeSpace}
                versions={versions}
                loading={loadingVersions}
                canBuild={activeSpace.can_build !== false}
                isOwner={activeSpace.is_owner === true}
                editable={editable}
                onSaveVersion={handleSaveVersion}
                onApplyVersion={handleApplyVersion}
                onDeployVersion={(v) =>
                  setDeployModal({ mode: "version", version: v })
                }
                onDeleteVersion={handleDeleteVersion}
                onReindex={handleProcessAll}
                reindexing={processing}
              />
              {/* after deploy: machine access for other enterprise apps */}
              <ApiAccessPanel
                space={activeSpace}
                canManage={activeSpace.can_build !== false}
              />
            </>
          )}

          {panel !== "uploads" &&
            panel !== "flow" &&
            panel !== "eval" &&
            panel !== "versions" && (
            <ConfigPanel
              panel={panel}
              setPanel={setPanel}
              cfg={cfg}
              space={activeSpace}
              setC={setC}
              saveCfg={saveCfg}
              savingCfg={savingCfg}
              embedModels={embedModels}
              llmModels={llmModels}
              llmState={llmState}
              loadingLlm={loadingLlm}
              deptUsers={deptUsers}
              loadingDeptUsers={loadingDeptUsers}
              docs={docs}
              chunkCatalog={chunkCatalog}
              handleSetDocChunking={handleSetDocChunking}
              handleChunkModeChange={handleChunkModeChange}
              handleProcess={handleProcess}
              handleProcessAll={handleProcessAll}
              processing={processing}
              openModal={openModal}
              canBuild={activeSpace.can_build !== false}
              editable={editable}
            />
          )}
        </div>

        <RightSidebar
          panel={panel}
          setPanel={setPanel}
          space={activeSpace}
          docsCount={docs.length}
        />
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
        setEditTitle={setEditTitle}
        savingEdit={savingEdit}
        startEdit={startEdit}
        cancelEdit={cancelEdit}
        saveEdit={saveEdit}
        editBlock={editBlock}
        updateBlock={updateBlock}
        removeBlock={removeBlock}
        moveBlock={moveBlock}
        addHeading={addHeading}
        addText={addText}
        addTable={addTable}
        addImage={addImage}
        uploadingImage={uploadingImage}
        updateTable={updateTable}
        setRawSource={setRawSource}
        spaceId={activeSpace?.id}
      />

      {deployModal && (
        <DeployModal
          mode={deployModal.mode}
          version={deployModal.version}
          nextLabel={`v${(versions[0]?.version_number || 0) + 1}`}
          busy={deploying}
          onConfirm={confirmDeploy}
          onClose={() => setDeployModal(null)}
        />
      )}
    </div>
  );
};

export default RAGSpacesPage;
