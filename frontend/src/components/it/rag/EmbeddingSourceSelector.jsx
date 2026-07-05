import React, { useEffect, useState } from "react";
import {
  listProviders,
  getProviderModels,
} from "../../../services/providersApi";

/**
 * EmbeddingSourceSelector — Batch 6. Mirror of LLMSourceSelector, for
 * embeddings. Three sources:
 *   Local   → BGE-M3 (free, 1024 dims, the default)
 *   Company → an EMBEDDING provider the admin deployed (OpenAI / Voyage)
 *   Own key → the IT supplies a key for OPENAI or VOYAGE
 *
 * pgvector is fixed at 1024 dims. Every model offered here outputs 1024, so
 * switching source is safe — but re-indexing is still required for embeddings
 * to actually be regenerated with the new provider (flagged below).
 */
const OWN_FAMILIES = ["OPENAI", "VOYAGE"];

const EmbeddingSourceSelector = ({ value, onChange, hasOwnKey }) => {
  const [providers, setProviders] = useState([]);
  const [companyModels, setCompanyModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelError, setModelError] = useState("");
  const [mode, setMode] = useState(
    value.embedding_provider_id
      ? "company"
      : hasOwnKey
        ? "own"
        : "local",
  );

  useEffect(() => {
    listProviders()
      .then((all) => setProviders(all.filter((p) => p.kind === "EMBEDDING")))
      .catch(() => setProviders([]));
  }, []);

  useEffect(() => {
    if (mode !== "company" || !value.embedding_provider_id) {
      setCompanyModels([]);
      setModelError("");
      return;
    }
    setLoadingModels(true);
    setModelError("");
    getProviderModels(value.embedding_provider_id)
      .then((r) => setCompanyModels(r.models || []))
      .catch((e) => {
        setCompanyModels([]);
        setModelError(e.message || "Could not load models");
      })
      .finally(() => setLoadingModels(false));
  }, [mode, value.embedding_provider_id]);

  const pick = (next) => {
    setMode(next);
    if (next === "local") {
      onChange({
        embedding_provider: "LOCAL",
        embedding_model: "BAAI/bge-m3",
        embedding_provider_id: null,
        embedding_api_key: "",
      });
    } else if (next === "company") {
      onChange({ embedding_provider_id: providers[0]?.id || null });
    } else if (next === "own") {
      onChange({ embedding_provider_id: null, embedding_provider: "OPENAI" });
    }
  };

  return (
    <>
      <label className="rag-cfg-label">Embedding source</label>
      <div className="rag-cfg-cards">
        {[
          { k: "local", n: "Local", d: "BGE-M3, free" },
          { k: "company", n: "Company", d: "Admin provider" },
          { k: "own", n: "My key", d: "Your own API key" },
        ].map((m) => (
          <button
            key={m.k}
            className={`rag-cfg-card ${mode === m.k ? "active" : ""}`}
            onClick={() => pick(m.k)}
          >
            <div className="rag-cfg-card-n">{m.n}</div>
            <div className="rag-cfg-card-d">{m.d}</div>
          </button>
        ))}
      </div>

      {/* LOCAL */}
      {mode === "local" && (
        <div className="rag-cfg-hint">
          Uses the free local BGE-M3 model (1024 dims). No key needed — a good
          baseline to compare paid providers against.
        </div>
      )}

      {/* COMPANY */}
      {mode === "company" && (
        <>
          {providers.length === 0 ? (
            <div className="rag-cfg-hint">
              No company embedding providers yet. Ask your admin to add an
              OpenAI or Voyage provider (type EMBEDDING) in “API Providers”, or
              use your own key.
            </div>
          ) : (
            <>
              <label className="rag-cfg-label">Provider</label>
              <select
                className="rag-cfg-select"
                value={value.embedding_provider_id || ""}
                onChange={(e) =>
                  onChange({
                    embedding_provider_id: e.target.value,
                    embedding_model: "",
                  })
                }
              >
                <option value="">Select a provider…</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.family})
                  </option>
                ))}
              </select>

              <label className="rag-cfg-label">Model</label>
              {loadingModels ? (
                <div className="rag-cfg-hint">Loading models…</div>
              ) : modelError ? (
                <div className="rag-cfg-warn">{modelError}</div>
              ) : companyModels.length === 0 ? (
                <div className="rag-cfg-hint">
                  Select a provider to load its models.
                </div>
              ) : (
                <select
                  className="rag-cfg-select"
                  value={value.embedding_model || ""}
                  onChange={(e) => onChange({ embedding_model: e.target.value })}
                >
                  <option value="">Select a model…</option>
                  {companyModels.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </select>
              )}
            </>
          )}
        </>
      )}

      {/* OWN KEY */}
      {mode === "own" && (
        <>
          <label className="rag-cfg-label">Provider</label>
          <select
            className="rag-cfg-select"
            value={value.embedding_provider || "OPENAI"}
            onChange={(e) =>
              onChange({ embedding_provider: e.target.value, embedding_model: "" })
            }
          >
            {OWN_FAMILIES.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>

          <label className="rag-cfg-label">Model</label>
          <input
            className="rag-cfg-select"
            value={value.embedding_model || ""}
            onChange={(e) => onChange({ embedding_model: e.target.value })}
            placeholder={
              value.embedding_provider === "VOYAGE"
                ? "voyage-3.5"
                : "text-embedding-3-small"
            }
          />

          <label className="rag-cfg-label">API key</label>
          <input
            className="rag-cfg-select"
            type="password"
            onChange={(e) => onChange({ embedding_api_key: e.target.value })}
            placeholder={hasOwnKey ? "Key saved — type to replace" : "sk-… / pa-…"}
          />
          <div className="rag-cfg-hint">Stored encrypted. Never shown again.</div>
        </>
      )}

      <div className="rag-cfg-warn" style={{ marginTop: 10 }}>
        pgvector is fixed at 1024 dimensions. Changing the embedding source or
        model requires re-indexing your documents for it to take effect.
      </div>
    </>
  );
};

export default EmbeddingSourceSelector;
