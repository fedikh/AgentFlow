import React, { useState, useEffect } from "react";
import { listSpaces, listDocuments } from "../../services/ragApi";
import "../../styles/it/rag.css";

/**
 * Admin RAG Spaces — READ ONLY
 * Admin sees all RAG spaces across all departments.
 * No create, no upload, no delete, no chat.
 * Just monitoring: which spaces exist, how many docs, which department, status.
 */
const AdminRAGPage = () => {
  const [spaces, setSpaces] = useState([]);
  const [selected, setSelected] = useState(null);
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadSpaces();
  }, []);

  const loadSpaces = async () => {
    setLoading(true);
    try {
      const data = await listSpaces();
      setSpaces(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const selectSpace = async (space) => {
    setSelected(space);
    try {
      const data = await listDocuments(space.id);
      setDocs(data);
    } catch (e) {
      setError(e.message);
    }
  };

  // Group spaces by department
  const grouped = {};
  spaces.forEach((s) => {
    const dept = s.department_name || "No department";
    if (!grouped[dept]) grouped[dept] = [];
    grouped[dept].push(s);
  });

  return (
    <div className="rag-page">
      <h1 className="rag-title">RAG Spaces — Overview</h1>
      <p className="rag-sub">
        Monitor all RAG spaces across your organization (read-only)
      </p>

      {error && (
        <div className="rag-error">
          {error}{" "}
          <span
            onClick={() => setError("")}
            style={{ cursor: "pointer", marginLeft: 8 }}
          >
            x
          </span>
        </div>
      )}

      {loading && <p style={{ color: "#9CA3AF", fontSize: 13 }}>Loading...</p>}

      {!loading && (
        <div className="rag-layout">
          {/* ── Left: spaces grouped by department ── */}
          <div className="rag-sidebar">
            <div className="rag-sidebar-header">
              <span className="rag-sidebar-title">
                All Spaces ({spaces.length})
              </span>
            </div>

            {spaces.length === 0 && (
              <p className="rag-empty">No RAG spaces created yet</p>
            )}

            {Object.entries(grouped).map(([deptName, deptSpaces]) => (
              <div key={deptName} style={{ marginBottom: 12 }}>
                <div
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    color: "#6B7280",
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                    padding: "6px 12px 4px",
                  }}
                >
                  {deptName} ({deptSpaces.length})
                </div>
                {deptSpaces.map((s) => (
                  <div
                    key={s.id}
                    className={`rag-space-item ${selected?.id === s.id ? "active" : ""}`}
                    onClick={() => selectSpace(s)}
                  >
                    <div className="rag-space-name">{s.name}</div>
                    <div className="rag-space-meta">
                      {s.num_documents} doc(s) · {s.num_chunks} chunks
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>

          {/* ── Right: space details (read-only) ── */}
          <div className="rag-main">
            {!selected ? (
              <div className="rag-placeholder">
                <p>Select a RAG space to view its details</p>
              </div>
            ) : (
              <>
                {/* Header */}
                <div className="rag-detail-header">
                  <div>
                    <h2 className="rag-detail-title">{selected.name}</h2>
                    <p className="rag-detail-desc">
                      {selected.description || "No description"}
                      {selected.department_name && (
                        <span
                          style={{
                            marginLeft: 8,
                            fontSize: 11,
                            fontWeight: 500,
                            padding: "2px 8px",
                            borderRadius: 4,
                            background: "#EFF6FF",
                            color: "#1D4ED8",
                            border: "1px solid #BFDBFE",
                          }}
                        >
                          {selected.department_name}
                        </span>
                      )}
                    </p>
                  </div>
                  <div className="rag-config-pills">
                    <span className="rag-pill">
                      Chunks: {selected.chunk_size}
                    </span>
                    <span className="rag-pill">
                      Overlap: {selected.chunk_overlap}
                    </span>
                    <span className="rag-pill">Top-K: {selected.top_k}</span>
                    <span className="rag-pill">{selected.chunk_strategy}</span>
                  </div>
                </div>

                {/* Stats cards */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr 1fr",
                    gap: 12,
                    marginBottom: 20,
                  }}
                >
                  <div
                    style={{
                      padding: "14px 16px",
                      borderRadius: 10,
                      background: "#F0FDF4",
                      border: "1px solid #BBF7D0",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 22,
                        fontWeight: 700,
                        color: "#166534",
                      }}
                    >
                      {selected.num_documents}
                    </div>
                    <div
                      style={{ fontSize: 12, color: "#6B7280", marginTop: 2 }}
                    >
                      Documents
                    </div>
                  </div>
                  <div
                    style={{
                      padding: "14px 16px",
                      borderRadius: 10,
                      background: "#EFF6FF",
                      border: "1px solid #BFDBFE",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 22,
                        fontWeight: 700,
                        color: "#1E40AF",
                      }}
                    >
                      {selected.num_chunks}
                    </div>
                    <div
                      style={{ fontSize: 12, color: "#6B7280", marginTop: 2 }}
                    >
                      Chunks
                    </div>
                  </div>
                  <div
                    style={{
                      padding: "14px 16px",
                      borderRadius: 10,
                      background: "#FEF3C7",
                      border: "1px solid #FCD34D",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 22,
                        fontWeight: 700,
                        color: "#92400E",
                      }}
                    >
                      {selected.chunk_strategy}
                    </div>
                    <div
                      style={{ fontSize: 12, color: "#6B7280", marginTop: 2 }}
                    >
                      Strategy
                    </div>
                  </div>
                </div>

                {/* Documents list (read-only) */}
                <div className="rag-section">
                  <div className="rag-section-header">
                    <span className="rag-section-title">
                      Documents ({docs.length})
                    </span>
                  </div>

                  {docs.length === 0 && (
                    <p className="rag-empty">No documents uploaded yet</p>
                  )}

                  {docs.map((d) => (
                    <div key={d.id} className="rag-doc-item">
                      <div className="rag-doc-icon">PDF</div>
                      <div className="rag-doc-info">
                        <div className="rag-doc-name">{d.file_name}</div>
                        <div className="rag-doc-meta">
                          {d.num_chunks} chunks — {d.status}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminRAGPage;
