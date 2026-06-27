import React from "react";

const LABELS = {
  chunk: "Chunking",
  embed: "Embeddings",
  llm: "LLM Configuration",
  retrieval: "Retrieval",
  eval: "Evaluation",
};

const ConfigPanel = ({
  panel,
  cfg,
  setC,
  saveCfg,
  savingCfg,
  embedModels,
  llmModels,
  llmState,
  loadingLlm,
}) => {
  if (!cfg) return null;

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

      {/* CHUNKING */}
      {panel === "chunk" && (
        <>
          <label className="rag-cfg-label">Strategy</label>
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
          <label className="rag-cfg-label">Chunk size · {cfg.chunk_size}</label>
          <input
            type="range"
            min="256"
            max="1024"
            step="1"
            value={cfg.chunk_size}
            onChange={(e) => setC("chunk_size", e.target.value)}
            className="rag-cfg-range"
          />
          <label className="rag-cfg-label">Overlap · {cfg.chunk_overlap}</label>
          <input
            type="range"
            min="0"
            max="200"
            step="1"
            value={cfg.chunk_overlap}
            onChange={(e) => setC("chunk_overlap", e.target.value)}
            className="rag-cfg-range"
          />
        </>
      )}

      {/* EMBEDDING */}
      {panel === "embed" && (
        <>
          <label className="rag-cfg-label">Embedding model</label>
          <div className="rag-cfg-models">
            {embedModels.map((m) => (
              <label
                key={m.id}
                className={`rag-cfg-model ${cfg.embedding_model === m.id ? "active" : ""} ${!m.available ? "disabled" : ""}`}
              >
                <input
                  type="radio"
                  name="embed"
                  checked={cfg.embedding_model === m.id}
                  disabled={!m.available}
                  onChange={() => {
                    setC("embedding_model", m.id);
                    setC("embedding_provider", m.provider);
                  }}
                />
                <div>
                  <div className="rag-cfg-model-n">
                    {m.label} · {m.dim}d
                  </div>
                  <div className="rag-cfg-model-note">{m.note}</div>
                </div>
              </label>
            ))}
            {embedModels.length === 0 && (
              <div className="rag-cfg-hint">Loading…</div>
            )}
          </div>
          <div className="rag-cfg-warn">
            Changing the dimension re-embeds all chunks
          </div>
        </>
      )}

      {/* LLM */}
      {panel === "llm" && (
        <>
          <label className="rag-cfg-label">Provider</label>
          <select
            className="rag-cfg-select"
            value={cfg.llm_provider}
            onChange={(e) => {
              setC("llm_provider", e.target.value);
              setC("llm_model", "");
            }}
          >
            <option value="GROQ">Groq (free)</option>
            <option value="OLLAMA">Ollama (local)</option>
            <option value="OPENAI">OpenAI (paid)</option>
          </select>
          <label className="rag-cfg-label">Model</label>
          {loadingLlm ? (
            <div className="rag-cfg-hint">Loading…</div>
          ) : !llmState.available ? (
            <div className="rag-cfg-warn">
              {llmState.error || "Unavailable"}
            </div>
          ) : (
            <select
              className="rag-cfg-select"
              value={cfg.llm_model}
              onChange={(e) => setC("llm_model", e.target.value)}
            >
              <option value="">Select…</option>
              {llmModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          )}
          <label className="rag-cfg-label">
            Temperature · {cfg.llm_temperature}
          </label>
          <input
            type="range"
            min="0"
            max="2"
            step="0.1"
            value={cfg.llm_temperature}
            onChange={(e) => setC("llm_temperature", e.target.value)}
            className="rag-cfg-range"
          />
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
