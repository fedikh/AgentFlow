const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

// ── Helper ──
async function req(method, path, body = null) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
    credentials: "include",
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(`${BASE}${path}`, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

// ── Departments ──
export const listDepartments = () => req("GET", "/users/departments");

// ── Access control (Batch 1): USER-role members of a department ──
export const listDepartmentUsers = (deptId) =>
  req("GET", `/rag/departments/${deptId}/users`);

// ── Spaces ──
export const createSpace = (d) => req("POST", "/rag/spaces", d);
export const listSpaces = () => req("GET", "/rag/spaces");
export const getSpace = (id) => req("GET", `/rag/spaces/${id}`);
export const updateSpace = (id, d) => req("PUT", `/rag/spaces/${id}`, d);
export const deleteSpace = (id) => req("DELETE", `/rag/spaces/${id}`);

// ── Versioning + deploy lifecycle ──
export const listVersions = (id) => req("GET", `/rag/spaces/${id}/versions`);
export const saveVersion = (id, { label, notes } = {}) =>
  req("POST", `/rag/spaces/${id}/versions`, { label, notes });
export const applyVersion = (id, vid) =>
  req("POST", `/rag/spaces/${id}/versions/${vid}/apply`);
export const deployVersion = (id, vid, publish = false) =>
  req("POST", `/rag/spaces/${id}/versions/${vid}/deploy`, { publish });
export const deleteVersion = (id, vid) =>
  req("DELETE", `/rag/spaces/${id}/versions/${vid}`);
export const deployCurrent = (id, { label, notes, publish = false } = {}) =>
  req("POST", `/rag/spaces/${id}/deploy`, { label, notes, publish });
export const setPublish = (id, isPrivate) =>
  req("PUT", `/rag/spaces/${id}/publish`, { is_private: isPrivate });
export const pauseDeployment = (id) => req("POST", `/rag/spaces/${id}/pause`);

// ── Documents ──
export const listDocuments = (s) => req("GET", `/rag/spaces/${s}/documents`);
export const deleteDocument = (s, d) =>
  req("DELETE", `/rag/spaces/${s}/documents/${d}`);

// End-user-facing (access-checked) document list for a deployed space
export const listPublicDocuments = (s) =>
  req("GET", `/rag/spaces/${s}/public-documents`);

// Fetch the original file as a blob URL for inline viewing. The file route
// requires the auth cookie, and a bare cross-origin <iframe src> won't send it
// reliably — so we fetch with credentials and hand the object URL to the viewer.
// Caller must URL.revokeObjectURL(url) when done.
export const fetchDocumentBlobUrl = async (spaceId, docId) => {
  const res = await fetch(
    `${BASE}/rag/spaces/${spaceId}/documents/${docId}/file`,
    { credentials: "include" },
  );
  if (!res.ok) {
    let detail = "File load failed";
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  const blob = await res.blob();
  return { url: URL.createObjectURL(blob), type: blob.type };
};

// ── Upload (multipart) ──
export const uploadDocument = async (spaceId, file) => {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${BASE}/rag/spaces/${spaceId}/upload`, {
    method: "POST",
    credentials: "include",
    body: fd,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Upload failed");
  return data;
};

// ── Web sources ──
export const scrapeUrl = (s, url, extractImages = true) =>
  req("POST", `/rag/spaces/${s}/scrape`, { url, extract_images: extractImages });
export const parseRawHtml = (s, html, name, extractImages = true) =>
  req("POST", `/rag/spaces/${s}/web/html`, { html, name, extract_images: extractImages });
export const crawlWebsite = (s, payload) =>
  req("POST", `/rag/spaces/${s}/web/crawl`, payload);
export const ingestSitemap = (s, payload) =>
  req("POST", `/rag/spaces/${s}/web/sitemap`, payload);
export const ingestRss = (s, payload) =>
  req("POST", `/rag/spaces/${s}/web/rss`, payload);

// ── Loader output (raw text) ──
export const getLoadedContent = (s, d) =>
  req("GET", `/rag/spaces/${s}/documents/${d}/loaded`);

// ── Parser ──
export const parseDocument = (s, d) =>
  req("POST", `/rag/spaces/${s}/documents/${d}/parse`);
export const parseAllDocuments = (s) =>
  req("POST", `/rag/spaces/${s}/parse-all`);

// ── Parser output (structured blocks) ──
export const getExtractedContent = (s, d) =>
  req("GET", `/rag/spaces/${s}/documents/${d}/extracted`);
// ── Save edited parser output ──
export const updateExtractedContent = (s, d, parsedDocument) =>
  req("PUT", `/rag/spaces/${s}/documents/${d}/extracted`, parsedDocument);

// ── Per-document image extraction toggle ──
export const setDocumentExtractImages = (s, d, enabled) =>
  req("PUT", `/rag/spaces/${s}/documents/${d}/extract-images`, { enabled });

// ── Upload an image to add in the parsed-content editor ──
export const uploadDocumentImage = async (spaceId, docId, file) => {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(
    `${BASE}/rag/spaces/${spaceId}/documents/${docId}/image`,
    { method: "POST", credentials: "include", body: fd },
  );
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Image upload failed");
  return data; // { image_path, file_name }
};

// ── Process (chunk + embed) ──
export const processDocument = (s, d) =>
  req("POST", `/rag/spaces/${s}/documents/${d}/process`);
export const processAllDocuments = (s) =>
  req("POST", `/rag/spaces/${s}/process-all`);

// ── Chunks ──
export const listChunks = (s, d) =>
  req("GET", `/rag/spaces/${s}/documents/${d}/chunks`);

// ── Query ──
export const queryRAG = (s, q) =>
  req("POST", `/rag/spaces/${s}/query`, { question: q });

export const loadAndParseDocument = (s, d) =>
  req("POST", `/rag/spaces/${s}/documents/${d}/load-parse`);
export const loadAndParseAll = (s) =>
  req("POST", `/rag/spaces/${s}/load-parse-all`);
export const uploadFromDrive = (spaceId, fileId, accessToken) =>
  req("POST", `/rag/spaces/${spaceId}/upload-drive`, {
    file_id: fileId,
    access_token: accessToken,
  });
// ── Evaluation: dataset (upload / template / generate) + experiment runs ──
export const evalListCases = (s) => req("GET", `/rag/spaces/${s}/eval/cases`);
export const evalAddCase = (s, data) => req("POST", `/rag/spaces/${s}/eval/cases`, data);
export const evalDeleteCase = (s, id) => req("DELETE", `/rag/spaces/${s}/eval/cases/${id}`);
export const evalClearCases = (s) => req("DELETE", `/rag/spaces/${s}/eval/cases`);
export const evalUploadDataset = (s, cases) => req("POST", `/rag/spaces/${s}/eval/dataset`, { cases });
export const evalDatasetTemplate = (s) => req("GET", `/rag/spaces/${s}/eval/dataset-template`);
export const evalTemplateExcel = (s) => req("GET", `/rag/spaces/${s}/eval/template-excel`);
export const evalExpertForm = (s) => req("GET", `/rag/spaces/${s}/eval/expert-form`);
// Multipart upload of the filled expert file (.xlsx / .csv / .json)
export const evalUploadDatasetFile = async (s, file) => {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${BASE}/rag/spaces/${s}/eval/dataset-file`, {
    method: "POST", body: fd, credentials: "include",
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Upload failed");
  return data;
};
export const evalGenerateCases = (s, n = 8) => req("POST", `/rag/spaces/${s}/eval/generate-cases?n=${n}`);
export const evalRun = (s) => req("POST", `/rag/spaces/${s}/eval/run`);
export const evalRuns = (s) => req("GET", `/rag/spaces/${s}/eval/runs`);
export const evalRunDetail = (s, id) => req("GET", `/rag/spaces/${s}/eval/runs/${id}`);

// NOTE: BASE already ends in "/api", and the models router is mounted at
// "/api/models", so these paths must NOT repeat "/api" (else → /api/api/... 404).
// Vue d'ensemble : tous les providers LLM + embeddings en un appel
export const getAllModels = () => req("GET", "/models/all");

// Liste curatée des modèles d'embedding (avec dimensions)
export const getEmbeddingModels = () => req("GET", "/models/embeddings");

// Modèles d'un provider LLM (GROQ / OLLAMA / OPENAI), récupérés en direct
export const getLLMModels = (provider) =>
  req("GET", `/models/llm/${provider}`);
// ── Chunking catalog (per-format strategies + tunable params) ──
export const getChunkingCatalog = (fileType) =>
  req("GET", `/rag/chunking/catalog${fileType ? `?file_type=${fileType}` : ""}`);

// Set a document's chunking strategy + params (mode PER_DOCUMENT)
export const setDocumentChunking = (spaceId, docId, strategy, params) =>
  req("PUT", `/rag/spaces/${spaceId}/documents/${docId}/chunking`, { strategy, params });

