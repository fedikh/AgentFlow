import React, { useEffect, useState } from "react";
import { fetchDocumentBlobUrl } from "../../services/ragApi";

/**
 * DocViewerModal — inline preview of an original uploaded document.
 *
 * The file route is auth-protected and cross-origin, so a bare <iframe src>
 * wouldn't send the cookie. We fetch the file as a blob (with credentials) and
 * feed the object URL to an <iframe> (PDF) or <img> (image). The object URL is
 * revoked on close/unmount.
 */
const IMAGE_EXT = ["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"];

const DocViewerModal = ({ spaceId, doc, onClose }) => {
  const [state, setState] = useState({ loading: true, url: null, type: "", error: "" });

  useEffect(() => {
    let cancelled = false;
    let objUrl = null;
    setState({ loading: true, url: null, type: "", error: "" });
    fetchDocumentBlobUrl(spaceId, doc.id)
      .then(({ url, type }) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        objUrl = url;
        setState({ loading: false, url, type, error: "" });
      })
      .catch((e) =>
        setState({ loading: false, url: null, type: "", error: e.message }),
      );
    return () => {
      cancelled = true;
      if (objUrl) URL.revokeObjectURL(objUrl);
    };
  }, [spaceId, doc.id]);

  const ext = (doc.file_type || doc.file_name?.split(".").pop() || "").toLowerCase();
  const isPdf = ext === "pdf" || state.type === "application/pdf";
  const isImg = IMAGE_EXT.includes(ext) || (state.type || "").startsWith("image/");

  return (
    <div className="dv-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dv-modal">
        <div className="dv-head">
          <span className="dv-title" title={doc.file_name}>
            📄 {doc.file_name}
          </span>
          <div style={{ display: "flex", gap: 8 }}>
            {state.url && (
              <a
                className="rag-btn rag-btn-sm"
                href={state.url}
                download={doc.file_name}
              >
                Download
              </a>
            )}
            <button className="rag-btn rag-btn-sm rag-btn-dark" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
        <div className="dv-body">
          {state.loading && <div className="dv-msg">Loading preview…</div>}
          {state.error && (
            <div className="dv-msg">Couldn't open this file: {state.error}</div>
          )}
          {!state.loading && !state.error && state.url && (
            <>
              {isPdf && (
                <iframe title={doc.file_name} src={state.url} className="dv-frame" />
              )}
              {!isPdf && isImg && (
                <img alt={doc.file_name} src={state.url} className="dv-img" />
              )}
              {!isPdf && !isImg && (
                <div className="dv-msg">
                  Preview not available for this file type.{" "}
                  <a href={state.url} download={doc.file_name}>
                    Download instead
                  </a>
                  .
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default DocViewerModal;
