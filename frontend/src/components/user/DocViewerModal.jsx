import React, { useEffect, useState } from "react";
import { fetchDocumentBlobUrl, getPublicDocumentText } from "../../services/ragApi";
import { Download, FileText, X } from "lucide-react";
import "../../styles/user/agentChat.css";

/**
 * DocViewerModal — inline preview of an original uploaded document, in the
 * agent-chat design system (black / white / blue). EVERY format opens in its
 * native rendering:
 *
 *   pdf                    → browser PDF viewer (iframe on the blob)
 *   images                 → <img>
 *   csv                    → real table (sticky header)
 *   json                   → pretty-printed
 *   txt / md / log / xml   → text view
 *   html                   → sandboxed render
 *   docx / xlsx / pptx / … → the parsed text the platform indexed
 *                            (+ Download for the original)
 *
 * The file route is auth-protected and cross-origin, so files are fetched as
 * blobs (with credentials); object URLs are revoked on close/unmount.
 */
const IMAGE_EXT = ["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"];
const TEXT_EXT = ["txt", "md", "markdown", "log", "json", "xml", "csv"];
const HTML_EXT = ["html", "htm"];

const fmtSize = (b) => {
  if (!b) return "";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
};

/* Tiny CSV parser good enough for preview (handles ; or , + quoted cells). */
const parseCsv = (text, maxRows = 300) => {
  const lines = text.split(/\r?\n/).filter((l) => l.trim()).slice(0, maxRows);
  if (!lines.length) return null;
  const delim =
    (lines[0].match(/;/g) || []).length > (lines[0].match(/,/g) || []).length ? ";" : ",";
  const split = (line) => {
    const out = [];
    let cur = "", inQ = false;
    for (const ch of line) {
      if (ch === '"') inQ = !inQ;
      else if (ch === delim && !inQ) { out.push(cur); cur = ""; }
      else cur += ch;
    }
    out.push(cur);
    return out;
  };
  return lines.map(split);
};

const DocViewerModal = ({ spaceId, doc, onClose }) => {
  const [state, setState] = useState({ loading: true });

  const ext = (doc.file_type || doc.file_name?.split(".").pop() || "").toLowerCase();

  useEffect(() => {
    let cancelled = false;
    let objUrl = null;
    setState({ loading: true });

    const load = async () => {
      // 1) the original file as a blob (also powers the Download button)
      let url = null, type = "";
      try {
        const r = await fetchDocumentBlobUrl(spaceId, doc.id);
        url = r.url; type = r.type || "";
        objUrl = url;
      } catch { /* file may be gone — text preview can still work */ }
      if (cancelled) { if (url) URL.revokeObjectURL(url); return; }

      const isPdf = ext === "pdf" || type === "application/pdf";
      const isImg = IMAGE_EXT.includes(ext) || type.startsWith("image/");

      if (isPdf && url) return setState({ loading: false, kind: "pdf", url });
      if (isImg && url) return setState({ loading: false, kind: "img", url });

      // text-ish formats: read the blob itself
      if (url && (TEXT_EXT.includes(ext) || HTML_EXT.includes(ext))) {
        try {
          const raw = await (await fetch(url)).blob().then((b) => b.text());
          if (cancelled) return;
          if (HTML_EXT.includes(ext))
            return setState({ loading: false, kind: "html", url, html: raw });
          if (ext === "csv") {
            const grid = parseCsv(raw);
            if (grid) return setState({ loading: false, kind: "csv", url, grid });
          }
          const text = ext === "json"
            ? (() => { try { return JSON.stringify(JSON.parse(raw), null, 2); } catch { return raw; } })()
            : raw;
          return setState({ loading: false, kind: "text", url, text: text.slice(0, 300000) });
        } catch { /* fall through to parsed text */ }
      }

      // binary formats (docx/xlsx/pptx/…) → the parsed text the platform indexed
      try {
        const r = await getPublicDocumentText(spaceId, doc.id);
        if (cancelled) return;
        return setState({ loading: false, kind: "extracted", url, text: r.text });
      } catch (e) {
        if (cancelled) return;
        return setState({
          loading: false, kind: url ? "download-only" : "error", url,
          error: url ? "" : (e.message || "Couldn't open this file"),
        });
      }
    };
    load();

    return () => {
      cancelled = true;
      if (objUrl) URL.revokeObjectURL(objUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spaceId, doc.id]);

  const s = state;
  return (
    <div className="acv-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="acv-modal">
        {/* header */}
        <div className="acv-head">
          <span className="ac-ext">{(ext || "file").toUpperCase()}</span>
          <span className="acv-title" title={doc.file_name}>
            {doc.file_name}
            {doc.file_size ? <span className="acv-size">{fmtSize(doc.file_size)}</span> : null}
          </span>
          {s.url && (
            <a className="acv-btn" href={s.url} download={doc.file_name}>
              <Download size={13} /> Download
            </a>
          )}
          <button className="acv-btn dark" onClick={onClose}>
            <X size={13} /> Close
          </button>
        </div>

        {/* body */}
        <div className="acv-body">
          {s.loading && <div className="acv-msg">Loading preview…</div>}
          {s.kind === "error" && <div className="acv-msg">{s.error}</div>}

          {s.kind === "pdf" && (
            <iframe title={doc.file_name} src={s.url} className="acv-frame" />
          )}
          {s.kind === "img" && <img alt={doc.file_name} src={s.url} className="acv-img" />}
          {s.kind === "html" && (
            <iframe title={doc.file_name} srcDoc={s.html} sandbox=""
              className="acv-frame" style={{ background: "#fff" }} />
          )}
          {s.kind === "csv" && (
            <div className="acv-scroll">
              <table className="acv-table">
                <tbody>
                  {s.grid.map((row, i) => (
                    <tr key={i}>
                      {row.map((cell, j) => <td key={j}>{cell}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {(s.kind === "text" || s.kind === "extracted") && (
            <div className="acv-scroll">
              {s.kind === "extracted" && (
                <div className="acv-note">
                  <FileText size={13} />
                  Text preview — the original layout isn't shown; use Download
                  for the real file.
                </div>
              )}
              <pre className={`acv-pre ${s.kind === "extracted" ? "prose" : ""}`}>
                {s.text}
              </pre>
            </div>
          )}
          {s.kind === "download-only" && (
            <div className="acv-msg">
              No inline preview for this file type — use the Download button above.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DocViewerModal;
