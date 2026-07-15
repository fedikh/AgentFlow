import React, { useState } from "react";

/**
 * DeployModal — confirms deploying a RAG space to end users.
 *
 * mode="current"  → snapshot the current working config into a new version and
 *                   deploy it (asks for a label + notes).
 * mode="version"  → deploy an already-saved version (label is fixed).
 *
 * In both cases the IT decides whether to "publish" (make it visible to end
 * users). Deploying always sets the space ACTIVE; publishing flips is_private
 * off. A re-index reminder is shown because the live index must match the config.
 */
const DeployModal = ({ mode = "current", version = null, nextLabel = "v1", busy = false, onConfirm, onClose }) => {
  const [label, setLabel] = useState(mode === "version" ? version?.label || "" : nextLabel);
  const [notes, setNotes] = useState("");
  const [publish, setPublish] = useState(true);

  const confirm = () => onConfirm({ label: label.trim() || nextLabel, notes: notes.trim(), publish });

  return (
    <div className="rag-create-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="rag-create-modal" style={{ maxWidth: 460 }}>
        <div className="rag-create-modal-head">
          <span className="rag-create-title">
            {mode === "version" ? `Deploy ${version?.label}` : "Deploy space"}
          </span>
          <button className="rag-create-x" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="rag-create-body">
          {mode === "current" && (
            <>
              <label className="rag-create-label">Version name</label>
              <input
                className="rag-create-input"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder={nextLabel}
              />
              <label className="rag-create-label">Notes (optional)</label>
              <input
                className="rag-create-input"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="What changed in this version?"
              />
            </>
          )}

          <label
            className="rag-cfg-check"
            style={{ marginTop: 14, display: "flex", gap: 8, alignItems: "flex-start" }}
          >
            <input
              type="checkbox"
              checked={publish}
              onChange={(e) => setPublish(e.target.checked)}
              style={{ marginTop: 2 }}
            />
            <span>
              <strong>Publish to end users</strong>
              <div className="rag-cfg-hint" style={{ margin: "2px 0 0" }}>
                Make this space visible to the allowed end users of its department.
                Leave unchecked to deploy privately (only you &amp; collaborators).
              </div>
            </span>
          </label>

          <div
            className="rag-cfg-hint"
            style={{
              marginTop: 12,
              padding: "8px 10px",
              background: "rgba(245,158,11,.10)",
              border: "1px solid rgba(245,158,11,.35)",
              borderRadius: 8,
              color: "#92400e",
            }}
          >
            ⚠️ After deploying you may need to <strong>re-index</strong> the
            documents so the live answers match this configuration.
          </div>
        </div>

        <div className="rag-create-foot">
          <button className="rag-btn" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="rag-btn rag-btn-blue" onClick={confirm} disabled={busy}>
            {busy ? "Deploying…" : "Deploy"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DeployModal;
