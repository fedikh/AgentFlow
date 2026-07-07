import React from "react";
import LLMSourceSelector from "./LLMSourceSelector";
import EmbeddingSourceSelector from "./EmbeddingSourceSelector";
import SavedConfigBar from "./SavedConfigBar";
import AccessSelector from "./AccessSelector";

const LABELS = {
  chunk: "Chunking",
  embed: "Embeddings",
  llm: "LLM Configuration",
  retrieval: "Retrieval",
  access: "Access",
  eval: "Evaluation",
};

const ConfigPanel = ({
  panel,
  cfg,
  space,
  setC,
  saveCfg,
  savingCfg,
  embedModels,
  llmModels,
  llmState,
  loadingLlm,
  deptUsers = [],
  loadingDeptUsers = false,
  docs = [],
  handleSetDocStrategy = () => {},
  handleProcess = () => {},
  handleProcessAll = () => {},
  processing = false,
  openModal = () => {},
}) => {
  if (!cfg) return null;

  // ── Batch 3: per-document chunking strategy + indexing (moved from Uploads) ──
  const parsedDocs = docs.filter((d) => d.has_extracted_content);
  const extractedCount = docs.filter((d) => d.status === "EXTRACTED").length;

  // Apply a patch object coming from LLMSourceSelector via setC
  const applyLlmPatch = (patch) =>
    Object.entries(patch).forEach(([k, v]) => setC(k, v));

  // ── Access control (Batch 1) — allow-list; [] means everyone (open) ──
  const allowed = cfg.allowed_user_ids || [];

  return (
    <div className="rag-cfg-panel">
      <div className="rag-cfg-head">
        <div className="rag-cfg-title">{LABELS[panel]}</div>
        <button
          className="rag-btn rag-btn-sm rag-btn-dark"
          onClick={saveCfg}
          disabled={savingCfg}
        >
          {savingCfg ? "Saving…" : "Save"}
        </button>
      </div>

      {/* Currently-saved summary for this stage (chunk/embed/llm/retrieval) */}
      {["chunk", "embed", "llm", "retrieval"].includes(panel) && (
        <SavedConfigBar space={space} panelKey={panel} />
      )}

      {/* CHUNKING */}
      {panel === "chunk" && (
        <>
          <label className="rag-cfg-label">Chunking mode</label>
          <div className="rag-cfg-cards">
            {[
              {
                k: "FIXED_ALL",
                n: "Single",
                d: "One strategy for all documents",
              },
              {
                k: "PER_DOCUMENT",
                n: "Per document",
                d: "Choose strategy per file",
              },
              {
                k: "ADAPTIVE",
                n: "Adaptive",
                d: "Auto-pick the best per file",
              },
            ].map((m) => (
              <button
                key={m.k}
                className={`rag-cfg-card ${(cfg.chunk_mode || "FIXED_ALL") === m.k ? "active" : ""}`}
                onClick={() => setC("chunk_mode", m.k)}
              >
                <div className="rag-cfg-card-n">{m.n}</div>
                <div className="rag-cfg-card-d">{m.d}</div>
              </button>
            ))}
          </div>

          {(cfg.chunk_mode || "FIXED_ALL") === "ADAPTIVE" && (
            <div className="rag-cfg-hint">
              Adaptive mode tries every strategy on each document and keeps the
              best one. The winning strategy is shown on each document in the
              Uploads panel. Note: slower, since each file is chunked multiple
              times.
            </div>
          )}
          {(cfg.chunk_mode || "FIXED_ALL") === "PER_DOCUMENT" && (
            <div className="rag-cfg-hint">
              Pick a strategy for each document individually in the Uploads
              panel. The strategy below is used as the default for files you
              haven't set.
            </div>
          )}

          {/* Global strategy — only in Single mode. In Per-document you set the
              strategy on each file below; in Adaptive it's auto-picked. */}
          {(cfg.chunk_mode || "FIXED_ALL") === "FIXED_ALL" && (
            <>
              <label className="rag-cfg-label">
                Strategy — applied to every document
              </label>
              <div className="rag-cfg-cards">
                {[
                  { k: "FIXED", n: "Fixed", d: "Every N characters" },
                  { k: "SEMANTIC", n: "Semantic", d: "On topic change" },
                  { k: "HIERARCHICAL", n: "Hierarchical", d: "Parent + child" },
                ].map((s) => (
                  <button
                    key={s.k}
                    className={`rag-cfg-card ${cfg.chunk_strategy === s.k ? "active" : ""}`}
                    onClick={() => setC("chunk_strategy", s.k)}
                  >
                    <div className="rag-cfg-card-n">{s.n}</div>
                    <div className="rag-cfg-card-d">{s.d}</div>
                  </button>
                ))}
              </div>
            </>
          )}

          <div className="rag-cfg-grid2">
            <div>
              <label className="rag-cfg-label">Chunk size (chars)</label>
              <input
                type="number"
                min="256"
                max="1024"
                step="1"
                value={cfg.chunk_size}
                onChange={(e) => setC("chunk_size", e.target.value)}
                className="rag-cfg-select"
              />
            </div>
            <div>
              <label className="rag-cfg-label">Overlap (chars)</label>
              <input
                type="number"
                min="0"
                max="200"
                step="1"
                value={cfg.chunk_overlap}
                onChange={(e) => setC("chunk_overlap", e.target.value)}
                className="rag-cfg-select"
              />
            </div>
          </div>

          {/* ── Batch 3: per-document strategy + indexing (moved from Uploads) ── */}
          <div
            style={{
              borderTop: "1px solid var(--rag-border, #e2e8f0)",
              margin: "18px 0 12px",
            }}
          />
          <div className="rag-cfg-head" style={{ marginBottom: 6 }}>
            <label className="rag-cfg-label" style={{ margin: 0 }}>
              {(cfg.chunk_mode || "FIXED_ALL") === "PER_DOCUMENT"
                ? "Per-document strategy & indexing"
                : "Documents · indexing"}
            </label>
            {extractedCount > 0 && (
              <button
                className="rag-btn rag-btn-sm rag-btn-dark"
                onClick={handleProcessAll}
                disabled={processing}
              >
                {processing ? "…" : `Process all (${extractedCount})`}
              </button>
            )}
          </div>
          <div className="rag-cfg-hint">
            {(cfg.chunk_mode || "FIXED_ALL") === "PER_DOCUMENT"
              ? "Choose a strategy for each document (or leave Default to use the fallback above), then Process to chunk & index it."
              : (cfg.chunk_mode || "FIXED_ALL") === "ADAPTIVE"
                ? "Each document is chunked with the auto-selected best strategy. Process to chunk & index it."
                : `Every document is chunked with the “${cfg.chunk_strategy || "FIXED"}” strategy above. Process to chunk & index it.`}
          </div>

          {parsedDocs.length === 0 && (
            <div className="rag-cfg-hint">
              No parsed documents yet. Upload files and run Load + Parse in the
              Uploads section first.
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 10 }}>
            {parsedDocs.map((d) => (
              <div
                key={d.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: 8,
                  border: "1px solid var(--rag-border, #e2e8f0)",
                  borderRadius: 8,
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    className="rag-cfg-model-n"
                    style={{
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {d.file_name}
                  </div>
                  <div className="rag-cfg-model-note">
                    {d.status === "INDEXED"
                      ? `Indexed · ${d.num_chunks || 0} chunks`
                      : d.status === "PROCESSING"
                        ? "Processing…"
                        : "Parsed — not indexed"}
                  </div>
                </div>

                {(cfg.chunk_mode || "FIXED_ALL") === "PER_DOCUMENT" ? (
                  <select
                    className="rag-doc-strategy-select"
                    value={d.chunk_strategy || ""}
                    onChange={(e) => handleSetDocStrategy(d.id, e.target.value)}
                  >
                    <option value="">Default</option>
                    <option value="FIXED">Fixed</option>
                    <option value="SEMANTIC">Semantic</option>
                    <option value="HIERARCHICAL">Hierarchical</option>
                  </select>
                ) : (
                  <span className="rag-doc-strategy-fixed">
                    {(cfg.chunk_mode || "FIXED_ALL") === "ADAPTIVE"
                      ? d.chunk_strategy
                        ? `Auto · ${d.chunk_strategy}`
                        : "Auto"
                      : cfg.chunk_strategy || "FIXED"}
                  </span>
                )}

                <button
                  className="rag-btn rag-btn-xs rag-btn-dark"
                  onClick={() => handleProcess(d.id)}
                  disabled={processing}
                >
                  {d.status === "INDEXED" ? "Re-index" : "Process"}
                </button>

                {d.status === "INDEXED" && (
                  <button
                    className="rag-btn rag-btn-xs"
                    onClick={() => openModal("chunks", d)}
                  >
                    View chunks
                  </button>
                )}
              </div>
            ))}
          </div>
        </>
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
          <label className="rag-cfg-label">
            Semantic {Math.round(cfg.semantic_weight * 100)}% · Keyword{" "}
            {Math.round((1 - cfg.semantic_weight) * 100)}%
          </label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={cfg.semantic_weight}
            onChange={(e) => setC("semantic_weight", e.target.value)}
            className="rag-cfg-range"
          />
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
          <label className="rag-cfg-check">
            <input
              type="checkbox"
              checked={!!cfg.reranking_enabled}
              onChange={(e) => setC("reranking_enabled", e.target.checked)}
            />
            Reranking (LLM re-ranking)
          </label>
        </>
      )}

      {/* ACCESS (Batch 1) */}
      {panel === "access" && (
        <>
          <label className="rag-cfg-label">Who can use this space</label>
          <AccessSelector
            users={deptUsers}
            allowedIds={allowed}
            onChange={(next) => setC("allowed_user_ids", next)}
            loading={loadingDeptUsers}
          />
          <div className="rag-cfg-hint" style={{ marginTop: 10 }}>
            Click a member to deactivate (exclude) them. Changes apply after you
            press <strong>Save</strong>. Admin & IT always have access, so
            restrictions only affect end-users.
          </div>
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
  );
};

export default ConfigPanel;
