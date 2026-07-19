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

// Group the uploads list by document FORMAT so PDFs, Word, PowerPoint, etc. show
// under their own category header (ordered; empty categories are omitted).
const _ft = (d) => (d.file_type || "").toLowerCase();
const DOC_CATS = [
  { key: "pdf", label: "PDF", match: (d) => _ft(d) === "pdf" },
  { key: "word", label: "Word", match: (d) => ["docx", "doc"].includes(_ft(d)) },
  { key: "ppt", label: "PowerPoint", match: (d) => ["pptx", "ppt"].includes(_ft(d)) },
  { key: "text", label: "Text", match: (d) => ["txt", "md", "markdown"].includes(_ft(d)) },
  { key: "sheet", label: "Spreadsheets", match: (d) => ["csv", "xlsx", "xls"].includes(_ft(d)) },
  { key: "data", label: "Data (JSON / XML)", match: (d) => ["json", "xml"].includes(_ft(d)) },
  {
    key: "web",
    label: "Web pages",
    match: (d) =>
      d.source_type === "url" ||
      d.source_type === "raw_html" ||
      ["html", "htm", "url", "web"].includes(_ft(d)),
  },
];

function groupDocsByFormat(list) {
  const buckets = new Map();
  for (const d of list || []) {
    const cat = DOC_CATS.find((c) => c.match(d)) || { key: "other", label: "Other" };
    if (!buckets.has(cat.key))
      buckets.set(cat.key, { key: cat.key, label: cat.label, items: [] });
    buckets.get(cat.key).items.push(d);
  }
  const order = [...DOC_CATS.map((c) => c.key), "other"];
  return [...buckets.values()].sort(
    (a, b) => order.indexOf(a.key) - order.indexOf(b.key),
  );
}

// ── Search / filter helpers (normalized, multi-term, ranked) ──
// normalize: strip diacritics + case so "Résumé" matches "resume".
function _norm(s) {
  return (s || "")
    .toString()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}
const _catOf = (d) => DOC_CATS.find((c) => c.match(d)) || { key: "other", label: "Other" };
// everything a query can match against: name, url, extension, format label, source
function _haystack(d) {
  const cat = _catOf(d);
  return _norm([d.file_name, d.source_url, d.file_type, cat.label, d.source_type].filter(Boolean).join(" "));
}
// relevance score for a doc against query terms (lower = better → sorts first)
function _score(d, terms) {
  const name = _norm(d.file_name);
  let s = 0;
  for (const t of terms) {
    if (name.startsWith(t)) s += 3;      // name prefix — strongest
    else if (name.includes(t)) s += 2;   // name substring
    else s += 1;                         // matched elsewhere (url / format)
  }
  return -s;
}
// filter by active format categories + AND-match of every query term, then group
// by format and rank each group by relevance.
function searchDocs(docs, terms, cats) {
  let list = docs || [];
  if (cats && cats.size) list = list.filter((d) => cats.has(_catOf(d).key));
  if (terms.length) {
    list = list.filter((d) => {
      const hay = _haystack(d);
      return terms.every((t) => hay.includes(t));
    });
  }
  const grouped = groupDocsByFormat(list);
  if (terms.length) {
    for (const g of grouped)
      g.items.sort((a, b) => _score(a, terms) - _score(b, terms) || _norm(a.file_name).localeCompare(_norm(b.file_name)));
  }
  return grouped;
}
// split a matched name into {t, hit} segments so hits can be highlighted
function _highlight(text, terms) {
  const esc = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).filter(Boolean);
  if (!esc.length) return [{ t: text, hit: false }];
  const re = new RegExp(`(${esc.join("|")})`, "gi");
  const out = [];
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push({ t: text.slice(last, m.index), hit: false });
    out.push({ t: m[0], hit: true });
    last = m.index + m[0].length;
    if (m.index === re.lastIndex) re.lastIndex++;
  }
  if (last < text.length) out.push({ t: text.slice(last), hit: false });
  return out;
}

