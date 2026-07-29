import React from "react";
import {
  cellsLayout, cellsNcols, matrixToPositional, buildMatrix,
  tblSetText, tblMergeRight, tblMergeDown, tblSplit,
  tblInsertRow, tblDeleteRow, tblMoveRow,
  tblInsertCol, tblDeleteCol, tblMoveCol,
} from "./tableModel";

// Header row for an editable block: tag + move up/down + remove.
function EditBlockHeader({ label, bg, fg, i, count, onMove, onRemove }) {
  return (
    <div className="rag-block-header">
      <span
        className="rag-block-tag"
        style={bg ? { background: bg, color: fg } : undefined}
      >
        {label}
      </span>
      <div style={{ display: "flex", gap: 4 }}>
        <button
          className="rag-btn rag-btn-xs"
          title="Move up"
          disabled={i === 0}
          onClick={() => onMove(i, -1)}
        >
          ▲
        </button>
        <button
          className="rag-btn rag-btn-xs"
          title="Move down"
          disabled={i === count - 1}
          onClick={() => onMove(i, 1)}
        >
          ▼
        </button>
        <button
          className="rag-btn rag-btn-xs rag-btn-red"
          onClick={() => onRemove(i)}
        >
          Remove
        </button>
      </div>
    </div>
  );
}

// ── Reusable merged-cell table editor (colspan + rowspan) ────────────────────
// Powers document tables and CSV/Excel. Fixed columns; any cell can span columns
// (⇥ merge right) or rows (⇩ merge down), and split back (⊟). Row/column tools
// (insert N / move / delete) via the ⋮ menus. Two modes: visual grid or markdown.
function gridToMd(headers, grid) {
  const pos = matrixToPositional(buildMatrix(grid));
  const ncols = Math.max(headers.length, ...pos.map((r) => r.length), 1);
  const h = Array.from({ length: ncols }, (_, i) => headers[i] ?? "");
  const lines = ["| " + h.join(" | ") + " |", "|" + Array(ncols).fill("---").join("|") + "|"];
  for (const r of pos) lines.push("| " + Array.from({ length: ncols }, (_, i) => r[i] ?? "").join(" | ") + " |");
  return lines.join("\n");
}

