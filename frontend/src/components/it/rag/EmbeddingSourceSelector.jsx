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
const OWN_FAMILIES = ["OPENAI", "VOYAGE", "GOOGLE"];

/* Curated per-family embedding models (mirror of the backend catalog).
 * Non-1024 native dims (Gemini) are fitted to the 1024 pgvector column. */
const OWN_MODELS = {
  OPENAI: [
    { id: "text-embedding-3-small", label: "text-embedding-3-small (1024)" },
    { id: "text-embedding-3-large", label: "text-embedding-3-large (1024)" },
  ],
  VOYAGE: [
    { id: "voyage-3.5", label: "voyage-3.5 (1024)" },
    { id: "voyage-3.5-lite", label: "voyage-3.5-lite (1024)" },
    { id: "voyage-3-large", label: "voyage-3-large (1024)" },
    { id: "voyage-multimodal-3.5", label: "Voyage Multimodal 3.5 (1024)" },
    { id: "voyage-code-3", label: "voyage-code-3 (code)" },
    { id: "voyage-finance-2", label: "voyage-finance-2 (finance)" },
    { id: "voyage-law-2", label: "voyage-law-2 (legal)" },
  ],
  GOOGLE: [
    { id: "gemini-embedding-002", label: "Gemini Embedding 2 (fit 1024)" },
    { id: "gemini-embedding-001", label: "Gemini Embedding 1 (fit 1024)" },
  ],
};

const KEY_PLACEHOLDER = {
  OPENAI: "sk-…",
  VOYAGE: "pa-…",
  GOOGLE: "AIza…",
};

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
      const first = providers[0];
      onChange({
        embedding_provider_id: first?.id || null,
        embedding_model: "",
        ...(first?.family ? { embedding_provider: first.family } : {}),
      });
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
          <label className="rag-cfg-label">Local &amp; Ollama embedding models</label>
          <div className="rag-cfg-models">
            {embedModels
              .filter((m) => m.provider === "LOCAL" || m.provider === "OLLAMA")
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
                        embedding_provider: m.provider,   // LOCAL or OLLAMA
                        embedding_provider_id: null,
                        embedding_api_key: "",
                      })
                    }
                  />
                  <div>
                    <div className="rag-cfg-model-n">
                      {m.label} · {m.dim}d
                      {m.provider === "OLLAMA" && (
                        <span className="rag-config-tag" style={{ marginLeft: 6 }}>Ollama</span>
                      )}
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
            the machine. <strong>Ollama</strong> models run on your local Ollama
            daemon (<code>ollama serve</code>); vectors are fit to 1024 —
            <code>mxbai-embed-large</code> is a native 1024 match.
          </div>
        </>
      )}

      {/* COMPANY */}
      {mode === "company" && (
        <>
          {providers.length === 0 ? (
            <div className="rag-cfg-hint">
              No company embedding providers yet. Ask your admin to add an
              OpenAI, Voyage or Google (Gemini) provider in “API Providers”,
              or use your own key.
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
                onChange={(id) => {
                  // Also store the provider's FAMILY so embedding_provider
                  // reflects the real source (GOOGLE/OPENAI/VOYAGE), not a
                  // stale "LOCAL" from a previous mode.
                  const fam = providers.find((p) => p.id === id)?.family;
                  onChange({
                    embedding_provider_id: id,
                    embedding_model: "",
                    ...(fam ? { embedding_provider: fam } : {}),
                  });
                }}
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
          <CustomDropdown
            options={(OWN_MODELS[value.embedding_provider] || OWN_MODELS.OPENAI).map(
              (m) => ({ value: m.id, label: m.label }),
            )}
            value={value.embedding_model || ""}
            onChange={(id) => onChange({ embedding_model: id })}
            placeholder="Select a model…"
          />

          <label className="rag-cfg-label">API key</label>
          <input
            className="rag-cfg-select"
            type="password"
            onChange={(e) => onChange({ embedding_api_key: e.target.value })}
            placeholder={
              hasOwnKey
                ? "Key saved — type to replace"
                : KEY_PLACEHOLDER[value.embedding_provider] || "sk-…"
            }
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