const UploadsPanel = ({
  docs,
  fileRef,
  folderRef,
  uploading,
  scraping,
  parsing,
  handleUpload,
  handleFolderUpload = () => {},
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
  const [webExtractImages, setWebExtractImages] = React.useState(true);
  const [uploadMenu, setUploadMenu] = React.useState(false);
  const uploadWrapRef = React.useRef(null);

  // ── Search + format filter ──
  const [search, setSearch] = React.useState("");   // raw input
  const [query, setQuery] = React.useState("");      // debounced
  const [cats, setCats] = React.useState(() => new Set());
  const searchRef = React.useRef(null);
  React.useEffect(() => {
    const id = setTimeout(() => setQuery(search), 150);   // debounce
    return () => clearTimeout(id);
  }, [search]);
  const terms = React.useMemo(() => _norm(query).split(/\s+/).filter(Boolean), [query]);
  // format chips available in the current doc set, with counts
  const availableCats = React.useMemo(() => {
    const m = new Map();
    for (const d of docs || []) {
      const c = _catOf(d);
      const prev = m.get(c.key);
      m.set(c.key, { key: c.key, label: c.label, count: (prev?.count || 0) + 1 });
    }
    const order = [...DOC_CATS.map((c) => c.key), "other"];
    return [...m.values()].sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key));
  }, [docs]);
  const toggleCat = (k) =>
    setCats((prev) => { const n = new Set(prev); n.has(k) ? n.delete(k) : n.add(k); return n; });
  const grouped = React.useMemo(() => searchDocs(docs, terms, cats), [docs, terms, cats]);
  const shownCount = grouped.reduce((a, g) => a + g.items.length, 0);
  const totalCount = (docs || []).length;
  const filtering = terms.length > 0 || cats.size > 0;
  const clearFilters = () => { setSearch(""); setQuery(""); setCats(new Set()); };
  // close the file/folder menu when clicking outside it
  React.useEffect(() => {
    if (!uploadMenu) return;
    const onDoc = (e) => {
      if (uploadWrapRef.current && !uploadWrapRef.current.contains(e.target))
        setUploadMenu(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [uploadMenu]);

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
    const ei = webExtractImages;   // extract images before scraping (same as PDF)
    const payloads = {
      url: { url: webUrl, extract_images: ei },
      html: { html: rawHtml, extract_images: ei },
      crawl: { url: webUrl, max_depth: maxDepth, max_pages: maxPages, extract_images: ei },
      sitemap: { url: webUrl, max_pages: maxPages, extract_images: ei },
      rss: { url: webUrl, max_items: maxPages, extract_images: ei },
    };
    await handleWebIngest(webMode, payloads[webMode]);
    setWebUrl("");
    setRawHtml("");
  };
  const webDisabled =
    scraping || (webMode === "html" ? !rawHtml.trim() : !webUrl.trim());

  // Uploaded files (PDF/DOCX/PPTX) decide "extract images" on the card — they
  // have no pre-ingest form. Web/URL docs decide it in the scrape form instead,
  // so the card toggle is intentionally NOT shown for them.
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
        {/* Folder picker: webkitdirectory makes the dialog select a folder and
            return every file inside it. Set imperatively so it's reliable. */}
        <input
          type="file"
          ref={(el) => {
            if (el) {
              el.setAttribute("webkitdirectory", "");
              el.setAttribute("directory", "");
              el.setAttribute("mozdirectory", "");
              if (folderRef) folderRef.current = el;
            }
          }}
          onChange={handleFolderUpload}
          style={{ display: "none" }}
          multiple
        />
        <div className="rag-src-tiles">
          <div className="rag-src-tile-wrap" ref={uploadWrapRef}>
            <button
              className="rag-src-tile"
              onClick={() => setUploadMenu((v) => !v)}
              disabled={uploading}
            >
              <span className="rag-src-icon rag-src-icon-file">📁</span>
              <span className="rag-src-text">
                <span className="rag-src-title">
                  {uploading ? "Uploading…" : "Upload"}
                </span>
                <span className="rag-src-sub">File or folder ▾</span>
              </span>
            </button>
            {uploadMenu && (
              <div className="rag-upload-menu">
                <button
                  className="rag-upload-menu-item"
                  onClick={() => { setUploadMenu(false); fileRef.current?.click(); }}
                >
                  📄 Choose files
                </button>
                <button
                  className="rag-upload-menu-item"
                  onClick={() => { setUploadMenu(false); folderRef?.current?.click(); }}
                >
                  📁 Choose a folder
                </button>
              </div>
            )}
          </div>
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

          {/* Extract images option — decided BEFORE scraping (same vision model
              as PDF/DOCX/PPTX). Describes meaningful page images so they're
              searchable; skip it for text-only, faster/cheaper scraping. */}
          <label className="rag-doc-imgtoggle" style={{ marginTop: 4 }}>
            <input
              type="checkbox"
              checked={webExtractImages}
              onChange={(e) => setWebExtractImages(e.target.checked)}
            />
            Extract images
            <span className="rag-doc-imgtoggle-hint">
              · describe page images with the vision model (slower)
            </span>
          </label>

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

      {totalCount > 0 && (
        <div className="rag-docs-toolbar">
          <div className="rag-docs-search">
            <span className="rag-docs-search-icon">🔍</span>
            <input
              ref={searchRef}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Escape") clearFilters(); }}
              placeholder="Search documents by name, URL or format…"
              aria-label="Search documents"
            />
            {search && (
              <button className="rag-docs-search-clear" title="Clear" onClick={() => setSearch("")}>×</button>
            )}
          </div>
          <div className="rag-docs-chips">
            {availableCats.map((c) => (
              <button
                key={c.key}
                className={`rag-docs-chip ${cats.has(c.key) ? "on" : ""}`}
                onClick={() => toggleCat(c.key)}
                title={`Filter: ${c.label}`}
              >
                {c.label}<span className="rag-docs-chip-n">{c.count}</span>
              </button>
            ))}
            {filtering && (
              <button className="rag-docs-chip rag-docs-chip-clear" onClick={clearFilters}>
                Clear
              </button>
            )}
          </div>
          <div className="rag-docs-count">
            {filtering ? `${shownCount} of ${totalCount}` : `${totalCount} document${totalCount > 1 ? "s" : ""}`}
          </div>
        </div>
      )}

      <div className="rag-docs-list">
        {docs.length === 0 && (
          <div className="rag-empty-state">
            No documents yet — upload a file, import from Drive, or scrape a URL
          </div>
        )}
        {totalCount > 0 && shownCount === 0 && (
          <div className="rag-empty-state">
            No documents match your search.
            <button className="rag-btn rag-btn-xs" style={{ marginLeft: 8 }} onClick={clearFilters}>
              Clear filters
            </button>
          </div>
        )}
        {grouped.map((g) => (
          <React.Fragment key={g.key}>
            <div className="rag-docs-cat">
              <span className="rag-docs-cat-name">{g.label}</span>
              <span className="rag-docs-cat-count">{g.items.length}</span>
              <span className="rag-docs-cat-rule" />
            </div>
            {g.items.map((d) => (
          <div key={d.id} className="rag-doc-card">
            <div className="rag-doc-icon">
              {d.source_type === "url"
                ? "URL"
                : d.source_type === "google_drive"
                  ? "GD"
                  : (d.file_type || "?").toUpperCase()}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="rag-doc-name">
                {terms.length
                  ? _highlight(d.file_name || "", terms).map((p, i) =>
                      p.hit ? <mark key={i} className="rag-hl">{p.t}</mark> : <span key={i}>{p.t}</span>,
                    )
                  : d.file_name}
              </div>
              <div className="rag-doc-meta">
                {d.file_size ? `${(d.file_size / 1024).toFixed(1)} KB` : ""}
                {d.num_chunks > 0 && ` · ${d.num_chunks} chunks`}
                {d.source_type === "google_drive" && " · Google Drive"}
              </div>

              {/* Chunking strategy & indexing now live in the Chunking section. */}

              {/* Per-document image extraction (PDF/DOCX/PPTX, before indexing).
                  Web/URL docs choose this in the scrape form instead. */}
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
          </React.Fragment>
        ))}
      </div>
    </>
  );
};

export default UploadsPanel;
