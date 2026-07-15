import React from "react";

const SL = {
  UPLOADING: "Uploaded",
  LOADED: "Loaded",
  EXTRACTED: "Parsed",
  PROCESSING: "Processing",
  INDEXED: "Indexed",
  ERROR: "Error",
};
const SB = {
  UPLOADING: "rag-badge-loaded",
  LOADED: "rag-badge-loaded",
  EXTRACTED: "rag-badge-parsed",
  INDEXED: "rag-badge-indexed",
  ERROR: "rag-badge-error",
};

const UploadsPanel = ({
  docs,
  fileRef,
  uploading,
  scraping,
  parsing,
  handleUpload,
  handleDriveUpload,
  handleWebIngest = () => {},
  handleLoadParse,
  handleLoadParseAll,
  handleParse,
  handleParseAll,
  handleDeleteDoc,
  openModal,
  counts,
  handleSetExtractImages = () => {},
  spaceId,
  isOwner = true,
  editable = true,
}) => {
  const { uploadingCount, loadedCount, extractedCount } = counts;

  // ── Web source selector ──
  const [webMode, setWebMode] = React.useState("url");
  const [webUrl, setWebUrl] = React.useState("");
  const [rawHtml, setRawHtml] = React.useState("");
  const [maxDepth, setMaxDepth] = React.useState(2);
  const [maxPages, setMaxPages] = React.useState(50);
  const [webOpen, setWebOpen] = React.useState(false);

  const WEB_MODES = [
    ["url", "🔗", "Single URL"],
    ["crawl", "🕸️", "Website"],
    ["sitemap", "🗺️", "Sitemap"],
    ["rss", "📰", "RSS Feed"],
    ["html", "≺≻", "Raw HTML"],
  ];
  const WEB_ICON = { url: "🔗", crawl: "🕸️", sitemap: "🗺️", rss: "📰" };
  const WEB_DESC = {
    url: "Scrape one page with JavaScript rendering (Crawl4AI).",
    crawl: "Follow same-domain links and import every page found.",
    sitemap: "Import every URL listed in a sitemap.xml.",
    rss: "Import each article from an RSS / Atom feed.",
    html: "Paste raw HTML to parse it directly — no fetch.",
  };
  const WEB_PLACEHOLDER = {
    url: "https://example.com/page",
    crawl: "https://docs.example.com",
    sitemap: "https://example.com/sitemap.xml",
    rss: "https://blog.example.com/rss.xml",
  };
  const WEB_SUBMIT = {
    url: "Scrape page", crawl: "Crawl website", sitemap: "Import sitemap",
    rss: "Import feed", html: "Add HTML",
  };

  const submitWeb = async () => {
    const payloads = {
      url: { url: webUrl },
      html: { html: rawHtml },
      crawl: { url: webUrl, max_depth: maxDepth, max_pages: maxPages },
      sitemap: { url: webUrl, max_pages: maxPages },
      rss: { url: webUrl, max_items: maxPages },
    };
    await handleWebIngest(webMode, payloads[webMode]);
    setWebUrl("");
    setRawHtml("");
  };
  const webDisabled =
    scraping || (webMode === "html" ? !rawHtml.trim() : !webUrl.trim());

  const canImages = (d) =>
    ["pdf", "docx", "pptx"].includes((d.file_type || "").toLowerCase());
  const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
  const viewFile = (d) =>
    window.open(
      `${API}/rag/spaces/${spaceId}/documents/${d.id}/file`,
      "_blank",
      "noopener",
    );

  return (
    <>
      {!isOwner && (
        <div className="rag-cfg-hint" style={{ marginBottom: 12 }}>
          Only the space <strong>owner</strong> can add or delete documents. You
          can tune the configuration and test the space.
        </div>
      )}
      {isOwner && !editable && (
        <div
          className="rag-cfg-hint"
          style={{
            marginBottom: 12,
            padding: "8px 11px",
            borderRadius: 8,
            background: "rgba(22,163,74,.08)",
            border: "1px solid rgba(22,163,74,.3)",
            color: "#166534",
          }}
        >
          🔒 This space is <strong>deployed &amp; live</strong> — documents are
          locked. Click <strong>Stop to edit</strong> in the header to add or
          remove documents.
        </div>
      )}
      {isOwner && editable && (
      <div className="rag-upload-zone">
        <div className="rag-upload-zone-head">
          <div className="rag-upload-zone-title">Add documents</div>
          <div className="rag-upload-zone-sub">
            Upload a file, import from Google Drive, or add content from the web
          </div>
        </div>
        <input
          type="file"
          ref={fileRef}
          onChange={handleUpload}
          style={{ display: "none" }}
          accept=".pdf,.docx,.txt,.md,.csv,.xlsx,.xls,.html,.htm,.json,.xml,.pptx"
          multiple
        />
        <div className="rag-src-tiles">
          <button
            className="rag-src-tile"
            onClick={() => fileRef.current.click()}
            disabled={uploading}
          >
            <span className="rag-src-icon rag-src-icon-file">📁</span>
            <span className="rag-src-text">
              <span className="rag-src-title">
                {uploading ? "Uploading…" : "Upload a file"}
              </span>
              <span className="rag-src-sub">PDF, DOCX, CSV, XLSX…</span>
            </span>
          </button>
          <button
            className="rag-src-tile"
            onClick={handleDriveUpload}
            disabled={uploading}
          >
            <span className="rag-src-icon rag-src-icon-drive">☁️</span>
            <span className="rag-src-text">
              <span className="rag-src-title">Google Drive</span>
              <span className="rag-src-sub">Import from the cloud</span>
            </span>
          </button>
          <button
            className={`rag-src-tile ${webOpen ? "active" : ""}`}
            onClick={() => setWebOpen((v) => !v)}
          >
            <span className="rag-src-icon rag-src-icon-web">🌐</span>
            <span className="rag-src-text">
              <span className="rag-src-title">Web</span>
              <span className="rag-src-sub">URL, site, sitemap, RSS</span>
            </span>
          </button>
        </div>
        {webOpen && (
        <div className="rag-web">
          <div className="rag-web-tabs">
            {WEB_MODES.map(([m, icon, label]) => (
              <button
                key={m}
                className={`rag-web-tab ${webMode === m ? "active" : ""}`}
                onClick={() => setWebMode(m)}
              >
                <span className="rag-web-tab-icon">{icon}</span>
                {label}
              </button>
            ))}
          </div>

          <div className="rag-web-desc">{WEB_DESC[webMode]}</div>

          {webMode === "html" ? (
            <textarea
              className="rag-web-textarea"
              placeholder="Paste raw HTML here…"
              value={rawHtml}
              onChange={(e) => setRawHtml(e.target.value)}
            />
          ) : (
            <div className="rag-web-field">
              <span className="rag-upload-url-icon">{WEB_ICON[webMode]}</span>
              <input
                placeholder={WEB_PLACEHOLDER[webMode]}
                value={webUrl}
                onChange={(e) => setWebUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !webDisabled && submitWeb()}
              />
            </div>
          )}

          {(webMode === "crawl" || webMode === "sitemap" || webMode === "rss") && (
            <div className="rag-web-opts">
              {webMode === "crawl" && (
                <label className="rag-web-opt">
                  Depth
                  <input
                    className="rag-web-num"
                    type="number"
                    min={1}
                    max={5}
                    value={maxDepth}
                    onChange={(e) => setMaxDepth(+e.target.value)}
                  />
                </label>
              )}
              <label className="rag-web-opt">
                {webMode === "rss" ? "Max items" : "Max pages"}
                <input
                  className="rag-web-num"
                  type="number"
                  min={1}
                  max={500}
                  value={maxPages}
                  onChange={(e) => setMaxPages(+e.target.value)}
                />
              </label>
            </div>
          )}

          <div className="rag-web-actions">
            <button
              className="rag-upload-scrape-btn"
              onClick={submitWeb}
              disabled={webDisabled}
              style={{ padding: "9px 20px" }}
            >
              {scraping ? "Working…" : WEB_SUBMIT[webMode]}
            </button>
            {(webMode === "crawl" || webMode === "sitemap" || webMode === "rss") && (
              <span className="rag-web-hint">
                Each page becomes a separate document.
              </span>
            )}
          </div>
        </div>
        )}
      </div>
      )}

      {editable && (uploadingCount > 0 || loadedCount > 0) && (
        <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
          {uploadingCount > 0 && (
            <button
              className="rag-btn rag-btn-blue rag-btn-sm"
              onClick={handleLoadParseAll}
              disabled={parsing}
            >
              {parsing ? "…" : `Load + Parse All (${uploadingCount})`}
            </button>
          )}
          {loadedCount > 0 && (
            <button
              className="rag-btn rag-btn-sm"
              onClick={handleParseAll}
              disabled={parsing}
            >
              {parsing ? "…" : `Parse All (${loadedCount})`}
            </button>
          )}
        </div>
      )}

      {extractedCount > 0 && (
        <div className="rag-cfg-hint" style={{ marginBottom: 12 }}>
          {extractedCount} document(s) parsed and ready. Choose a chunking
          strategy and index them in the <strong>Chunking</strong> section.
        </div>
      )}

      <div className="rag-docs-list">
        {docs.length === 0 && (
          <div className="rag-empty-state">
            No documents yet — upload a file, import from Drive, or scrape a URL
          </div>
        )}
        {docs.map((d) => (
          <div key={d.id} className="rag-doc-card">
            <div className="rag-doc-icon">
              {d.source_type === "url"
                ? "URL"
                : d.source_type === "google_drive"
                  ? "GD"
                  : (d.file_type || "?").toUpperCase()}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="rag-doc-name">{d.file_name}</div>
              <div className="rag-doc-meta">
                {d.file_size ? `${(d.file_size / 1024).toFixed(1)} KB` : ""}
                {d.num_chunks > 0 && ` · ${d.num_chunks} chunks`}
                {d.source_type === "google_drive" && " · Google Drive"}
              </div>

              {/* Chunking strategy & indexing now live in the Chunking section. */}

              {/* Per-document image extraction (PDF/DOCX/PPTX, before indexing) */}
              {editable && canImages(d) && d.status !== "INDEXED" && (
                <label className="rag-doc-imgtoggle">
                  <input
                    type="checkbox"
                    checked={d.extract_images !== false}
                    onChange={(e) =>
                      handleSetExtractImages(d.id, e.target.checked)
                    }
                  />
                  Extract images
                  <span className="rag-doc-imgtoggle-hint">
                    {d.has_extracted_content
                      ? "· re-run Load + Parse to apply"
                      : "· applied on Load + Parse"}
                  </span>
                </label>
              )}

              <div className="rag-doc-btns">
                {d.source_type !== "url" && (
                  <button
                    className="rag-btn rag-btn-xs"
                    onClick={() => viewFile(d)}
                    title="Open the original file"
                  >
                    View document
                  </button>
                )}
                {editable && d.status === "UPLOADING" && (
                  <button
                    className="rag-btn rag-btn-xs rag-btn-blue"
                    onClick={() => handleLoadParse(d.id)}
                    disabled={parsing}
                  >
                    Load + Parse
                  </button>
                )}
                {d.has_loaded_content && (
                  <button
                    className="rag-btn rag-btn-xs"
                    onClick={() => openModal("loaded", d)}
                  >
                    View loaded
                  </button>
                )}
                {editable && d.status === "LOADED" && (
                  <button
                    className="rag-btn rag-btn-xs rag-btn-blue"
                    onClick={() => handleParse(d.id)}
                    disabled={parsing}
                  >
                    Parse
                  </button>
                )}
                {d.has_extracted_content && (
                  <button
                    className="rag-btn rag-btn-xs"
                    onClick={() => openModal("parsed", d)}
                  >
                    View parsed
                  </button>
                )}
              </div>
            </div>
            <span className={`rag-badge ${SB[d.status] || ""}`}>
              {SL[d.status] || d.status}
            </span>
            {editable && (
              <button
                className="rag-doc-del"
                onClick={() => handleDeleteDoc(d.id)}
              >
                ×
              </button>
            )}
          </div>
        ))}
      </div>
    </>
  );
};

export default UploadsPanel;
