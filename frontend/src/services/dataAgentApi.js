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

/* ── Data sources: CRUD, connection, lifecycle ── */
export const listDialects = () => req("GET", "/data-sources/dialects");
export const listDataSources = () => req("GET", "/data-sources");
export const getDataSource = (id) => req("GET", `/data-sources/${id}`);
export const createDataSource = (d) => req("POST", "/data-sources", d);
export const updateDataSource = (id, d) => req("PATCH", `/data-sources/${id}`, d);
export const deleteDataSource = (id) => req("DELETE", `/data-sources/${id}`);
export const testDataSource = (id) => req("POST", `/data-sources/${id}/test`);

export const setSourceAuthorization = (id, userIds) =>
  req("PUT", `/data-sources/${id}/authorization`, { user_ids: userIds });
export const deploySource = (id) => req("POST", `/data-sources/${id}/deploy`);
export const pauseSource = (id) => req("POST", `/data-sources/${id}/pause`);

/* ── Schema & training ── */
export const introspectSource = (id) => req("POST", `/data-sources/${id}/introspect`);
export const trainSource = (id) => req("POST", `/data-sources/${id}/index`);
export const dataJobStatus = (jobId) => req("GET", `/data-sources/jobs/${jobId}`);
export const getSourceSchema = (id) => req("GET", `/data-sources/${id}/schema`);
export const updateSourceTable = (id, tableId, d) =>
  req("PATCH", `/data-sources/${id}/tables/${tableId}`, d);
export const getKnowledgeStats = (id) => req("GET", `/data-sources/${id}/knowledge`);

/* ── Business knowledge: glossary · examples · documents ── */
export const listGlossary = (id) => req("GET", `/data-sources/${id}/glossary`);
export const addGlossary = (id, term, definition) =>
  req("POST", `/data-sources/${id}/glossary`, { term, definition });
export const deleteGlossary = (id, termId) =>
  req("DELETE", `/data-sources/${id}/glossary/${termId}`);

export const listExamples = (id) => req("GET", `/data-sources/${id}/examples`);
export const addExample = (id, question, sql, isVerified = false) =>
  req("POST", `/data-sources/${id}/examples`, { question, sql, is_verified: isVerified });
export const verifyExample = (id, exampleId) =>
  req("POST", `/data-sources/${id}/examples/${exampleId}/verify`);
export const deleteExample = (id, exampleId) =>
  req("DELETE", `/data-sources/${id}/examples/${exampleId}`);

/* CSV bulk import (question,sql[,verified] · term,definition) */
const upload = async (path, file) => {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${BASE}${path}`, {
    method: "POST", credentials: "include", body: fd,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Upload failed");
  return data;
};
export const importExamplesCsv = (id, file) =>
  upload(`/data-sources/${id}/examples/import`, file);
export const importGlossaryCsv = (id, file) =>
  upload(`/data-sources/${id}/glossary/import`, file);
export const csvTemplateUrl = (kind) => `${BASE}/data-sources/csv-template/${kind}`;

/* Knowledge documents live in a hidden RAG space: this provisions it, then
   the panel drives it with the RAG endpoints (ragApi) — no duplicate API. */
export const ensureKnowledgeSpace = (sourceId) =>
  req("POST", `/data-sources/${sourceId}/knowledge-space`);

/* ── Ask (LangGraph + Vanna) ── */
export const askData = (dataSourceId, question, sessionId = null) =>
  req("POST", "/data-agent/ask",
      { question, data_source_id: dataSourceId, session_id: sessionId });
export const executeSql = (dataSourceId, sql) =>
  req("POST", "/data-agent/execute", { data_source_id: dataSourceId, sql });
export const listDaSessions = () => req("GET", "/data-agent/sessions");
export const getDaSession = (id) => req("GET", `/data-agent/sessions/${id}`);
export const deleteDaSession = (id) => req("DELETE", `/data-agent/sessions/${id}`);
