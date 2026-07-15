import React, { useState } from "react";
import "../../../styles/it/versions.css";

/**
 * VersionsPanel — save/apply/deploy config snapshots of a space.
 *
 * A version stores the pipeline config only (not the index). Deploying a version
 * applies its config to the space and flips it ACTIVE; the IT then re-indexes so
 * the live answers match. "Apply" loads a version's config into the working form
 * without deploying it.
 */
const cfgChips = (cfg = {}) => {
  const items = [];
  if (cfg.chunk_strategy)
    items.push(["chunk", `${cfg.chunk_strategy} · ${cfg.chunk_size ?? "?"}`]);
  if (cfg.embedding_model)
    items.push(["embed", String(cfg.embedding_model).split("/").pop()]);
  if (cfg.llm_model) items.push(["llm", cfg.llm_model]);
  if (cfg.top_k != null) items.push(["top-k", cfg.top_k]);
  return items;
};

const fmtDate = (s) => {
  try {
    return new Date(s).toLocaleString();
  } catch {
    return s;
  }
};

const VersionsPanel = ({
  space,
  versions = [],
  loading = false,
  canBuild = true,
  isOwner = false,
  editable = true,
  onSaveVersion,
  onApplyVersion,
  onDeployVersion,
  onDeleteVersion,
  onReindex,
  reindexing = false,
}) => {
  const [showSave, setShowSave] = useState(false);
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");

  const deployedId = space?.deployed_version_id;
  const paused = space?.status === "EDITING";
  const nextLabel = `v${(versions[0]?.version_number || 0) + 1}`;

  const submitSave = () => {
    onSaveVersion({ label: label.trim() || nextLabel, notes: notes.trim() });
    setLabel("");
    setNotes("");
    setShowSave(false);
  };

  return (
    <div className="rag-cfg-panel">
      <div className="vp-head">
        <div>
          <div className="vp-head-title">Versions</div>
          <div className="vp-head-sub">
            Save config snapshots, compare them, and deploy the one you want.
          </div>
        </div>
        {canBuild && editable && (
          <button
            className="rag-btn rag-btn-sm rag-btn-dark"
            onClick={() => setShowSave((v) => !v)}
          >
            {showSave ? "Cancel" : "＋ Save current config"}
          </button>
        )}
      </div>

      {canBuild && !editable && (
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
          🔒 This space is <strong>deployed &amp; live</strong> — versions are
          read-only. Click <strong>Stop to edit</strong> in the header to save,
          load or deploy a different version.
        </div>
      )}

      {canBuild && editable && !isOwner && (
        <div className="rag-cfg-hint" style={{ marginBottom: 12 }}>
          You can save and load versions, but only the space <strong>owner</strong>{" "}
          can deploy.
        </div>
      )}

      {showSave && (
        <div className="vp-card" style={{ marginBottom: 12 }}>
          <label className="rag-cfg-label">Version name</label>
          <input
            className="rag-cfg-select"
            value={label}
            placeholder={nextLabel}
            onChange={(e) => setLabel(e.target.value)}
          />
          <label className="rag-cfg-label">Notes (optional)</label>
          <input
            className="rag-cfg-select"
            value={notes}
            placeholder="e.g. bigger chunks + reranking"
            onChange={(e) => setNotes(e.target.value)}
          />
          <div className="vp-actions">
            <button className="rag-btn rag-btn-sm rag-btn-blue" onClick={submitSave}>
              Save version
            </button>
          </div>
        </div>
      )}

      {paused && (
        <div className="vp-banner reindex">
          <span>⏸️</span>
          <div style={{ flex: 1 }}>
            <strong>Paused for editing.</strong> This space is offline — end users
            can't use it. Re-deploy a version (or use “Re-deploy” in the header) to
            bring it back online.
          </div>
        </div>
      )}

      {space?.reindex_required && editable && (
        <div className="vp-banner reindex">
          <span>⚠️</span>
          <div style={{ flex: 1 }}>
            <strong>Re-index needed.</strong> Chunking/embedding settings changed
            — rebuild the index so answers reflect this configuration.
          </div>
          {canBuild && (
            <button
              className="rag-btn rag-btn-sm"
              onClick={onReindex}
              disabled={reindexing}
            >
              {reindexing ? "Re-indexing…" : "Re-index now"}
            </button>
          )}
        </div>
      )}

      {loading ? (
        <div className="vp-banner empty">Loading versions…</div>
      ) : versions.length === 0 ? (
        <div className="vp-banner empty">
          No versions yet. Tune the pipeline, then “Save current config” to create
          v1.
        </div>
      ) : (
        <div className="vp-list">
          {versions.map((v) => {
            // The deployed version is only actually LIVE when the space is ACTIVE.
            // While paused for editing (EDITING), it's the deployed version but
            // temporarily offline → show "Paused", not "Live".
            const isDeployed = v.id === deployedId || v.status === "DEPLOYED";
            const isLive = isDeployed && !paused;
            const badge = isLive
              ? "deployed"
              : isDeployed && paused
                ? "paused"
                : v.status === "ARCHIVED"
                  ? "archived"
                  : "saved";
            return (
              <div
                key={v.id}
                className={`vp-card ${isLive ? "deployed" : isDeployed && paused ? "paused" : ""}`}
              >
                <div className="vp-card-top">
                  <span className="vp-label">{v.label}</span>
                  <span className={`vp-badge ${badge}`}>
                    {isLive ? "Deployed" : isDeployed && paused ? "Paused" : v.status}
                  </span>
                  <span className="vp-when">{fmtDate(v.created_at)}</span>
                </div>
                {v.notes && <p className="vp-notes">{v.notes}</p>}
                <div className="vp-chips">
                  {cfgChips(v.config).map(([k, val]) => (
                    <span className="vp-chip" key={k}>
                      <b>{k}</b> {String(val)}
                    </span>
                  ))}
                </div>
                {canBuild && (
                  <div className="vp-actions">
                    <button
                      className="rag-btn rag-btn-sm"
                      onClick={() => onApplyVersion(v)}
                      disabled={!editable}
                      title={
                        !editable
                          ? "Deployed & live — Stop to edit first"
                          : "Load this config into the editor (no deploy)"
                      }
                    >
                      Load config
                    </button>
                    {isOwner && (
                      <button
                        className="rag-btn rag-btn-sm rag-btn-blue"
                        onClick={() => onDeployVersion(v)}
                        disabled={isLive || !editable}
                        title={
                          isDeployed && paused
                            ? "Bring this version back online"
                            : !editable
                              ? "Deployed & live — Stop to edit first"
                              : undefined
                        }
                      >
                        {isLive
                          ? "Live"
                          : isDeployed && paused
                            ? "Re-deploy"
                            : "Deploy"}
                      </button>
                    )}
                    <button
                      className="rag-btn rag-btn-sm rag-btn-red"
                      onClick={() => onDeleteVersion(v)}
                      disabled={isDeployed || !editable}
                      title={isDeployed ? "Can't delete the deployed version" : "Delete"}
                    >
                      Delete
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default VersionsPanel;
