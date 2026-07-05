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
  processing,
  urlInput,
  setUrlInput,
  handleUpload,
  handleDriveUpload,
  handleScrape,
  handleLoadParse,
  handleLoadParseAll,
  handleParse,
  handleParseAll,
  handleProcess,
  handleProcessAll,
  handleDeleteDoc,
  openModal,
  counts,
  chunkMode,
  handleSetDocStrategy,
}) => {
  const { uploadingCount, loadedCount, extractedCount } = counts;

  return (
    <>
      <div className="rag-upload-zone">
        <div className="rag-upload-zone-head">
          <div className="rag-upload-zone-title">Add documents</div>
          <div className="rag-upload-zone-sub">
            Upload from your computer, Google Drive, or paste a URL to scrape
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
        <div className="rag-upload-tiles">
          <button
            className="rag-upload-tile"
            onClick={() => fileRef.current.click()}
            disabled={uploading}
          >
            <span className="rag-upload-tile-icon">📁</span>
            <span className="rag-upload-tile-title">
              {uploading ? "Uploading…" : "Upload a file"}
            </span>
            <span className="rag-upload-tile-sub">
              PDF, DOCX, CSV, XLSX, TXT…
            </span>
          </button>
          <button
            className="rag-upload-tile"
            onClick={handleDriveUpload}
            disabled={uploading}
          >
            <span className="rag-upload-tile-icon">☁️</span>
            <span className="rag-upload-tile-title">Google Drive</span>
            <span className="rag-upload-tile-sub">Import from the cloud</span>
          </button>
        </div>
        <div className="rag-upload-or">
          <span className="rag-upload-or-line" />
          <span className="rag-upload-or-text">or</span>
          <span className="rag-upload-or-line" />
        </div>
        <div className="rag-upload-url-row">
          <div className="rag-upload-url-input">
            <span className="rag-upload-url-icon">🔗</span>
            <input
              placeholder="Paste a URL to scrape…"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleScrape()}
            />
          </div>
          <button
            className="rag-upload-scrape-btn"
            onClick={handleScrape}
            disabled={scraping}
          >
            {scraping ? "…" : "Scrape"}
          </button>
        </div>
      </div>

      {(uploadingCount > 0 || loadedCount > 0) && (
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

              <div className="rag-doc-btns">
                {d.status === "UPLOADING" && (
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
                {d.status === "LOADED" && (
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
            <button
              className="rag-doc-del"
              onClick={() => handleDeleteDoc(d.id)}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </>
  );
};

export default UploadsPanel;
