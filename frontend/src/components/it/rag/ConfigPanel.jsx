import React from "react";
import LLMSourceSelector from "./LLMSourceSelector";
import EmbeddingSourceSelector from "./EmbeddingSourceSelector";
import SavedConfigBar from "./SavedConfigBar";
import AccessSelector from "./AccessSelector";
import ChunkingConfig from "./ChunkingConfig";
import RetrievalPipeline from "./RetrievalPipeline";

const LABELS = {
  chunk: "Chunking & Indexing",
  embed: "Embeddings",
  llm: "LLM Configuration",
  retrieval: "Retrieval",
  access: "Access",
  eval: "Evaluation",
};

const SUBTITLES = {
  chunk: "How documents are split, then chunked + embedded + indexed on Process.",
  embed: "The vector model that turns chunks into searchable vectors, at each model's native dimension.",
  llm: "The model that writes answers from the retrieved chunks.",
  retrieval: "How relevant chunks are found for each question.",
  access: "Who in the department can query this space.",
};

const ConfigPanel = ({
  panel,
  cfg,
  space,
  setC,
  saveCfg,
  savingCfg,
  embedModels,
  deptUsers = [],
  loadingDeptUsers = false,
  docs = [],
  chunkCatalog = null,
  handleSetDocChunking = () => {},
  handleChunkModeChange = () => {},
  handleProcess = () => {},
  handleProcessAll = () => {},
  processing = false,
  openModal = () => {},
  canBuild = true,
  editable = true,
  setPanel = () => {},
}) => {
  if (!cfg) return null;

  // A deployed (live) space is locked — the form is shown read-only until the
  // owner clicks "Stop to edit".
  const lockStyle = editable
    ? undefined
    : { pointerEvents: "none", opacity: 0.6, userSelect: "none" };

  // ── Batch 3: per-document chunking strategy + indexing (moved from Uploads) ──
  const parsedDocs = docs.filter((d) => d.has_extracted_content);
  const extractedCount = docs.filter((d) => d.status === "EXTRACTED").length;

  // Apply a patch object coming from LLMSourceSelector via setC
  const applyLlmPatch = (patch) =>
    Object.entries(patch).forEach(([k, v]) => setC(k, v));

  // ── Access control (Batch 1) — allow-list; [] means everyone (open) ──
  // The owner always has access, so exclude them from the member picker
  // (listing them as toggleable is misleading — you can't lock yourself out).
  const ownerId = space?.owner_id;
  const allowed = (cfg.allowed_user_ids || []).filter((id) => id !== ownerId);
  const accessUsers = deptUsers.filter((u) => u.id !== ownerId);

  return (
    <div className="rag-cfg-panel">
      <div className="rag-cfg-head">
        <div>
          <div className="rag-cfg-title">{LABELS[panel]}</div>
          {SUBTITLES[panel] && <div className="rag-cfg-sub">{SUBTITLES[panel]}</div>}
        </div>
        {canBuild && (
          <button
            className="rag-btn rag-btn-sm rag-btn-dark"
            onClick={saveCfg}
            disabled={savingCfg || !editable}
            title={!editable ? "Deployed & live — Stop to edit first" : undefined}
          >
            {savingCfg ? "Saving…" : "Save"}
          </button>
        )}
      </div>

      {canBuild && !editable && (
        <div
          className="rag-cfg-hint"
          style={{
            marginBottom: 10,
            padding: "8px 11px",
            borderRadius: 8,
            background: "rgba(22,163,74,.08)",
            border: "1px solid rgba(22,163,74,.3)",
            color: "#166534",
          }}
        >
          🔒 This space is <strong>deployed &amp; live</strong> — settings are
          read-only. Click <strong>Stop to edit</strong> in the header to change
          them.
        </div>
      )}

      <div style={lockStyle}>
      {/* Currently-saved summary for this stage (chunk/embed/llm/retrieval) */}
      {["chunk", "embed", "llm", "retrieval"].includes(panel) && (
        <SavedConfigBar space={space} panelKey={panel} />
      )}

      {/* CHUNKING */}
      {panel === "chunk" && (
        <ChunkingConfig
          cfg={cfg}
          setC={setC}
          catalog={chunkCatalog}
          parsedDocs={parsedDocs}
          extractedCount={extractedCount}
          handleSetDocChunking={handleSetDocChunking}
          handleChunkModeChange={handleChunkModeChange}
          handleProcess={handleProcess}
          handleProcessAll={handleProcessAll}
          processing={processing}
          openModal={openModal}
          canBuild={canBuild}
          onGoEmbed={() => setPanel("embed")}
        />
      )}

      {/* EMBEDDING */}
      {panel === "embed" && (
        <EmbeddingSourceSelector
          value={cfg}
          onChange={applyLlmPatch}
          hasOwnKey={cfg.embedding_has_own_key}
          embedModels={embedModels}
        />
      )}

      {/* LLM */}
      {panel === "llm" && (
        <>
          <LLMSourceSelector
            value={cfg}
            onChange={applyLlmPatch}
            hasOwnKey={cfg.llm_has_own_key}
          />

          <label className="rag-cfg-label" style={{ marginTop: 18 }}>
            Temperature
          </label>
          <input
            type="number"
            min="0"
            max="2"
            step="0.1"
            value={cfg.llm_temperature ?? 0.2}
            onChange={(e) => setC("llm_temperature", e.target.value)}
            className="rag-cfg-select"
          />
          <div className="rag-cfg-hint">
            0 = deterministic/factual, 2 = most creative. Range 0–2.
          </div>

          <label className="rag-cfg-label">Max tokens</label>
          <input
            type="number"
            min="256"
            max="8000"
            step="1"
            value={cfg.llm_max_tokens ?? 1024}
            onChange={(e) => setC("llm_max_tokens", e.target.value)}
            className="rag-cfg-select"
          />
          <div className="rag-cfg-hint">
            Maximum length of the generated answer. Higher = longer answers but
            slower and more costly. Range 256–8000; 1024 suits most Q&amp;A.
          </div>

          <label className="rag-cfg-label">System prompt</label>
          <textarea
            className="rag-cfg-textarea"
            rows={3}
            placeholder="Leave empty for the default prompt"
            value={cfg.system_prompt || ""}
            onChange={(e) => setC("system_prompt", e.target.value)}
          />
        </>
      )}

      {/* RETRIEVAL */}
      {panel === "retrieval" && (
        <>
          <label className="rag-cfg-label">Top-K · {cfg.top_k}</label>
          <input
            type="range"
            min="1"
            max="20"
            step="1"
            value={cfg.top_k}
            onChange={(e) => setC("top_k", e.target.value)}
            className="rag-cfg-range"
          />

          {/* The full engine, stage by stage (saved in retrieval_params). */}
          <label className="rag-cfg-label" style={{ marginTop: 20 }}>
            Retrieval pipeline
          </label>
          <RetrievalPipeline cfg={cfg} setC={setC} />
        </>
      )}

      {/* ACCESS (Batch 1) */}
      {panel === "access" && (
        <>
          <label className="rag-cfg-label">Who can use this space</label>
          {cfg.is_private ? (
            <div
              style={{
                display: "flex",
                gap: 10,
                padding: "12px 14px",
                borderRadius: 10,
                background: "rgba(180,83,9,.08)",
                border: "1px solid rgba(180,83,9,.28)",
              }}
            >
              <span>🔒</span>
              <div>
                <div style={{ fontWeight: 700, fontSize: 13, color: "#92400e" }}>
                  Private — no end users
                </div>
                <div style={{ fontSize: 12.5, color: "#92400e", marginTop: 2 }}>
                  Only you and your IT team can use this space. To let end users
                  in, <strong>Deploy</strong> it with “Publish to end users” — then
                  you can choose exactly who here.
                </div>
              </div>
            </div>
          ) : (
            <>
              <AccessSelector
                users={accessUsers}
                allowedIds={allowed}
                onChange={(next) => setC("allowed_user_ids", next)}
                loading={loadingDeptUsers}
              />
              <div className="rag-cfg-hint" style={{ marginTop: 10 }}>
                Choose who in the department can use this agent — end users and IT
                members. Click a member to exclude them. Changes apply after you
                press <strong>Save</strong>. You (the owner) and admins always
                have access.
              </div>
            </>
          )}
        </>
      )}

      {/* EVAL */}
      {panel === "eval" && (
        <p className="rag-cfg-hint">
          Evaluation (test set + score) is coming in the next step. It will
          measure the quality of this config (hit rate, MRR) to compare
          versions.
        </p>
      )}
      </div>
    </div>
  );
};

export default ConfigPanel;
