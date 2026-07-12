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
  const [elementsView, setElementsView] = React.useState(false);
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
                  className={`rag-btn rag-btn-sm ${elementsView ? "rag-btn-dark" : ""}`}
                  onClick={() => {
                    setElementsView(!elementsView);
                    setShowJson(false);
                  }}
                >
                  {elementsView ? "Blocks" : "Elements"}
                </button>
                <button
                  className={`rag-btn rag-btn-sm ${showJson ? "rag-btn-dark" : ""}`}
                  onClick={() => {
                    setShowJson(!showJson);
                    setElementsView(false);
                  }}
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
            <LoadedView data={modalData} />
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
              ) : elementsView ? (
                <ElementsView
                  doc={modalData.parsed_document}
                  imgUrl={imgUrl}
                />
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
                  {modalData.parsed_document?.metadata?.vision?.reason &&
                    modalData.parsed_document?.images?.length > 0 && (
                      <div
                        className="rag-block"
                        style={{
                          background: "#FEF2F2",
                          border: "1px solid #FECACA",
                          color: "#991B1B",
                          fontSize: 13,
                          lineHeight: 1.6,
                        }}
                      >
                        {modalData.parsed_document.metadata.vision.reason ===
                        "quota_exceeded"
                          ? "Image descriptions were not generated — the vision API (Gemini) quota was exceeded (HTTP 429). Enable billing on the VISION_API_KEY, or wait for the free-tier quota to reset, then re-run Load & Parse."
                          : "Image descriptions were not generated — a vision API error occurred. Check the server logs, then re-run Load & Parse."}
                      </div>
                    )}
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

// ── Element-schema viewer (new parsing format) ──

const TYPE_COLOR = {
  heading: "#2563EB",
  paragraph: "#374151",
  list_item: "#6B7280",
  table: "#B45309",
  image: "#7C3AED",
  code: "#0F766E",
  quote: "#9333EA",
};

// ── Tree viewer for structured data (JSON / XML element schema) ──

const TREE_TYPES = [
  "json_object",
  "json_array",
  "json_key_value",
  "json_null",
  "xml_element",
];

const JSON_VALUE_COLOR = {
  string: "#059669",
  number: "#0891B2",
  boolean: "#7C3AED",
  null: "#94A3B8",
};

function JsonValue({ value, valueType }) {
  const color = JSON_VALUE_COLOR[valueType] || "#334155";
  const text =
    valueType === "string"
      ? `"${value}"`
      : value === null || value === undefined
        ? "null"
        : String(value);
  return <span style={{ color }}>{text}</span>;
}

function TreeNode({ node, byId, depth, mode }) {
  const initOpen =
    mode === "expand" ? true : mode === "collapse" ? depth < 1 : depth < 2;
  const [open, setOpen] = React.useState(initOpen);
  const [hover, setHover] = React.useState(false);
  const childIds = node.relationships?.children || [];
  const has = childIds.length > 0;
  const c = node.content || {};
  const attrs = c.attributes || {};
  const path = node.location?.xpath || node.location?.path || "";
  const isXml = node.type === "xml_element";
  const isPrim = node.type === "json_key_value" || node.type === "json_null";

  const name = isXml
    ? c.tag
    : c.key != null
      ? c.key
      : !path || path === "$"
        ? "root"
        : path.replace(/\]$/, "").split(/[.[/]/).filter(Boolean).pop() || "root";

  return (
    <div style={{ borderLeft: depth ? "1px solid #EDF1F6" : "none", marginLeft: depth ? 7 : 0 }}>
      <div
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onClick={() => has && setOpen(!open)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 7,
          padding: "3px 8px",
          fontSize: 12.5,
          lineHeight: 1.6,
          borderRadius: 5,
          background: hover ? "#F6F9FC" : "transparent",
          cursor: has ? "pointer" : "default",
        }}
      >
        <span style={{ width: 10, flexShrink: 0, color: "#CBD5E1", fontSize: 9 }}>
          {has ? (open ? "▼" : "▶") : ""}
        </span>
        <span
          style={{
            fontWeight: 600,
            color: isXml ? "#7C3AED" : "#0F172A",
            whiteSpace: "nowrap",
          }}
        >
          {isXml ? `<${name}>` : name}
        </span>

        {isPrim && (
          <>
            <span style={{ color: "#94A3B8" }}>:</span>
            <JsonValue value={c.value} valueType={c.json_type} />
          </>
        )}
        {node.type === "json_object" && (
          <span style={{ color: "#94A3B8" }}>{`{${c.keys_count}}`}</span>
        )}
        {node.type === "json_array" && (
          <span style={{ color: "#B45309" }}>{`[${c.items_count}]`}</span>
        )}
        {node.type === "xml_element" &&
          Object.entries(attrs).map(([k, v]) => (
            <span
              key={k}
              style={{
                fontSize: 11,
                color: "#475569",
                background: "#F1F5F9",
                padding: "0 5px",
                borderRadius: 3,
                whiteSpace: "nowrap",
              }}
            >
              {k}=<span style={{ color: "#059669" }}>{String(v)}</span>
            </span>
          ))}
        {node.type === "xml_element" && c.text && (
          <span style={{ color: "#059669" }}>{c.text}</span>
        )}
        {node.type === "xml_element" && !c.text && c.child_count > 0 && (
          <span style={{ color: "#94A3B8" }}>{`{${c.child_count}}`}</span>
        )}

        {hover && path && (
          <span
            style={{
              marginLeft: "auto",
              fontSize: 10.5,
              color: "#CBD5E1",
              whiteSpace: "nowrap",
              fontFamily: "var(--mono, monospace)",
            }}
          >
            {path}
          </span>
        )}
      </div>
      {open &&
        has &&
        childIds.map(
          (cid) =>
            byId[cid] && (
              <TreeNode key={cid} node={byId[cid]} byId={byId} depth={depth + 1} mode={mode} />
            ),
        )}
    </div>
  );
}