function TableGridEditor({ headers, grid, onChange }) {
  const layout = cellsLayout(grid); // { nrows, ncols, rows:[[{r,c,t,cs,rs}]] }
  const ncols = Math.max(headers.length, layout.ncols, 1);
  const H = Array.from({ length: ncols }, (_, i) => headers[i] ?? "");

  const [mode, setMode] = React.useState("grid");
  const [mdText, setMdText] = React.useState("");
  const [menu, setMenu] = React.useState(null);
  const [count, setCount] = React.useState(1); // how many rows/cols to insert at once
  const toggleMenu = (type, index) =>
    setMenu((m) => (m && m.type === type && m.index === index ? null : { type, index }));
  const enterMarkdown = () => { setMdText(gridToMd(H, grid)); setMode("markdown"); };
  const onMdChange = (val) => {
    setMdText(val);
    const g = parseMarkdownTable(val);
    onChange(g.length ? g[0] : [], g.length ? g.slice(1).map((row) => row.map((t) => ({ t, cs: 1, rs: 1 }))) : []);
  };

  const setHeader = (ci, val) => { const nh = [...H]; nh[ci] = val; onChange(nh, grid); };
  const setText = (r, c, val) => onChange(H, tblSetText(grid, r, c, val));
  const mergeRight = (r, c) => onChange(H, tblMergeRight(grid, r, c));
  const mergeDown = (r, c) => onChange(H, tblMergeDown(grid, r, c));
  const split = (r, c) => onChange(H, tblSplit(grid, r, c));
  const insRow = (idx, n = 1) => onChange(H, tblInsertRow(grid, idx, n));
  const delRow = (idx) => { onChange(H, tblDeleteRow(grid, idx)); setMenu(null); };
  const mvRow = (idx, dir) => { onChange(H, tblMoveRow(grid, idx, dir)); setMenu({ type: "row", index: idx + dir }); };
  const insCol = (idx, n = 1) => {
    const nh = [...H];
    for (let i = 0; i < n; i++) nh.splice(idx, 0, `Column ${nh.length + 1}`);
    onChange(nh, tblInsertCol(grid, idx, n));
  };
  const delCol = (idx) => { if (ncols <= 1) return; const nh = H.filter((_, i) => i !== idx); onChange(nh, tblDeleteCol(grid, idx)); setMenu(null); };
  const mvCol = (idx, dir) => {
    const j = idx + dir; if (j < 0 || j >= ncols) return;
    const nh = [...H]; [nh[idx], nh[j]] = [nh[j], nh[idx]];
    onChange(nh, tblMoveCol(grid, idx, dir)); setMenu({ type: "col", index: j });
  };

  return (
    <div>
      <div style={{ display: "flex", gap: 6, marginBottom: 6 }}>
        <button type="button" className={`rag-btn rag-btn-xs ${mode === "grid" ? "rag-btn-dark" : ""}`} onClick={() => setMode("grid")}>Grid</button>
        <button type="button" className={`rag-btn rag-btn-xs ${mode === "markdown" ? "rag-btn-dark" : ""}`} onClick={enterMarkdown}>Markdown</button>
      </div>
      {mode === "markdown" ? (
        <>
          <div style={{ fontSize: 11, color: "#94A3B8", margin: "0 0 4px 2px" }}>
            Edit the raw markdown table — one row per line, cells separated by “|”.
            (Markdown can't store merged cells; use <strong>Grid</strong> for those.)
          </div>
          <textarea className="rag-edit-textarea rag-block-content-mono" style={{ minHeight: 180, fontSize: 12 }}
            spellCheck={false} value={mdText} onChange={(e) => onMdChange(e.target.value)}
            placeholder="| Header 1 | Header 2 |&#10;|---|---|&#10;| a | b |" />
        </>
      ) : (
        <>
          <div style={{ fontSize: 11, color: "#94A3B8", margin: "0 0 4px 2px" }}>
            Hover a cell for <b>⇥ merge&nbsp;right</b>, <b>⇩ merge&nbsp;down</b>,
            <b> ⊟ split</b>. Click a row's <b>⋮</b> or a column header's <b>⋮</b> to
            insert / move / delete.
          </div>
          <div className="rag-grid-wrap">
            <table className="rag-grid">
              <thead>
                <tr>
                  <th style={{ width: 24 }} />
                  {H.map((h, ci) => (
                    <th key={ci}>
                      <div className="rag-grid-hcell">
                        <input className="rag-grid-cellinput head" value={h} placeholder={`Col ${ci + 1}`}
                          onChange={(e) => setHeader(ci, e.target.value)} />
                        <button className={`rag-grid-menu-btn ${menu?.type === "col" && menu.index === ci ? "on" : ""}`}
                          title="Column tools" onClick={() => toggleMenu("col", ci)}>⋮</button>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {menu?.type === "col" && menu.index < ncols && (
                  <tr>
                    <td className="rag-grid-gutter" />
                    <td className="rag-grid-toolbar-cell" colSpan={ncols}>
                      <div className="rag-grid-toolbar">
                        <span className="lbl">Column {menu.index + 1}</span>
                        <button className="rag-grid-tbtn" onClick={() => insCol(menu.index, count)}>+◀ insert left</button>
                        <button className="rag-grid-tbtn" onClick={() => insCol(menu.index + 1, count)}>insert right ▶+</button>
                        <button className="rag-grid-tbtn" disabled={menu.index === 0} onClick={() => mvCol(menu.index, -1)}>◀ move</button>
                        <button className="rag-grid-tbtn" disabled={menu.index === ncols - 1} onClick={() => mvCol(menu.index, 1)}>move ▶</button>
                        <button className="rag-grid-tbtn red" disabled={ncols <= 1} onClick={() => delCol(menu.index)}>✕ delete</button>
                      </div>
                    </td>
                  </tr>
                )}
                {layout.rows.map((cellsInRow, r) => (
                  <React.Fragment key={r}>
                    <tr>
                      <td className="rag-grid-gutter">
                        <button className={`rag-grid-menu-btn ${menu?.type === "row" && menu.index === r ? "on" : ""}`}
                          title="Row tools" onClick={() => toggleMenu("row", r)}>⋮</button>
                      </td>
                      {cellsInRow.map((cell) => (
                        <td key={cell.c} colSpan={cell.cs} rowSpan={cell.rs}>
                          <div className="rag-grid-cell">
                            <input className="rag-grid-cellinput" value={cell.t}
                              onChange={(e) => setText(cell.r, cell.c, e.target.value)} />
                            <span className="rag-grid-cellbtns">
                              {cell.c + cell.cs < ncols && (
                                <button className="rag-grid-cbtn" title="Merge with cell on the right" onClick={() => mergeRight(cell.r, cell.c)}>⇥</button>
                              )}
                              {cell.r + cell.rs < layout.nrows && (
                                <button className="rag-grid-cbtn" title="Merge with cell below" onClick={() => mergeDown(cell.r, cell.c)}>⇩</button>
                              )}
                              {(cell.cs > 1 || cell.rs > 1) && (
                                <button className="rag-grid-cbtn" title="Split merged cell" onClick={() => split(cell.r, cell.c)}>⊟</button>
                              )}
                            </span>
                          </div>
                        </td>
                      ))}
                    </tr>
                    {menu?.type === "row" && menu.index === r && (
                      <tr>
                        <td className="rag-grid-gutter" />
                        <td className="rag-grid-toolbar-cell" colSpan={ncols}>
                          <div className="rag-grid-toolbar">
                            <span className="lbl">Row {r + 1}</span>
                            <button className="rag-grid-tbtn" onClick={() => insRow(r, count)}>+▲ above</button>
                            <button className="rag-grid-tbtn" onClick={() => insRow(r + 1, count)}>+▼ below</button>
                            <button className="rag-grid-tbtn" disabled={r === 0} onClick={() => mvRow(r, -1)}>▲ move</button>
                            <button className="rag-grid-tbtn" disabled={r === layout.nrows - 1} onClick={() => mvRow(r, 1)}>move ▼</button>
                            <button className="rag-grid-tbtn red" onClick={() => delRow(r)}>✕ delete</button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
                {layout.nrows === 0 && (
                  <tr><td colSpan={ncols + 1} style={{ padding: 10 }}>
                    <span style={{ fontSize: 12, color: "#9CA3AF" }}>No rows yet — add one below.</span>
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div style={{ display: "flex", gap: 8, padding: "8px 2px", flexWrap: "wrap", alignItems: "center" }}>
            <label style={{ fontSize: 12, color: "#475569", display: "flex", alignItems: "center", gap: 4 }}>
              count:
              <input type="number" min={1} value={count}
                onChange={(e) => setCount(Math.max(1, parseInt(e.target.value) || 1))}
                style={{ width: 46, padding: "3px 5px", border: "1px solid #E2E8F0", borderRadius: 4, fontSize: 12 }} />
            </label>
            <button className="rag-btn rag-btn-xs" onClick={() => insRow(layout.nrows, count)}>+ {count} Row{count > 1 ? "s" : ""}</button>
            <button className="rag-btn rag-btn-xs" onClick={() => insCol(ncols, count)}>+ {count} Column{count > 1 ? "s" : ""}</button>
          </div>
        </>
      )}
    </div>
  );
}

// CSV / Excel editor — title + one grid per table element.
function TabularEditor({ tables, title, setEditTitle, updateTable }) {
  return (
    <>
      <div className="rag-edit-note">
        Edit cells directly; add or remove rows/columns with the buttons. Saving
        keeps the document at <strong>Parsed</strong> — then <strong>Process</strong>{" "}
        to rebuild the chunks from your edits.
      </div>
      <input
        className="rag-edit-input"
        placeholder="Document title"
        value={title}
        onChange={(e) => setEditTitle(e.target.value)}
      />
      {tables.length === 0 && (
        <div style={{ padding: 16, color: "#9CA3AF", fontSize: 13 }}>
          No editable tables in this file.
        </div>
      )}
      {tables.map((t, ti) => (
        <div key={ti} className="rag-block">
          <div className="rag-block-header">
            <span className="rag-block-tag" style={{ background: "#FEF3C7", color: "#92400E" }}>
              {t.name || `Table ${ti + 1}`}
            </span>
            <span className="rag-block-meta">
              {t.grid.length} rows × {Math.max(t.headers.length, ...t.grid.map((r) => r.length), 0)} cols
            </span>
          </div>
          <TableGridEditor
            headers={t.headers}
            grid={t.grid}
            onChange={(headers, grid) => updateTable(ti, { headers, grid })}
          />
        </div>
      ))}
    </>
  );
}

// JSON / XML editor — edit the raw source; re-parsed into a fresh tree on save.
function TreeSourceEditor({ rawSource, sourceType, onChange }) {
  const label = (sourceType || "source").toUpperCase();
  return (
    <>
      <div className="rag-edit-note">
        Edit the raw {label}. On save it is re-parsed into a fresh, valid
        structure — invalid {label} is rejected. Then <strong>Process</strong> to
        rebuild the chunks.
      </div>
      <textarea
        className="rag-edit-textarea rag-block-content-mono"
        style={{ minHeight: 420, fontSize: 12 }}
        spellCheck={false}
        value={rawSource}
        onChange={(e) => onChange(e.target.value)}
        placeholder={`Raw ${label} source`}
      />
    </>
  );
}

const DocModal = ({
  modal,
  modalData,
  modalLoading,
  closeModal,
  showJson,
  setShowJson,
  editMode,
  editDoc,
  setEditTitle = () => {},
  savingEdit,
  startEdit,
  cancelEdit,
  saveEdit,
  editBlock = () => {},
  updateBlock = () => {},
  removeBlock,
  moveBlock = () => {},
  addHeading = () => {},
  addText = () => {},
  addTable = () => {},
  addImage = () => {},
  uploadingImage = false,
  updateTable = () => {},
  setRawSource = () => {},
  spaceId,
}) => {
  const [elementsView, setElementsView] = React.useState(false);
  if (!modal) return null;

  const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
  // Web images are external URLs → use them directly; local file paths go
  // through the server's image endpoint.
  const imgUrl = (path) =>
    /^https?:\/\//i.test(path || "")
      ? path
      : `${API}/rag/spaces/${spaceId}/image?path=${encodeURIComponent(path || "")}`;

  // CSV/Excel (tabular) and JSON/XML (tree) have a single natural view, so the
  // "Elements / Blocks" split is meaningless there — only document formats get
  // the toggle. `parsedKind` drives that decision throughout the header + body.
  const parsedKind = docKind(modalData?.parsed_document || {});
  const isDocKind = parsedKind === "doc";

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
                {isDocKind && (
                  <button
                    className={`rag-btn rag-btn-sm ${elementsView ? "rag-btn-dark" : ""}`}
                    onClick={() => {
                      setElementsView(!elementsView);
                      setShowJson(false);
                    }}
                  >
                    {elementsView ? "Blocks" : "Elements"}
                  </button>
                )}
                <button
                  className={`rag-btn rag-btn-sm ${showJson ? "rag-btn-dark" : ""}`}
                  onClick={() => {
                    setShowJson(!showJson);
                    setElementsView(false);
                  }}
                >
                  {showJson
                    ? isDocKind
                      ? "Blocks"
                      : parsedKind === "tabular"
                        ? "Table"
                        : "Tree"
                    : "JSON"}
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
                  // OCR quality only exists for PDFs (scanned pages) — other
                  // formats show their image count instead
                  (modalData.file_type || "").toUpperCase() === "PDF"
                    ? { l: "OCR", v: modalData.ocr_quality }
                    : { l: "Images", v: modalData.total_images ?? 0 },
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
                editDoc.kind === "tree" ? (
                  <TreeSourceEditor
                    rawSource={editDoc.rawSource || ""}
                    sourceType={editDoc.sourceType}
                    onChange={setRawSource}
                  />
                ) : editDoc.kind === "tabular" ? (
                  <TabularEditor
                    tables={editDoc.tables || []}
                    title={editDoc.title || ""}
                    setEditTitle={setEditTitle}
                    updateTable={updateTable}
                  />
                ) : (
                <>
                  <div className="rag-edit-note">
                    Everything is shown in reading order — edit text, fix
                    headings/pages, reorder with ▲▼, or add / remove blocks.
                    Saving keeps the document at <strong>Parsed</strong> — then
                    <strong> Process</strong> to rebuild the chunks from your edits.
                  </div>
                  <input
                    className="rag-edit-input"
                    placeholder="Document title"
                    value={editDoc.title || ""}
                    onChange={(e) => setEditTitle(e.target.value)}
                  />
                  {(editDoc.blocks || []).map((b, i) => {
                    const count = editDoc.blocks.length;
                    if (b.kind === "table") {
                      return (
                        <div key={i} className="rag-block rag-block-table">
                          <EditBlockHeader label="Table" bg="#FEF3C7" fg="#92400E"
                            i={i} count={count} onMove={moveBlock} onRemove={removeBlock} />
                          <TableGridEditor
                            headers={b.headers || []}
                            grid={b.grid || []}
                            onChange={(headers, grid) => updateBlock(i, { headers, grid })}
                          />
                          <div className="rag-edit-fields">
                            <label className="rag-edit-field">
                              Page
                              <input type="number" min={1} value={b.page || 1}
                                onChange={(e) => editBlock(i, "page", parseInt(e.target.value) || 1)} />
                            </label>
                          </div>
                        </div>
                      );
                    }
                    if (b.kind === "code") {
                      return (
                        <div key={i} className="rag-block">
                          <EditBlockHeader label="Code" bg="#CCFBF1" fg="#0F766E"
                            i={i} count={count} onMove={moveBlock} onRemove={removeBlock} />
                          <textarea
                            className="rag-edit-textarea rag-block-content-mono"
                            rows={6}
                            placeholder="Code"
                            value={b.text || ""}
                            onChange={(e) => editBlock(i, "text", e.target.value)}
                          />
                        </div>
                      );
                    }
                    if (b.kind === "image") {
                      return (
                        <div key={i} className="rag-block">
                          <EditBlockHeader label="Image" bg="#F3E8FF" fg="#7C3AED"
                            i={i} count={count} onMove={moveBlock} onRemove={removeBlock} />
                          <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
                            <img
                              src={b.src || imgUrl(b.image_path)}
                              alt="Block"
                              style={{
                                width: 140, height: 140, objectFit: "contain",
                                borderRadius: 8, background: "#F8FAFC",
                                border: "1px solid #F1F1F1", flexShrink: 0,
                              }}
                              onError={(e) => { e.target.style.opacity = 0.2; }}
                            />
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <textarea
                                className="rag-edit-textarea"
                                rows={3}
                                placeholder="Description (used for retrieval)"
                                value={b.text_for_embedding || ""}
                                onChange={(e) => editBlock(i, "text_for_embedding", e.target.value)}
                              />
                              <input
                                className="rag-edit-input"
                                placeholder="Caption (optional)"
                                value={b.caption || ""}
                                onChange={(e) => editBlock(i, "caption", e.target.value)}
                              />
                              <input
                                className="rag-edit-input"
                                placeholder="OCR text (optional)"
                                value={b.ocr_text || ""}
                                onChange={(e) => editBlock(i, "ocr_text", e.target.value)}
                              />
                              <div className="rag-edit-fields">
                                <label className="rag-edit-field">
                                  Page
                                  <input type="number" min={1} value={b.page || 1}
                                    onChange={(e) => editBlock(i, "page", parseInt(e.target.value) || 1)} />
                                </label>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    }
                    if (b.kind === "heading") {
                      return (
                        <div key={i} className="rag-block">
                          <EditBlockHeader label={`Heading H${b.level || 1}`} bg="#DBEAFE" fg="#1E40AF"
                            i={i} count={count} onMove={moveBlock} onRemove={removeBlock} />
                          <input
                            className="rag-edit-input"
                            style={{ fontWeight: 600 }}
                            placeholder="Heading text"
                            value={b.text || ""}
                            onChange={(e) => editBlock(i, "text", e.target.value)}
                          />
                          <div className="rag-edit-fields">
                            <label className="rag-edit-field">
                              Level
                              <input type="number" min={1} max={6} value={b.level || 1}
                                onChange={(e) => editBlock(i, "level", parseInt(e.target.value) || 1)} />
                            </label>
                            <label className="rag-edit-field">
                              Page
                              <input type="number" min={1} value={b.page || 1}
                                onChange={(e) => editBlock(i, "page", parseInt(e.target.value) || 1)} />
                            </label>
                          </div>
                        </div>
                      );
                    }
                    if (b.kind === "text") {
                      const isList = b.elType === "list_item";
                      return (
                        <div key={i} className="rag-block">
                          <EditBlockHeader label={isList ? "List item" : "Text"}
                            i={i} count={count} onMove={moveBlock} onRemove={removeBlock} />
                          <textarea
                            className="rag-edit-textarea"
                            rows={4}
                            placeholder="Text"
                            value={b.text || ""}
                            onChange={(e) => editBlock(i, "text", e.target.value)}
                          />
                          <div className="rag-edit-fields">
                            <label className="rag-edit-field">
                              Type
                              <select
                                value={b.elType || "paragraph"}
                                onChange={(e) => editBlock(i, "elType", e.target.value)}
                              >
                                <option value="paragraph">Paragraph</option>
                                <option value="list_item">List item</option>
                                <option value="quote">Quote</option>
                              </select>
                            </label>
                            <label className="rag-edit-field">
                              Page
                              <input type="number" min={1} value={b.page || 1}
                                onChange={(e) => editBlock(i, "page", parseInt(e.target.value) || 1)} />
                            </label>
                          </div>
                        </div>
                      );
                    }
                    // legacy "section" block (heading + grouped text)
                    return (
                      <div key={i} className="rag-block">
                        <EditBlockHeader label="Section"
                          i={i} count={count} onMove={moveBlock} onRemove={removeBlock} />
                        <input
                          className="rag-edit-input"
                          placeholder="Heading"
                          value={b.heading || ""}
                          onChange={(e) => editBlock(i, "heading", e.target.value)}
                        />
                        <textarea
                          className="rag-edit-textarea"
                          rows={5}
                          placeholder="Content"
                          value={b.content || ""}
                          onChange={(e) => editBlock(i, "content", e.target.value)}
                        />
                        <div className="rag-edit-fields">
                          <label className="rag-edit-field">
                            Level
                            <input type="number" min={1} max={6} value={b.level || 1}
                              onChange={(e) => editBlock(i, "level", parseInt(e.target.value) || 1)} />
                          </label>
                          <label className="rag-edit-field">
                            Page
                            <input type="number" min={1} value={b.page || 1}
                              onChange={(e) => editBlock(i, "page", parseInt(e.target.value) || 1)} />
                          </label>
                        </div>
                      </div>
                    );
                  })}
                  <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                    <button className="rag-btn rag-btn-sm" onClick={addHeading}>
                      + Add heading
                    </button>
                    <button className="rag-btn rag-btn-sm" onClick={addText}>
                      + Add text
                    </button>
                    <button className="rag-btn rag-btn-sm" onClick={addTable}>
                      + Add table
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
                )
              ) : elementsView && isDocKind ? (
                <ElementsView
                  doc={modalData.parsed_document}
                  imgUrl={imgUrl}
                />
              ) : showJson ? (
                <JsonDump obj={modalData.parsed_document} />
              ) : modalData.parsed_document?.elements?.length ? (
                <BlocksView doc={modalData.parsed_document} imgUrl={imgUrl} />
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
                          src={imgUrl(img.image_path)}
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
              <Capped items={modalData} step={200} label="chunks">{(c) => (
                <div key={c.id} className="rag-block">
                  <div className="rag-block-header">
                    <span className="rag-block-tag">
                      Chunk {c.chunk_index + 1}
                    </span>
                    {c.section_path && (
                      <span className="rag-block-tag" style={{ background: "#eef2ff", color: "#3730a3" }}
                        title="Section (heading breadcrumb)">
                        § {c.section_path}
                      </span>
                    )}
                    <span className="rag-block-meta">
                      p.{c.page}
                      {c.token_count != null ? ` · ${c.token_count} tok` : ` · ${c.content.length}c`}
                      {c.lang ? ` · ${c.lang}` : ""}
                      {c.strategy ? ` · ${c.strategy}` : ""}
                      {c.meta?.quality != null ? ` · Q${c.meta.quality}` : ""}
                    </span>
                  </div>
                  {c.meta?.title && (
                    <div className="rag-block-meta" style={{ padding: "2px 0 6px", color: "#4338ca" }}>
                      🏷 {c.meta.title}
                      {c.meta.keywords?.length ? ` — ${c.meta.keywords.join(", ")}` : ""}
                    </div>
                  )}
                  <pre className="rag-block-content">{c.content}</pre>
                </div>
              )}</Capped>
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

// Decide how a parsed document should render, from its metadata + element types.
// Shared by BOTH the Elements and the Blocks views so every format shows in both:
//   "tabular" → CSV / Excel  → grid / workbook (TableView)
//   "tree"    → JSON / XML    → collapsible tree (TreeView)
//   "doc"     → PDF/DOCX/PPTX/web → reading-ordered blocks / element list
function docKind(doc) {
  const els = doc?.elements || [];
  const meta = doc?.metadata || {};
  const st = (meta.source_type || meta.file_type || "").toLowerCase();
  if (st === "csv" || st === "xlsx" || st === "xls" ||
      els.some((e) => e.type === "workbook" || e.type === "sheet") ||
      // a CSV/Excel table element carries typed `columns`; a PDF/DOCX table
      // uses plain `headers` — so `columns` reliably signals tabular data.
      els.some((e) => e.type === "table" && Array.isArray(e.content?.columns) && e.content.columns.length))
    return "tabular";
  if (st === "json" || st === "xml" ||
      els.some((e) => TREE_TYPES.includes(e.type)))
    return "tree";
  return "doc";
}

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

/* ── Progressive rendering (big documents must not explode the DOM) ──
   A 5 MB JSON can parse into tens of thousands of elements; mounting them all
   at once freezes the tab. These helpers render a batch and load more on
   demand. */
function ShowMoreBar({ shown, total, step, onMore, label = "items" }) {
  if (shown >= total) return null;
  return (
    <button
      className="rag-btn rag-btn-sm"
      style={{ display: "block", margin: "10px auto" }}
      onClick={onMore}
    >
      ▼ Show {Math.min(step, total - shown).toLocaleString()} more {label} (
      {(total - shown).toLocaleString()} remaining)
    </button>
  );
}

function Capped({ items = [], step = 150, label = "items", children }) {
  const [n, setN] = React.useState(step);
  const shown = Math.min(n, items.length);
  return (
    <>
      {items.slice(0, shown).map(children)}
      <ShowMoreBar shown={shown} total={items.length} step={step}
        onMore={() => setN(n + step)} label={label} />
    </>
  );
}

function CappedText({ text, first = 30000, step = 150000, className, pre = false }) {
  const t = text || "";
  const [n, setN] = React.useState(first);
  const Tag = pre ? "pre" : "div";
  return (
    <>
      <Tag className={className}>{t.slice(0, n) || "Empty"}</Tag>
      {n < t.length && (
        <button
          className="rag-btn rag-btn-sm"
          style={{ display: "block", margin: "10px auto" }}
          onClick={() => setN(n + step)}
        >
          ▼ Show more text ({(t.length - n).toLocaleString()} characters remaining)
        </button>
      )}
    </>
  );
}

function JsonDump({ obj }) {
  const text = React.useMemo(() => {
    try { return JSON.stringify(obj, null, 2) || ""; }
    catch { return "(unserializable)"; }
  }, [obj]);
  return (
    <div className="rag-json">
      <CappedText text={text} first={60000} step={200000} pre />
    </div>
  );
}

const _TREE_KIDS_STEP = 200;

function TreeNode({ node, byId, depth, mode }) {
  const initOpen =
    mode === "expand" ? true : mode === "collapse" ? depth < 1 : depth < 2;
  const [open, setOpen] = React.useState(initOpen);
  const [hover, setHover] = React.useState(false);
  const [kidsShown, setKidsShown] = React.useState(_TREE_KIDS_STEP);
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
      {open && has && (
        <>
          {childIds.slice(0, kidsShown).map(
            (cid) =>
              byId[cid] && (
                <TreeNode key={cid} node={byId[cid]} byId={byId} depth={depth + 1} mode={mode} />
              ),
          )}
          <ShowMoreBar shown={Math.min(kidsShown, childIds.length)}
            total={childIds.length} step={_TREE_KIDS_STEP}
            onMore={() => setKidsShown(kidsShown + _TREE_KIDS_STEP)}
            label="child nodes" />
        </>
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
        <Capped items={roots} step={200} label="root nodes">
          {(r) => <TreeNode key={r.id} node={r} byId={byId} depth={0} mode={mode} />}
        </Capped>
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
          {tables.map((t) => {
            const name = t.content?.table_name;
            const showName = name && !name.includes("!");   // real title, not "Sheet!B4:E9"
            return (
              <div key={t.id} style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 12, marginBottom: 3, display: "flex", gap: 8, alignItems: "baseline" }}>
                  {showName && (
                    <span style={{ fontWeight: 700, color: "#0F766E" }}>{name}</span>
                  )}
                  <span style={{ fontSize: 11, color: "#94A3B8" }}>{t.location?.range}</span>
                </div>
                <TableGrid table={t} />
              </div>
            );
          })}
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

// Parse a markdown table into a grid of string cells. Tolerates leading/trailing
// pipes and skips separator rows (|---|:--:|). Returns [] if nothing table-like.
function parseMarkdownTable(md) {
  const out = [];
  for (const raw of (md || "").split("\n")) {
    const line = raw.trim();
    if (!line || line.indexOf("|") === -1) continue;
    const noPipes = line.replace(/\|/g, "").trim();
    if (noPipes && /^[:\-\s]+$/.test(noPipes)) continue; // separator row
    let cells = line.split("|");
    if (cells.length && cells[0].trim() === "") cells = cells.slice(1);
    if (cells.length && cells[cells.length - 1].trim() === "")
      cells = cells.slice(0, -1);
    out.push(cells.map((c) => c.trim()));
  }
  return out;
}

// Read a cell positionally, tolerating rows shaped as arrays, index-keyed dicts
// ("0".."n"), or (legacy) header-keyed dicts.
function cellAt(row, ci, headers) {
  if (Array.isArray(row)) return row[ci] ?? "";
  if (row && typeof row === "object") {
    if (Object.prototype.hasOwnProperty.call(row, String(ci)))
      return row[String(ci)] ?? "";
    const h = headers[ci];
    if (h != null && Object.prototype.hasOwnProperty.call(row, h))
      return row[h] ?? "";
    return Object.values(row)[ci] ?? "";
  }
  return "";
}

const _tblTh = { border: "1px solid #E5E7EB", padding: "4px 8px", background: "#F9FAFB", textAlign: "left" };
const _tblTd = { border: "1px solid #E5E7EB", padding: "4px 8px" };

function TableBlock({ content }) {
  // Rich cell model with colspan + rowspan (from the editor) → real merged cells.
  if (Array.isArray(content.cells) && content.cells.length) {
    const span = (c) => Math.max(1, c.cs || c.s || 1);
    const ncols = Math.max(
      (content.headers || []).length,
      ...content.cells.map((r) => r.reduce((a, c) => a + span(c), 0)),
      1,
    );
    const head = content.headers || [];
    const hasHead = head.some((h) => (h ?? "").toString().trim() !== "");
    return (
      <div style={{ overflowX: "auto" }}>
        {content.caption && <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>{content.caption}</div>}
        <table style={{ borderCollapse: "collapse", fontSize: 12, width: "100%" }}>
          {hasHead && (
            <thead>
              <tr>
                {Array.from({ length: ncols }).map((_, i) => (
                  <th key={i} style={_tblTh}>{head[i] ?? ""}</th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {content.cells.map((row, ri) => (
              <tr key={ri}>
                {row.map((cell, ci) => (
                  <td key={ci} colSpan={span(cell)} rowSpan={Math.max(1, cell.rs || 1)} style={_tblTd}>{cell.t ?? ""}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  // Otherwise prefer the markdown grid — always complete/consistent; fall back
  // to positional rows, then raw text.
  const grid = parseMarkdownTable(content.markdown || "");
  let head = [];
  let body = [];
  if (grid.length) {
    head = grid[0];
    body = grid.slice(1);
  } else {
    head = content.headers || [];
    body = (content.rows || []).map((r) => head.map((_, ci) => cellAt(r, ci, head)));
  }
  if (!head.length && !body.length) {
    return (
      <pre className="rag-block-content rag-block-content-mono">
        {content.markdown || ""}
      </pre>
    );
  }
  const cols = Math.max(head.length, ...body.map((r) => r.length), 0);
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
            {Array.from({ length: cols }).map((_, i) => (
              <th key={i} style={_tblTh}>{head[i] ?? ""}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((r, ri) => (
            <tr key={ri}>
              {Array.from({ length: cols }).map((_, ci) => (
                <td key={ci} style={_tblTd}>{r[ci] ?? ""}</td>
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

// Blocks view entry point. Tabular (CSV/Excel) and structured (JSON/XML) docs
// have no "reading order" of prose blocks, so they render with the SAME
// specialized views as the Elements tab; document-style content uses the
// reading-ordered block layout below.
function BlocksView({ doc, imgUrl }) {
  const kind = docKind(doc);
  if (kind === "tabular") return <TableView doc={doc} />;
  if (kind === "tree") return <TreeView doc={doc} />;
  return <OrderedBlocks doc={doc} imgUrl={imgUrl} />;
}

// Blocks view rendered from elements[] in READING ORDER, so images / tables /
// code appear in their correct place (not dumped at the end). Consecutive text
// is grouped under its heading into a section card.
function OrderedBlocks({ doc, imgUrl }) {
  const els = [...(doc?.elements || [])].sort(
    (a, b) => (a.metadata?.reading_order || 0) - (b.metadata?.reading_order || 0),
  );
  const blocks = [];
  let cur = null;
  const flush = () => {
    if (cur && (cur.heading || cur.lines.length)) {
      blocks.push({ kind: "section", ...cur, content: cur.lines.join("\n") });
    }
    cur = null;
  };
  for (const el of els) {
    const t = el.type;
    const c = el.content || {};
    const page = el.location?.page;
    if (t === "heading") {
      flush();
      cur = { heading: c.text || "", level: el.level || 1, page, lines: [] };
    } else if (t === "paragraph" || t === "list_item" || t === "quote") {
      if (!cur) cur = { heading: "", level: 1, page, lines: [] };
      cur.lines.push((t === "list_item" ? "• " : "") + (c.text || ""));
    } else if (t === "table") {
      flush();
      blocks.push({ kind: "table", el, page });
    } else if (t === "image") {
      flush();
      blocks.push({ kind: "image", el, page });
    } else if (t === "code") {
      flush();
      blocks.push({ kind: "code", el, page });
    }
  }
  flush();

  return <Capped items={blocks} step={150} label="blocks">{(b, i) => {
    if (b.kind === "table") {
      return (
        <div key={i} className="rag-block rag-block-table">
          <div className="rag-block-header">
            <span className="rag-block-tag" style={{ background: "#FEF3C7", color: "#92400E" }}>
              Table
            </span>
            <span className="rag-block-meta">p.{b.page}</span>
          </div>
          <TableBlock content={b.el.content || {}} />
        </div>
      );
    }
    if (b.kind === "code") {
      return (
        <div key={i} className="rag-block">
          <div className="rag-block-header">
            <span className="rag-block-tag" style={{ background: "#CCFBF1", color: "#0F766E" }}>
              Code
            </span>
            <span className="rag-block-meta">p.{b.page}</span>
          </div>
          {renderElementContent(b.el, imgUrl)}
        </div>
      );
    }
    if (b.kind === "image") {
      const c = b.el.content || {};
      return (
        <div key={i} className="rag-block">
          <div className="rag-block-header">
            <span className="rag-block-tag" style={{ background: "#F3E8FF", color: "#7C3AED" }}>
              Image
            </span>
            <span className="rag-block-meta">p.{b.page}</span>
          </div>
          <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
            <img
              src={c.src || imgUrl(c.image_path)}
              alt={c.caption || "image"}
              style={{
                width: 160, height: 160, objectFit: "contain", borderRadius: 8,
                background: "#F8FAFC", border: "1px solid #F1F1F1", flexShrink: 0,
              }}
              onError={(e) => { e.target.style.opacity = 0.2; }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              {c.text_for_embedding ? (
                <div style={{ fontSize: 13, lineHeight: 1.6 }}>{c.text_for_embedding}</div>
              ) : c.caption ? (
                <div style={{ fontSize: 13 }}>{c.caption}</div>
              ) : (
                <div style={{ fontSize: 13, color: "#9CA3AF" }}>No description</div>
              )}
              {c.ocr_text && (
                <div style={{ fontSize: 12, color: "#525252", marginTop: 6 }}>OCR: {c.ocr_text}</div>
              )}
            </div>
          </div>
        </div>
      );
    }
    // section (grouped text under a heading)
    return (
      <div key={i} className="rag-block">
        <div className="rag-block-header">
          <div className="rag-heading-tag">
            <span className="rag-block-tag">Section</span>
            {b.heading && (
              <span style={{ fontSize: 13, fontWeight: 600 }}>{b.heading}</span>
            )}
            {b.level ? <span className="rag-h-level">H{b.level}</span> : null}
          </div>
          <span className="rag-block-meta">
            p.{b.page} · {b.content.length}c
          </span>
        </div>
        <pre className="rag-block-content">{b.content}</pre>
      </div>
    );
  }}</Capped>;
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
        <CappedText text={data.raw_text} className="rag-raw-text" />
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
      <CappedText text={data.raw_text} className="rag-wl-body" />
    </>
  );
}

function ElementsView({ doc, imgUrl }) {
  const els = doc?.elements || [];
  const info = doc?.document || {};
  const meta = doc?.metadata || {};

  // Tabular data (CSV / Excel) → table grid / workbook view.
  if (docKind(doc) === "tabular") {
    return <TableView doc={doc} />;
  }

  // Structured data (JSON / XML) → collapsible tree instead of the flat list.
  if (docKind(doc) === "tree") {
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
