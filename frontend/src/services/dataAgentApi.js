const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

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

// Spaces
export const createDataSpace = (d) => req("POST", "/data-agent/spaces", d);
export const listDataSpaces = () => req("GET", "/data-agent/spaces");
export const deleteDataSpace = (id) =>
  req("DELETE", `/data-agent/spaces/${id}`);

// Files
export const uploadDataFile = async (spaceId, file) => {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${BASE}/data-agent/spaces/${spaceId}/upload`, {
    method: "POST",
    credentials: "include",
    body: fd,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Upload failed");
  return data;
};

export const listDataFiles = (s) => req("GET", `/data-agent/spaces/${s}/files`);
export const previewDataFile = (s, id) =>
  req("GET", `/data-agent/spaces/${s}/files/${id}/preview`);
export const getFileSchema = (s, id) =>
  req("GET", `/data-agent/spaces/${s}/files/${id}/schema`);
export const deleteDataFile = (s, id) =>
  req("DELETE", `/data-agent/spaces/${s}/files/${id}`);

// Query
export const queryData = (s, q) =>
  req("POST", `/data-agent/spaces/${s}/query`, { question: q });

export const connectDatabase = (s, d) =>
  req("POST", `/data-agent/spaces/${s}/database/connect`, d);
export const getDatabaseInfo = (s) =>
  req("GET", `/data-agent/spaces/${s}/database`);
export const disconnectDb = (s) =>
  req("DELETE", `/data-agent/spaces/${s}/database`);
export const tablePreview = (s, t) =>
  req("GET", `/data-agent/spaces/${s}/database/tables/${t}/preview`);
export const tableSchema = (s, t) =>
  req("GET", `/data-agent/spaces/${s}/database/tables/${t}/schema`);
export const queryDatabase = (s, q, tables) =>
  req("POST", `/data-agent/spaces/${s}/database/query`, {
    question: q,
    tables,
  });
export const getFullSchema = (s) =>
  req("GET", `/data-agent/spaces/${s}/database/full-schema`);
