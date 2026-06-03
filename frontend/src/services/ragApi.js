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

// Spaces
export const createSpace = (data) => request("POST", "/rag/spaces", data);
export const listSpaces = () => request("GET", "/rag/spaces");
export const getSpace = (id) => request("GET", `/rag/spaces/${id}`);
export const updateSpace = (id, data) =>
  request("PUT", `/rag/spaces/${id}`, data);
export const deleteSpace = (id) => request("DELETE", `/rag/spaces/${id}`);

// Documents
export const listDocuments = (spaceId) =>
  request("GET", `/rag/spaces/${spaceId}/documents`);
export const deleteDocument = (spaceId, docId) =>
  request("DELETE", `/rag/spaces/${spaceId}/documents/${docId}`);

// Upload (local file)
export const uploadDocument = async (spaceId, file) => {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE_URL}/rag/spaces/${spaceId}/upload`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Upload failed");
  return data;
};

// Scrape URL
export const scrapeUrl = (spaceId, url) =>
  request("POST", `/rag/spaces/${spaceId}/scrape`, { url });

// Extracted content (for review)
export const getExtractedContent = (spaceId, docId) =>
  request("GET", `/rag/spaces/${spaceId}/documents/${docId}/extracted`);

// Process (chunking + embedding)
export const processDocument = (spaceId, docId) =>
  request("POST", `/rag/spaces/${spaceId}/documents/${docId}/process`);
export const processAllDocuments = (spaceId) =>
  request("POST", `/rag/spaces/${spaceId}/process-all`);

// Chunks
export const listChunks = (spaceId, docId) =>
  request("GET", `/rag/spaces/${spaceId}/documents/${docId}/chunks`);

// Query
export const queryRAG = (spaceId, question) =>
  request("POST", `/rag/spaces/${spaceId}/query`, { question });
