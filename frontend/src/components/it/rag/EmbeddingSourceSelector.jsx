import React, { useEffect, useState } from "react";
import {
  listProviders,
  getProviderModels,
} from "../../../services/providersApi";
import CustomDropdown from "./CustomDropdown";

/**
 * EmbeddingSourceSelector — Batch 6. Mirror of LLMSourceSelector, for
 * embeddings, now with the same logo dropdowns. Three sources:
 *   Local   → BGE-M3 (free, 1024 dims, the default)
 *   Company → an embedding-capable provider the admin deployed (OpenAI / Voyage)
 *   Own key → the IT supplies a key for OPENAI or VOYAGE
 *
 * A single OpenAI admin key is dual-capable: it appears here for embeddings
 * AND in the LLM picker, so admins add OpenAI once.
 *
 * pgvector is fixed at 1024 dims. Every model offered here outputs 1024, so
 * switching source is safe — but re-indexing is still required for embeddings
 * to actually be regenerated with the new provider (flagged below).
 */
const OWN_FAMILIES = ["OPENAI", "VOYAGE"];

const EmbeddingSourceSelector = ({ value, onChange, hasOwnKey, embedModels = [] }) => {
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
      // Show any provider whose family can serve EMBEDDING — this includes a
      // dual-capable OpenAI key even if it was registered as an LLM provider.
      .then((all) =>
        setProviders(
          all.filter((p) =>
            p.capabilities
              ? p.capabilities.includes("EMBEDDING")
              : p.kind === "EMBEDDING",
          ),
        ),
      )
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
    getProviderModels(value.embedding_provider_id, "EMBEDDING")
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
      onChange({ embedding_provider_id: providers[0]?.id || null, embedding_model: "" });
    } else if (next === "own") {
      onChange({
        embedding_provider_id: null,
        embedding_provider: "OPENAI",
        embedding_model: "",
      });
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
        <>
          <label className="rag-cfg-label">Local embedding model</label>
          <div className="rag-cfg-models">
            {embedModels
              .filter((m) => m.provider === "LOCAL")
              .map((m) => (
                <label
                  key={m.id}
                  className={`rag-cfg-model ${value.embedding_model === m.id ? "active" : ""}`}
                >
                  <input
                    type="radio"
                    name="embed"
                    checked={value.embedding_model === m.id}
                    onChange={() =>
                      onChange({
                        embedding_model: m.id,
                        embedding_provider: "LOCAL",
                        embedding_provider_id: null,
                        embedding_api_key: "",
                      })
                    }
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
          <div className="rag-cfg-hint">
            BGE-M3 (1024d) is the recommended local default — it matches the
            pgvector column, so no re-indexing is needed. No key, no data leaves
            the machine.
          </div>
        </>
      )}

      {/* COMPANY */}
      {mode === "company" && (
        <>
          {providers.length === 0 ? (
            <div className="rag-cfg-hint">
              No company embedding providers yet. Ask your admin to add an
              OpenAI or Voyage provider in “API Providers”, or use your own key.
            </div>
          ) : (
            <>
              <label className="rag-cfg-label">Provider</label>
              <CustomDropdown
                showLogo
                options={providers.map((p) => ({
                  value: p.id,
                  label: `${p.name} (${p.family})`,
                  family: p.family,
                }))}
                value={value.embedding_provider_id || ""}
                onChange={(id) =>
                  onChange({ embedding_provider_id: id, embedding_model: "" })
                }
                placeholder="Select a provider…"
              />

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
                <CustomDropdown
                  options={companyModels.map((m) => ({
                    value: m.id,
                    label: m.label,
                  }))}
                  value={value.embedding_model || ""}
                  onChange={(id) => onChange({ embedding_model: id })}
                  placeholder={`Select a model… (${companyModels.length})`}
                />
              )}
            </>
          )}
        </>
      )}

      {/* OWN KEY */}
      {mode === "own" && (
        <>
          <label className="rag-cfg-label">Provider</label>
          <CustomDropdown
            showLogo
            options={OWN_FAMILIES.map((f) => ({
              value: f,
              label: f,
              family: f,
            }))}
            value={value.embedding_provider || "OPENAI"}
            onChange={(f) =>
              onChange({ embedding_provider: f, embedding_model: "" })
            }
            placeholder="Select a provider…"
          />

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
