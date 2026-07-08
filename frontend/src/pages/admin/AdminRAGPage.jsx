import React, { useState, useEffect, useMemo } from "react";
import { listSpaces, listDocuments } from "../../services/ragApi";
import "../../styles/admin/adminRag.css";

/**
 * Admin RAG Spaces — READ ONLY monitoring dashboard.
 * Admin sees every space across all departments: KPIs, per-space config and
 * documents. No create/upload/delete/chat.
 */
const Icon = {
  search: (p) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" {...p}>
      <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
      <path d="M21 21l-4.3-4.3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  ),
  doc: (p) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M14 3v5h5M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-5Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
    </svg>
  ),
  layers: (p) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M12 2 2 7l10 5 10-5-10-5ZM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
    </svg>
  ),
  scissors: (p) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" {...p}>
      <circle cx="6" cy="6" r="3" stroke="currentColor" strokeWidth="1.7" />
      <circle cx="6" cy="18" r="3" stroke="currentColor" strokeWidth="1.7" />
      <path d="M20 4 8.1 15.9M14.5 14.5 20 20M8.1 8.1 12 12" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  ),
  target: (p) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" {...p}>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.7" />
      <circle cx="12" cy="12" r="5" stroke="currentColor" strokeWidth="1.7" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" />
    </svg>
  ),
  empty: (p) => (
    <svg width="46" height="46" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M12 2 2 7l10 5 10-5-10-5ZM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  ),
  cog: (p) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" {...p}>
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.7" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 6 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0-1.2-2.9H0M4.6 9A1.7 1.7 0 0 0 5.8 6" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  ),
};

const pct = (v) => `${Math.round((Number(v) || 0) * 100)}%`;
const ext = (name = "") => (name.split(".").pop() || "FILE").toUpperCase().slice(0, 4);