function TreeView({ doc }) {
  const els = doc?.elements || [];
  const meta = doc?.metadata || {};
  const info = doc?.document || {};
  const [mode, setMode] = React.useState("default");
  const [version, setVersion] = React.useState(0);

  const byId = {};
  els.forEach((e) => {
    byId[e.id] = e;
  });
  const roots = els.filter((e) => e.parent_id == null);

  const setAll = (m) => {
    setMode(m);
    setVersion((v) => v + 1); // remount tree so every node re-reads its open state
  };

  return (
    <div>
      <div
        className="rag-block"
        style={{
          background: "#F8FAFC",
          border: "1px solid #E2E8F0",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div style={{ fontSize: 13, minWidth: 0 }}>
          <b>{info.name || meta.source || "Document"}</b>{" "}
          <span style={{ color: "#64748B" }}>
            · {(meta.source_type || "").toUpperCase()} · root:{" "}
            <code style={{ color: "#334155" }}>{meta.root ?? "—"}</code> · {els.length} nodes
          </span>
        </div>
        <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
          <button className="rag-btn rag-btn-xs" onClick={() => setAll("expand")}>
            Expand all
          </button>
          <button className="rag-btn rag-btn-xs" onClick={() => setAll("collapse")}>
            Collapse all
          </button>
        </div>
      </div>
      <div
        key={version}
        className="rag-block"
        style={{ fontFamily: "var(--mono, monospace)", padding: "8px 6px" }}
      >
        {roots.map((r) => (
          <TreeNode key={r.id} node={r} byId={byId} depth={0} mode={mode} />
        ))}
      </div>
    </div>
  );
}

// ── Table viewer for structured tabular data (CSV / Excel) ──

const _TH = {
  border: "1px solid #E5E7EB",
  padding: "5px 9px",
  background: "#F9FAFB",
  textAlign: "left",
  whiteSpace: "nowrap",
};
const _TD = { border: "1px solid #E5E7EB", padding: "4px 9px" };

function fmtCell(v) {
  if (v === null || v === undefined)
    return <span style={{ color: "#CBD5E1" }}>—</span>;
  return String(v);
}

function TableGrid({ table }) {
  const c = table.content || {};
  const columns = c.columns || [];
  const rows = c.rows || [];
  const meta = table.metadata || {};
  const shown = rows.slice(0, 100);
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", fontSize: 12, width: "100%" }}>
        <thead>
          <tr>
            <th style={{ ..._TH, color: "#94A3B8" }}>#</th>
            {columns.map((col) => (
              <th key={col.name} style={_TH}>
                {col.name}
                <span
                  style={{
                    marginLeft: 6,
                    fontSize: 9,
                    color: "#64748B",
                    background: "#EEF2F7",
                    padding: "1px 4px",
                    borderRadius: 3,
                    textTransform: "uppercase",
                  }}
                >
                  {col.type}
                </span>
                {col.nullable && (
                  <span style={{ color: "#CBD5E1", marginLeft: 3 }}>?</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => (
            <tr key={r.index}>
              <td style={{ ..._TD, color: "#94A3B8" }}>{r.index}</td>
              {columns.map((col) => (
                <td key={col.name} style={_TD}>
                  {fmtCell(r.values ? r.values[col.name] : undefined)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > shown.length && (
        <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 6 }}>
          Showing {shown.length} of {meta.row_count ?? rows.length} rows
        </div>
      )}
    </div>
  );
}

function SheetBlock({ sheet, byId }) {
  const [open, setOpen] = React.useState(true);
  const c = sheet.content || {};
  const children = (sheet.relationships?.children || [])
    .map((id) => byId[id])
    .filter(Boolean);
  const tables = children.filter((e) => e.type === "table");
  const formulas = children.filter((e) => e.type === "formula");
  const merged = children.filter((e) => e.type === "merged_cell");
  const chunks = children.filter((e) => e.type === "cell_block");
  const charts = children.filter((e) => e.type === "chart");
  return (
    <div className="rag-block">
      <div
        onClick={() => setOpen(!open)}
        style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}
      >
        <span style={{ color: "#CBD5E1", fontSize: 10 }}>{open ? "▼" : "▶"}</span>
        <b style={{ fontSize: 13 }}>{c.name}</b>
        <span style={{ color: "#94A3B8", fontSize: 12 }}>
          {sheet.location?.range} · {sheet.metadata?.row_count ?? 0} rows ×{" "}
          {sheet.metadata?.column_count ?? 0} cols
        </span>
      </div>
      {open && (
        <div style={{ marginTop: 10 }}>
          {tables.map((t) => (
            <div key={t.id} style={{ marginBottom: 12 }}>
              {tables.length > 1 && (
                <div style={{ fontSize: 11, color: "#94A3B8", marginBottom: 3 }}>
                  {t.location?.range}
                </div>
              )}
              <TableGrid table={t} />
            </div>
          ))}
          {charts.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "#7C3AED" }}>
                CHARTS ({charts.length})
              </div>
              {charts.map((ch) => (
                <div key={ch.id} style={{ fontSize: 12, marginTop: 3 }}>
                  <span
                    style={{
                      fontSize: 9,
                      textTransform: "uppercase",
                      color: "#fff",
                      background: "#7C3AED",
                      padding: "1px 5px",
                      borderRadius: 3,
                      marginRight: 6,
                    }}
                  >
                    {ch.content.chart_type}
                  </span>
                  <b>{ch.content.title || "(untitled)"}</b>
                  {ch.content.summary_text && (
                    <div style={{ color: "#64748B", whiteSpace: "pre-wrap", marginTop: 2 }}>
                      {ch.content.summary_text}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
          {formulas.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "#0F766E" }}>
                FORMULAS ({formulas.length})
              </div>
              {formulas.map((f) => (
                <div
                  key={f.id}
                  style={{ fontSize: 12, fontFamily: "var(--mono, monospace)" }}
                >
                  <b>{f.content.cell}</b>: {f.content.formula}
                  {f.content.calculated_value != null && (
                    <span style={{ color: "#059669" }}>
                      {" "}= {String(f.content.calculated_value)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
          {merged.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "#B45309" }}>
                MERGED CELLS ({merged.length})
              </div>
              {merged.map((m) => (
                <div key={m.id} style={{ fontSize: 12 }}>
                  <b>{m.content.range}</b>: {String(m.content.value ?? "")}
                </div>
              ))}
            </div>
          )}
          {chunks.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "#2563EB" }}>
                RAG CHUNKS ({chunks.length})
              </div>
              {chunks.map((cb) => (
                <details key={cb.id} style={{ fontSize: 12, marginTop: 4 }}>
                  <summary style={{ cursor: "pointer" }}>
                    <b>{cb.location?.range}</b>
                    <span style={{ color: "#94A3B8" }}>
                      {" "}· {cb.content.block_type} · {cb.content.token_count} tok
                    </span>
                  </summary>
                  <pre
                    className="rag-block-content rag-block-content-mono"
                    style={{ fontSize: 11, marginTop: 4 }}
                  >
                    {cb.content.text}
                  </pre>
                </details>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TableView({ doc }) {
  const els = doc?.elements || [];
  const meta = doc?.metadata || {};
  const info = doc?.document || {};
  const byId = {};
  els.forEach((e) => {
    byId[e.id] = e;
  });
  const wb = els.find((e) => e.type === "workbook");
  const tables = els.filter((e) => e.type === "table");

  const header = (
    <div className="rag-block" style={{ background: "#F8FAFC", border: "1px solid #E2E8F0" }}>
      <div style={{ fontSize: 13 }}>
        <b>{info.name || meta.source || "Document"}</b>{" "}
        <span style={{ color: "#64748B" }}>
          · {(meta.source_type || "").toUpperCase()}
          {wb
            ? ` · ${wb.content.sheet_count} sheet(s)${meta.excel_engine ? ` · ${meta.excel_engine}` : ""}`
            : ` · ${tables.length} table · ${tables[0]?.metadata?.row_count ?? 0} rows`}
        </span>
      </div>
    </div>
  );

  if (wb) {
    return (
      <div>
        {header}
        {(wb.relationships?.children || []).map(
          (id) => byId[id] && <SheetBlock key={id} sheet={byId[id]} byId={byId} />,
        )}
      </div>
    );
  }
  return (
    <div>
      {header}
      {tables.map((t) => (
        <div key={t.id} className="rag-block">
          <TableGrid table={t} />
        </div>
      ))}
    </div>
  );
}

function TableBlock({ content }) {
  const headers = content.headers || [];
  const rows = content.rows || [];
  if (!headers.length && !rows.length) {
    return (
      <pre className="rag-block-content rag-block-content-mono">
        {content.markdown || ""}
      </pre>
    );
  }
  return (
    <div style={{ overflowX: "auto" }}>
      {content.caption && (
        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
          {content.caption}
        </div>
      )}
      <table style={{ borderCollapse: "collapse", fontSize: 12, width: "100%" }}>
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th
                key={i}
                style={{
                  border: "1px solid #E5E7EB",
                  padding: "4px 8px",
                  background: "#F9FAFB",
                  textAlign: "left",
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={ri}>
              {headers.map((h, ci) => (
                <td
                  key={ci}
                  style={{ border: "1px solid #E5E7EB", padding: "4px 8px" }}
                >
                  {r[h]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderElementContent(el, imgUrl) {
  const c = el.content || {};
  if (el.type === "heading") {
    return (
      <div style={{ fontSize: 14, fontWeight: 700, color: "#0F172A" }}>
        {c.text}
      </div>
    );
  }
  if (el.type === "paragraph" || el.type === "list_item") {
    return (
      <div style={{ fontSize: 13, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
        {el.type === "list_item" ? "• " : ""}
        {c.text}
      </div>
    );
  }
  if (el.type === "code") {
    return (
      <div>
        {c.language && (
          <div style={{ fontSize: 11, color: "#0F766E", marginBottom: 4 }}>
            {c.language}
          </div>
        )}
        <pre
          className="rag-block-content rag-block-content-mono"
          style={{
            background: "#0B1020",
            color: "#E5E7EB",
            padding: 10,
            borderRadius: 6,
            overflowX: "auto",
            margin: 0,
          }}
        >
          {c.text}
        </pre>
      </div>
    );
  }
  if (el.type === "quote") {
    return (
      <div
        style={{
          fontSize: 13,
          lineHeight: 1.6,
          fontStyle: "italic",
          color: "#4B5563",
          borderLeft: "3px solid #9333EA",
          paddingLeft: 10,
        }}
      >
        {c.text}
      </div>
    );
  }
  if (el.type === "table") return <TableBlock content={c} />;
  if (el.type === "image") {
    return (
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        <img
          src={c.src || imgUrl(c.image_path)}
          alt={c.caption || c.alt || "image"}
          style={{
            width: 120,
            height: 120,
            objectFit: "contain",
            border: "1px solid #F1F1F1",
            borderRadius: 6,
            background: "#F8FAFC",
            flexShrink: 0,
          }}
          onError={(e) => {
            e.target.style.opacity = 0.2;
          }}
        />
        <div style={{ fontSize: 12, lineHeight: 1.5, color: "#374151" }}>
          {c.caption && <div style={{ fontWeight: 600 }}>{c.caption}</div>}
          {c.text_for_embedding ? (
            <div>{c.text_for_embedding}</div>
          ) : (
            <div style={{ color: "#9CA3AF" }}>No description</div>
          )}
        </div>
      </div>
    );
  }
  return null;
}

function LoadedView({ data }) {
  const meta = data.metadata || {};
  const url = meta.source_url || meta.canonical_url || "";
  const isWeb = data.category === "web" || !!url;

  if (!isWeb) {
    return (
      <>
        <div className="rag-stats rag-stats-4">
          {[
            { l: "Type", v: data.file_type },
            { l: "Category", v: data.category },
            { l: "Pages", v: data.num_pages },
            { l: "Characters", v: data.total_chars?.toLocaleString() },
          ].map((s, i) => (
            <div key={i} className="rag-stat">
              <div className="rag-stat-label">{s.l}</div>
              <div className="rag-stat-value">{s.v}</div>
            </div>
          ))}
        </div>
        <div className="rag-raw-text">{data.raw_text || "Empty"}</div>
      </>
    );
  }

  let domain = meta.domain;
  if (!domain && url) {
    try {
      domain = new URL(url).hostname;
    } catch {
      domain = "web";
    }
  }
  const chips = [
    meta.language && `🌍 ${meta.language}`,
    meta.author && `✍ ${meta.author}`,
    meta.published_at && `📅 ${meta.published_at}`,
  ].filter(Boolean);

  return (
    <>
      <div className="rag-wl-head">
        <div className="rag-wl-top">
          <span className="rag-wl-domain">🌐 {domain || "web"}</span>
          {meta.engine && <span className="rag-wl-badge">{meta.engine}</span>}
          <span className="rag-wl-badge" style={{ marginLeft: "auto" }}>
            {(data.total_chars || 0).toLocaleString()} chars
          </span>
        </div>
        <div className="rag-wl-title">{meta.title || data.file_name}</div>
        {url && (
          <a className="rag-wl-url" href={url} target="_blank" rel="noreferrer">
            {url}
          </a>
        )}
        {meta.description && <div className="rag-wl-desc">{meta.description}</div>}
        {chips.length > 0 && (
          <div className="rag-wl-meta">
            {chips.map((c, i) => (
              <span key={i} className="rag-wl-chip">
                {c}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="rag-wl-body">{data.raw_text || "Empty"}</div>
    </>
  );
}

function ElementsView({ doc, imgUrl }) {
  const els = doc?.elements || [];
  const info = doc?.document || {};
  const meta = doc?.metadata || {};

  // Tabular data (CSV / Excel) → table grid / workbook view.
  if (
    meta.source_type === "csv" ||
    meta.source_type === "xlsx" ||
    els.some((e) => e.type === "workbook" || e.type === "sheet")
  ) {
    return <TableView doc={doc} />;
  }

  // Structured data (JSON / XML) → collapsible tree instead of the flat list.
  if (
    meta.source_type === "json" ||
    meta.source_type === "xml" ||
    els.some((e) => TREE_TYPES.includes(e.type))
  ) {
    return <TreeView doc={doc} />;
  }

  if (!els.length) {
    return (
      <div style={{ padding: 20, color: "#9CA3AF", fontSize: 13 }}>
        No elements in this document. Re-run <b>Load &amp; Parse</b> to generate
        the element schema (PDF / DOCX / PPTX).
      </div>
    );
  }

  // Compute indent depth so the hierarchy reads as a tree. `section` carries
  // the current heading level forward so content nests under its heading;
  // nested list items indent further by their list_level.
  const rows = els.reduce((acc, el) => {
    const prev = acc.length ? acc[acc.length - 1].section : 0;
    const section = el.type === "heading" ? el.level || 1 : prev;
    const listLevel = el.metadata?.list_level || 1;
    const depth =
      el.type === "heading"
        ? section - 1
        : el.type === "list_item"
          ? section + (listLevel - 1)
          : section;
    acc.push({ el, depth, section });
    return acc;
  }, []);

  return (
    <div>
      <div
        className="rag-block"
        style={{ background: "#F8FAFC", border: "1px solid #E2E8F0" }}
      >
        <div style={{ fontSize: 13, lineHeight: 1.7 }}>
          <b>{info.name || meta.source || "Document"}</b>{" "}
          <span style={{ color: "#64748B" }}>
            · {(meta.file_type || "").toUpperCase()} · {meta.page_count} pages ·{" "}
            {els.length} elements
            {meta.language ? ` · ${meta.language}` : ""}
            {meta.parser?.name
              ? ` · ${meta.parser.name} ${meta.parser.version || ""}`
              : ""}
          </span>
        </div>
        {info.source?.filename && (
          <div style={{ fontSize: 12, color: "#94A3B8" }}>
            source: {info.source.type} · {info.source.filename}
          </div>
        )}
      </div>

      {meta.links && meta.links.length > 0 && (
        <details className="rag-block" style={{ fontSize: 12 }}>
          <summary style={{ cursor: "pointer", color: "#2563EB", fontWeight: 600 }}>
            LINKS ({meta.links.length})
          </summary>
          <div style={{ marginTop: 6, maxHeight: 220, overflowY: "auto" }}>
            {meta.links.map((l, i) => (
              <div key={i} style={{ marginBottom: 3 }}>
                <a
                  href={l.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: "#2563EB" }}
                >
                  {l.text || l.url}
                </a>
                <span style={{ color: "#CBD5E1" }}> — {l.url}</span>
              </div>
            ))}
          </div>
        </details>
      )}

      {rows.map(({ el, depth }, i) => (
        <div
          key={el.id || i}
          className="rag-block"
          style={{
            marginLeft: depth * 18,
            borderLeft:
              el.type === "heading"
                ? "3px solid #2563EB"
                : "1px solid #EEF2F7",
          }}
        >
          <div className="rag-block-header">
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span
                className="rag-block-tag"
                style={{
                  background: TYPE_COLOR[el.type] || "#374151",
                  color: "#fff",
                  textTransform: "uppercase",
                  letterSpacing: "0.03em",
                }}
              >
                {el.type}
                {el.type === "heading" && el.level ? ` H${el.level}` : ""}
              </span>
              <span style={{ fontSize: 11, color: "#94A3B8" }}>
                #{el.metadata?.reading_order} · {el.id}
              </span>
            </div>
            <span className="rag-block-meta">
              p.{el.location?.page}
              {el.hierarchy?.parent_section
                ? ` · in “${el.hierarchy.parent_section}”`
                : ""}
            </span>
          </div>
          {renderElementContent(el, imgUrl)}
        </div>
      ))}
    </div>
  );
}

export default DocModal;
