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

// ── Spaces ──
export const createSpace = (d) => req("POST", "/rag/spaces", d);
export const listSpaces = () => req("GET", "/rag/spaces");
export const getSpace = (id) => req("GET", `/rag/spaces/${id}`);
export const updateSpace = (id, d) => req("PUT", `/rag/spaces/${id}`, d);
export const deleteSpace = (id) => req("DELETE", `/rag/spaces/${id}`);

// ── Documents ──
export const listDocuments = (s) => req("GET", `/rag/spaces/${s}/documents`);
export const deleteDocument = (s, d) =>
  req("DELETE", `/rag/spaces/${s}/documents/${d}`);

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

// ── Scrape ──
export const scrapeUrl = (s, url) =>
  req("POST", `/rag/spaces/${s}/scrape`, { url });

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