const AdminRAGPage = () => {
  const [spaces, setSpaces] = useState([]);
  const [selected, setSelected] = useState(null);
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        setSpaces(await listSpaces());
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const selectSpace = async (space) => {
    setSelected(space);
    setDocs([]);
    try {
      setDocs(await listDocuments(space.id));
    } catch (e) {
      setError(e.message);
    }
  };

  const totalDocs = spaces.reduce((a, s) => a + (s.num_documents || 0), 0);
  const totalChunks = spaces.reduce((a, s) => a + (s.num_chunks || 0), 0);
  const deptCount = new Set(spaces.map((s) => s.department_name || "—")).size;

  const grouped = useMemo(() => {
    const filtered = spaces.filter((s) =>
      s.name.toLowerCase().includes(q.trim().toLowerCase()),
    );
    const g = {};
    filtered.forEach((s) => {
      const d = s.department_name || "No department";
      (g[d] = g[d] || []).push(s);
    });
    return g;
  }, [spaces, q]);

  const spec = (s) => [
    ["Chunk mode", s.chunk_mode || "FIXED_ALL"],
    ["Chunk strategy", s.chunk_strategy || "FIXED"],
    ["Chunk size", `${s.chunk_size ?? 512} chars`],
    ["Overlap", `${s.chunk_overlap ?? 50} chars`],
    ["Embedding", (s.embedding_model || "BAAI/bge-m3").split("/").pop()],
    ["LLM", s.llm_model || s.llm_provider || "—"],
    ["Semantic / keyword", `${pct(s.semantic_weight ?? 0.7)} / ${pct(1 - (s.semantic_weight ?? 0.7))}`],
    ["Reranking", s.reranking_enabled ? "On" : "Off"],
  ];

  return (
    <div className="arag">
      <div className="arag-head">
        <h1 className="arag-title">RAG Spaces</h1>
        <p className="arag-sub">
          Monitor every space across your organization · read-only
        </p>
      </div>

      {error && (
        <div className="arag-error">
          <span>{error}</span>
          <span
            onClick={() => setError("")}
            style={{ cursor: "pointer" }}
          >
            ✕
          </span>
        </div>
      )}

      {/* KPI row */}
      <div className="arag-kpis">
        {[
          ["Spaces", spaces.length],
          ["Documents", totalDocs],
          ["Indexed chunks", totalChunks],
          ["Departments", deptCount],
        ].map(([label, value]) => (
          <div className="arag-kpi" key={label}>
            <div className="arag-kpi-value">{value}</div>
            <div className="arag-kpi-label">{label}</div>
          </div>
        ))}
      </div>

      {loading ? (
        <div className="arag-loading">Loading spaces…</div>
      ) : (
        <div className="arag-layout">
          {/* Left — spaces list */}
          <aside className="arag-side">
            <div className="arag-side-head">
              All spaces <span className="arag-count">{spaces.length}</span>
            </div>
            <div className="arag-search">
              <Icon.search />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search spaces…"
              />
            </div>

            {spaces.length === 0 && (
              <div className="arag-empty">No RAG spaces created yet.</div>
            )}

            {Object.entries(grouped).map(([deptName, deptSpaces]) => (
              <div key={deptName}>
                <div className="arag-dept">
                  {deptName} ({deptSpaces.length})
                </div>
                {deptSpaces.map((s) => {
                  const st = (s.status || "DRAFT").toLowerCase();
                  return (
                    <button
                      key={s.id}
                      className={`arag-space-item ${selected?.id === s.id ? "active" : ""}`}
                      onClick={() => selectSpace(s)}
                    >
                      <div className="arag-space-item-top">
                        <span
                          className={`arag-dot ${st === "active" ? "active" : st === "error" ? "error" : ""}`}
                        />
                        <span className="arag-space-name">{s.name}</span>
                      </div>
                      <div className="arag-space-meta">
                        {s.num_documents || 0} docs · {s.num_chunks || 0} chunks
                      </div>
                    </button>
                  );
                })}
              </div>
            ))}
          </aside>

          {/* Right — detail */}
          <section className="arag-detail">
            {!selected ? (
              <div className="arag-placeholder">
                <Icon.empty />
                <p>Select a space to view its configuration and documents.</p>
              </div>
            ) : (
              <>
                <div className="arag-detail-head">
                  <h2 className="arag-detail-title">{selected.name}</h2>
                  <div className="arag-detail-meta">
                    {selected.department_name && (
                      <span className="arag-chip">
                        {selected.department_name}
                      </span>
                    )}
                    <span
                      className={`arag-status arag-status-${(selected.status || "DRAFT").toLowerCase()}`}
                    >
                      {selected.status || "DRAFT"}
                    </span>
                  </div>
                  {selected.description && (
                    <p className="arag-detail-desc">{selected.description}</p>
                  )}
                </div>

                {/* stat tiles */}
                <div className="arag-tiles">
                  {[
                    { label: "Documents", value: selected.num_documents || 0, icon: <Icon.doc /> },
                    { label: "Indexed chunks", value: selected.num_chunks || 0, icon: <Icon.layers /> },
                    { label: "Strategy", value: selected.chunk_strategy || "FIXED", icon: <Icon.scissors /> },
                    { label: "Top-K", value: selected.top_k ?? 5, icon: <Icon.target /> },
                  ].map((t) => (
                    <div className="arag-tile" key={t.label}>
                      <div className="arag-tile-ic">{t.icon}</div>
                      <div className="arag-tile-value">{t.value}</div>
                      <div className="arag-tile-label">{t.label}</div>
                    </div>
                  ))}
                </div>

                {/* pipeline spec */}
                <div className="arag-spec">
                  <div className="arag-spec-title">
                    <Icon.cog /> Pipeline configuration
                  </div>
                  <div className="arag-spec-grid">
                    {spec(selected).map(([k, v]) => (
                      <div className="arag-spec-row" key={k}>
                        <span className="arag-spec-k">{k}</span>
                        <span className="arag-spec-v">{String(v)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* documents */}
                <div>
                  <div className="arag-docs-title">
                    <Icon.doc /> Documents{" "}
                    <span className="arag-count">{docs.length}</span>
                  </div>
                  {docs.length === 0 ? (
                    <div className="arag-empty">No documents uploaded yet.</div>
                  ) : (
                    docs.map((d) => {
                      const st = (d.status || "").toUpperCase();
                      return (
                        <div key={d.id} className="arag-doc">
                          <span className="arag-doc-type">
                            {ext(d.file_name)}
                          </span>
                          <div className="arag-doc-info">
                            <div className="arag-doc-name">{d.file_name}</div>
                            <div className="arag-doc-meta">
                              {d.num_chunks || 0} chunks
                            </div>
                          </div>
                          <span
                            className={`arag-badge ${st === "INDEXED" ? "indexed" : st === "PROCESSING" ? "processing" : ""}`}
                          >
                            {d.status}
                          </span>
                        </div>
                      );
                    })
                  )}
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
};

export default AdminRAGPage;
