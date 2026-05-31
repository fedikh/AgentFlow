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

// Chunks — NEW
export const listChunks = (spaceId, docId) =>
  request("GET", `/rag/spaces/${spaceId}/documents/${docId}/chunks`);

// Upload (multipart)
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

// Query
export const queryRAG = async (spaceId, question) => {
  return request("POST", `/rag/spaces/${spaceId}/query`, { question });
};
