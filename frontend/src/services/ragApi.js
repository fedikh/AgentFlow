const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

async function request(method, endpoint, body = null) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
    credentials: "include",
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(`${BASE_URL}${endpoint}`, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Something went wrong");
  return data;
}

async function upload(endpoint, file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    method: "POST",
    credentials: "include",
    body: form, // no Content-Type header — browser sets multipart boundary
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Upload failed");
  return data;
}

// ── RAG Spaces ────────────────────────────────────────
export const createSpace = (payload) => request("POST", "/rag/spaces", payload);
export const listSpaces = () => request("GET", "/rag/spaces");
export const getSpace = (id) => request("GET", `/rag/spaces/${id}`);
export const updateSpace = (id, payload) =>
  request("PUT", `/rag/spaces/${id}`, payload);
export const deleteSpace = (id) => request("DELETE", `/rag/spaces/${id}`);

// ── Documents ─────────────────────────────────────────
export const uploadDocument = (spaceId, file) =>
  upload(`/rag/spaces/${spaceId}/upload`, file);
export const listDocuments = (spaceId) =>
  request("GET", `/rag/spaces/${spaceId}/documents`);
export const deleteDocument = (spaceId, docId) =>
  request("DELETE", `/rag/spaces/${spaceId}/documents/${docId}`);

// ── Query ─────────────────────────────────────────────
export const queryRAG = (spaceId, question) =>
  request("POST", `/rag/spaces/${spaceId}/query`, { question });
