import React from "react";

const DocModal = ({
  modal,
  modalData,
  modalLoading,
  closeModal,
  showJson,
  setShowJson,
  editMode,
  editDoc,
  setEditDoc,
  savingEdit,
  startEdit,
  cancelEdit,
  saveEdit,
  editField,
  removeBlock,
  addSection,
  addImage = () => {},
  uploadingImage = false,
  spaceId,
}) => {
  if (!modal) return null;

  const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
  const imgUrl = (path) =>
    `${API}/rag/spaces/${spaceId}/image?path=${encodeURIComponent(path || "")}`;

  return (
    <div
      className="rag-modal-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget && !editMode) closeModal();
      }}
    >
      <div className="rag-modal">
        <div className="rag-modal-header">
          <div className="rag-modal-title">
            {modal === "loaded" && "Loaded Text"}
            {modal === "parsed" &&
              (editMode ? "Edit Parsed Document" : "Parsed Document")}
            {modal === "chunks" && "Chunks"}
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            {modal === "parsed" && !editMode && (
              <>
                <button
                  className={`rag-btn rag-btn-sm ${showJson ? "rag-btn-dark" : ""}`}
                  onClick={() => setShowJson(!showJson)}
                >
                  {showJson ? "Blocks" : "JSON"}
                </button>
                {modalData?.status !== "INDEXED" && (
                  <button className="rag-btn rag-btn-sm" onClick={startEdit}>
                    ✎ Edit
                  </button>
                )}
              </>
            )}
            {modal === "parsed" && editMode && (
              <>
                <button
                  className="rag-btn rag-btn-sm rag-btn-dark"
                  onClick={saveEdit}
                  disabled={savingEdit}
                >
                  {savingEdit ? "Saving…" : "Save"}
                </button>
                <button
                  className="rag-btn rag-btn-sm"
                  onClick={cancelEdit}
                  disabled={savingEdit}
                >
                  Cancel
                </button>
              </>
            )}
            {!editMode && (
              <button className="rag-btn rag-btn-sm" onClick={closeModal}>
                ✕ Close
              </button>
            )}
          </div>
        </div>
        <div className="rag-modal-body">
          {modalLoading && <div className="rag-empty-state">Loading…</div>}

          {modal === "loaded" && modalData && !modalLoading && (
            <>
              <div className="rag-stats rag-stats-4">
                {[
                  { l: "Type", v: modalData.file_type },
                  { l: "Category", v: modalData.category },
                  { l: "Pages", v: modalData.num_pages },
                  {
                    l: "Characters",
                    v: modalData.total_chars?.toLocaleString(),
                  },
                ].map((s, i) => (
                  <div key={i} className="rag-stat">
                    <div className="rag-stat-label">{s.l}</div>
                    <div className="rag-stat-value">{s.v}</div>
                  </div>
                ))}
              </div>
              <div className="rag-raw-text">
                {modalData.raw_text || "Empty"}
              </div>
            </>
          )}

          {modal === "parsed" && modalData && !modalLoading && (
            <>
              <div className="rag-stats rag-stats-4">
                {[
                  { l: "Sections", v: modalData.total_sections },
                  { l: "Tables", v: modalData.total_tables },
                  {
                    l: "Characters",
                    v: modalData.total_chars?.toLocaleString(),
                  },
                  { l: "OCR", v: modalData.ocr_quality },
                ].map((s, i) => (
                  <div key={i} className="rag-stat">
                    <div className="rag-stat-label">{s.l}</div>
                    <div className="rag-stat-value">{s.v}</div>
                  </div>
                ))}
              </div>
              {modalData.ocr_issues?.length > 0 && (
                <div className="rag-ocr-warn">
                  {modalData.ocr_issues.join(" · ")}
                </div>
              )}
              {modalData.status === "INDEXED" && !editMode && (
                <div className="rag-edit-note">
                  This document is already indexed — parsed content is
                  read-only. To change it, delete and re-upload the document.
                </div>
              )}

              {editMode && editDoc ? (
                <>
                  <div className="rag-edit-note">
                    Edit sections, tables and images below. Saving keeps the
                    document at <strong>Parsed</strong> — re-process to rebuild
                    chunks from your changes.
                  </div>
                  <input
                    className="rag-edit-input"
                    placeholder="Document title"
                    value={editDoc.parsed_document.title || ""}
                    onChange={(e) =>
                      setEditDoc((prev) => ({
                        ...prev,
                        parsed_document: {
                          ...prev.parsed_document,
                          title: e.target.value,
                        },
                      }))
                    }
                  />
                  {editDoc.parsed_document.sections?.map((sec, i) => (
                    <div key={`es${i}`} className="rag-block">
                      <div className="rag-block-header">
                        <span className="rag-block-tag">Section {i + 1}</span>
                        <button
                          className="rag-btn rag-btn-xs rag-btn-red"
                          onClick={() => removeBlock("sections", i)}
                        >
                          Remove
                        </button>
                      </div>
                      <input
                        className="rag-edit-input"
                        placeholder="Heading"
                        value={sec.heading || ""}
                        onChange={(e) =>
                          editField("sections", i, "heading", e.target.value)
                        }
                      />
                      <textarea
                        className="rag-edit-textarea"
                        rows={5}
                        placeholder="Content"
                        value={sec.content || ""}
                        onChange={(e) =>
                          editField("sections", i, "content", e.target.value)
                        }
                      />
                      <div className="rag-edit-fields">
                        <label className="rag-edit-field">
                          Level
                          <input
                            type="number"
                            min={1}
                            max={6}
                            value={sec.level || 1}
                            onChange={(e) =>
                              editField(
                                "sections",
                                i,
                                "level",
                                parseInt(e.target.value) || 1,
                              )
                            }
                          />
                        </label>
                        <label className="rag-edit-field">
                          Page
                          <input
                            type="number"
                            min={1}
                            value={sec.page || 1}
                            onChange={(e) =>
                              editField(
                                "sections",
                                i,
                                "page",
                                parseInt(e.target.value) || 1,
                              )
                            }
                          />
                        </label>
                      </div>
                    </div>
                  ))}
                  {editDoc.parsed_document.tables?.map((tab, i) => (
                    <div key={`et${i}`} className="rag-block rag-block-table">
                      <div className="rag-block-header">
                        <span
                          className="rag-block-tag"
                          style={{ background: "#FEF3C7", color: "#92400E" }}
                        >
                          Table {i + 1} — {tab.num_rows}×{tab.num_cols}
                        </span>
                        <button
                          className="rag-btn rag-btn-xs rag-btn-red"
                          onClick={() => removeBlock("tables", i)}
                        >
                          Remove
                        </button>
                      </div>
                      <textarea
                        className="rag-edit-textarea rag-block-content-mono"
                        rows={6}
                        placeholder="Table content (markdown)"
                        value={tab.content || ""}
                        onChange={(e) =>
                          editField("tables", i, "content", e.target.value)
                        }
                      />
                      <div className="rag-edit-fields">
                        <label className="rag-edit-field">
                          Page
                          <input
                            type="number"
                            min={1}
                            value={tab.page || 1}
                            onChange={(e) =>
                              editField(
                                "tables",
                                i,
                                "page",
                                parseInt(e.target.value) || 1,
                              )
                            }
                          />
                        </label>
                      </div>
                    </div>
                  ))}
                  {editDoc.parsed_document.images?.map((img, i) => (
                    <div key={`ei${i}`} className="rag-block">
                      <div className="rag-block-header">
                        <span className="rag-block-tag">Image {i + 1}</span>
                        <button
                          className="rag-btn rag-btn-xs rag-btn-red"
                          onClick={() => removeBlock("images", i)}
                        >
                          Remove
                        </button>
                      </div>
                      <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
                        <img
                          src={imgUrl(img.image_path)}
                          alt={`Image ${i + 1}`}
                          style={{
                            width: 140,
                            height: 140,
                            objectFit: "contain",
                            borderRadius: 8,
                            background: "#F8FAFC",
                            border: "1px solid #F1F1F1",
                            flexShrink: 0,
                          }}
                          onError={(e) => {
                            e.target.style.opacity = 0.2;
                          }}
                        />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <textarea
                            className="rag-edit-textarea"
                            rows={3}
                            placeholder="Description (used for retrieval)"
                            value={img.text_for_embedding || ""}
                            onChange={(e) =>
                              editField("images", i, "text_for_embedding", e.target.value)
                            }
                          />
                          <input
                            className="rag-edit-input"
                            placeholder="Caption (optional)"
                            value={img.caption || ""}
                            onChange={(e) =>
                              editField("images", i, "caption", e.target.value)
                            }
                          />
                          <input
                            className="rag-edit-input"
                            placeholder="OCR text (optional)"
                            value={img.ocr_text || ""}
                            onChange={(e) =>
                              editField("images", i, "ocr_text", e.target.value)
                            }
                          />
                          <div className="rag-edit-fields">
                            <label className="rag-edit-field">
                              Page
                              <input
                                type="number"
                                min={1}
                                value={img.page || 1}
                                onChange={(e) =>
                                  editField(
                                    "images",
                                    i,
                                    "page",
                                    parseInt(e.target.value) || 1,
                                  )
                                }
                              />
                            </label>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                  <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                    <button className="rag-btn rag-btn-sm" onClick={addSection}>
                      + Add section
                    </button>
                    <label
                      className="rag-btn rag-btn-sm"
                      style={{ cursor: uploadingImage ? "default" : "pointer" }}
                    >
                      {uploadingImage ? "Uploading…" : "+ Add image"}
                      <input
                        type="file"
                        accept="image/*"
                        style={{ display: "none" }}
                        disabled={uploadingImage}
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          if (f) addImage(f);
                          e.target.value = "";
                        }}
                      />
                    </label>
                  </div>
                </>
              ) : showJson ? (
                <div className="rag-json">
                  <pre>
                    {JSON.stringify(modalData.parsed_document, null, 2)}
                  </pre>
                </div>
              ) : (
                <>
                  {modalData.parsed_document?.sections?.map((sec, i) => (
                    <div key={`s${i}`} className="rag-block">
                      <div className="rag-block-header">
                        <div className="rag-heading-tag">
                          <span className="rag-block-tag">Section {i + 1}</span>
                          {sec.heading && (
                            <span style={{ fontSize: 13, fontWeight: 600 }}>
                              {sec.heading}
                            </span>
                          )}
                          <span className="rag-h-level">H{sec.level}</span>
                        </div>
                        <span className="rag-block-meta">
                          p.{sec.page} · {sec.content?.length}c
                        </span>
                      </div>
                      <pre className="rag-block-content">{sec.content}</pre>
                    </div>
                  ))}
                  {modalData.parsed_document?.tables?.map((tab, i) => (
                    <div key={`t${i}`} className="rag-block rag-block-table">
                      <div className="rag-block-header">
                        <span
                          className="rag-block-tag"
                          style={{ background: "#FEF3C7", color: "#92400E" }}
                        >
                          Table {i + 1} — {tab.num_rows}×{tab.num_cols}
                        </span>
                        <span className="rag-block-meta">p.{tab.page}</span>
                      </div>
                      {tab.headers?.length > 0 && (
                        <div
                          style={{
                            fontSize: 11,
                            color: "#92400E",
                            marginBottom: 6,
                          }}
                        >
                          {tab.headers.join(", ")}
                        </div>
                      )}
                      <pre className="rag-block-content rag-block-content-mono">
                        {tab.content}
                      </pre>
                    </div>
                  ))}
                  {modalData.parsed_document?.images?.map((img, i) => (
                    <div key={`i${i}`} className="rag-block">
                      <div className="rag-block-header">
                        <span className="rag-block-tag">Image {i + 1}</span>
                        <span className="rag-block-meta">p.{img.page}</span>
                      </div>
                      <div
                        style={{
                          display: "flex",
                          gap: 14,
                          alignItems: "flex-start",
                        }}
                      >
                        <img
                          src={`${import.meta.env.VITE_API_URL || "http://localhost:8000/api"}/rag/spaces/${spaceId}/image?path=${encodeURIComponent(img.image_path)}`}
                          alt={`Image page ${img.page}`}
                          style={{
                            width: 160,
                            height: 160,
                            objectFit: "contain",
                            borderRadius: 8,
                            background: "#F8FAFC",
                            border: "1px solid #F1F1F1",
                            flexShrink: 0,
                          }}
                          onError={(e) => {
                            e.target.style.opacity = 0.2;
                          }}
                        />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          {img.text_for_embedding ? (
                            <div
                              style={{
                                fontSize: 13,
                                lineHeight: 1.6,
                                color: "#1A1A1A",
                              }}
                            >
                              {img.text_for_embedding}
                            </div>
                          ) : img.caption ? (
                            <div style={{ fontSize: 13 }}>{img.caption}</div>
                          ) : (
                            <div style={{ fontSize: 13, color: "#9CA3AF" }}>
                              No description
                            </div>
                          )}
                          {img.ocr_text && (
                            <div
                              style={{
                                fontSize: 12,
                                color: "#525252",
                                marginTop: 6,
                              }}
                            >
                              OCR: {img.ocr_text}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </>
              )}
            </>
          )}

          {modal === "chunks" && modalData && !modalLoading && (
            <>
              <div className="rag-stats rag-stats-3">
                {[
                  { l: "Chunks", v: modalData.length },
                  {
                    l: "Avg length",
                    v: Math.round(
                      modalData.reduce((s, c) => s + c.content.length, 0) /
                        (modalData.length || 1),
                    ),
                  },
                  {
                    l: "Total chars",
                    v: modalData
                      .reduce((s, c) => s + c.content.length, 0)
                      .toLocaleString(),
                  },
                ].map((s, i) => (
                  <div key={i} className="rag-stat">
                    <div className="rag-stat-label">{s.l}</div>
                    <div className="rag-stat-value">{s.v}</div>
                  </div>
                ))}
              </div>
              {modalData.map((c) => (
                <div key={c.id} className="rag-block">
                  <div className="rag-block-header">
                    <span className="rag-block-tag">
                      Chunk {c.chunk_index + 1}
                    </span>
                    <span className="rag-block-meta">
                      p.{c.page} · {c.content.length}c
                    </span>
                  </div>
                  <pre className="rag-block-content">{c.content}</pre>
                </div>
              ))}
            </>
          )}

        </div>
      </div>
    </div>
  );
};

export default DocModal;
