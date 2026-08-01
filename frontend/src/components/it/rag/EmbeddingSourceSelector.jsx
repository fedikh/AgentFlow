import React, { useEffect, useState } from "react";
import {
  listProviders,
  getProviderModels,
} from "../../../services/providersApi";
import CustomDropdown from "./CustomDropdown";
import SavedKeyInput from "./SavedKeyInput";

/**
 * EmbeddingSourceSelector — Batch 6. Mirror of LLMSourceSelector, for
 * embeddings. ALL three sources now pick their model through the same
 * CustomDropdown (the local list shows each model's note + dim inline):
 *   Local   → sentence-transformers / Ollama models (free, BGE-M3 default)
 *   Company → an embedding-capable provider the admin deployed (OpenAI / Voyage)
 *   Own key → the IT supplies a key for OPENAI or VOYAGE
 *
 * A single OpenAI admin key is dual-capable: it appears here for embeddings
 * AND in the LLM picker, so admins add OpenAI once.
 *
 * DIMENSIONS: every model runs at its NATIVE dimension (384/768/1024/1536/
 * 3072…) — vectors are stored in per-dimension buckets, so nothing is padded
 * or truncated anymore. Switching model/source still requires re-indexing.
 */
const OWN_FAMILIES = ["OPENAI", "VOYAGE", "GOOGLE"];

/* Curated per-family embedding models (mirror of the backend catalog),
 * each at its DEFAULT output dimension. */
const OWN_MODELS = {
  OPENAI: [
    { id: "text-embedding-3-small", label: "text-embedding-3-small (1536)" },
    { id: "text-embedding-3-large", label: "text-embedding-3-large (3072)" },
  ],
  VOYAGE: [
    { id: "voyage-4-large", label: "voyage-4-large (1024)" },
    { id: "voyage-4", label: "voyage-4 (1024)" },
    { id: "voyage-4-lite", label: "voyage-4-lite (1024)" },
    { id: "voyage-4-nano", label: "voyage-4-nano (1024)" },
    { id: "voyage-context-4", label: "voyage-context-4 (1024, contextual)" },
    { id: "voyage-3.5", label: "voyage-3.5 (1024)" },
    { id: "voyage-3.5-lite", label: "voyage-3.5-lite (1024)" },
    { id: "voyage-3-large", label: "voyage-3-large (1024)" },
    { id: "voyage-multimodal-3.5", label: "Voyage Multimodal 3.5 (1024)" },
    { id: "voyage-code-3", label: "voyage-code-3 (1024, code)" },
    { id: "voyage-finance-2", label: "voyage-finance-2 (1024, finance)" },
    { id: "voyage-law-2", label: "voyage-law-2 (1024, legal)" },
  ],
  GOOGLE: [
    { id: "gemini-embedding-002", label: "Gemini Embedding 2 (3072)" },
    { id: "gemini-embedding-001", label: "Gemini Embedding 1 (3072)" },
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

  const localModels = embedModels.filter(
    (m) => m.provider === "LOCAL" || m.provider === "OLLAMA",
  );
  const selectedLocal = localModels.find((m) => m.id === value.embedding_model);

  /* Brand logo for a local model: Ollama models keep the Ollama logo; the
   * in-process ones get their own brand (BGE-M3 → BAAI, Jina v3 → Jina). */
  const localLogoFamily = (m) => {
    if (m.provider === "OLLAMA") return "OLLAMA";
    const id = (m.id || "").toLowerCase();
    if (id.includes("bge")) return "BAAI";
    if (id.includes("jina")) return "JINA";
    return "LOCAL";
  };

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

      {/* LOCAL — same dropdown as the other modes (logo + note per model) */}
      {mode === "local" && (
        <>
          <label className="rag-cfg-label">Model</label>
          {localModels.length === 0 ? (
            <div className="rag-cfg-hint">Loading…</div>
          ) : (
            <CustomDropdown
              showLogo
              options={localModels.map((m) => ({
                value: m.id,
                label: `${m.label} (${m.dim}d)`,
                family: localLogoFamily(m),
                sub: m.note,
                tag: m.provider === "OLLAMA" ? "Ollama" : "Local",
              }))}
              value={value.embedding_model || ""}
              onChange={(id) => {
                const m = localModels.find((x) => x.id === id);
                onChange({
                  embedding_model: id,
                  embedding_provider: m?.provider || "LOCAL", // LOCAL or OLLAMA
                  embedding_provider_id: null,
                  embedding_api_key: "",
                });
              }}
              placeholder={`Select a model… (${localModels.length})`}
            />
          )}
          {selectedLocal && (
            <div className="rag-cfg-hint">
              {selectedLocal.note} · {selectedLocal.dim}d
            </div>
          )}
          <div className="rag-cfg-hint">
            Every model runs at its <strong>default dimension</strong> — smaller
            dims (384/768d) are the fastest and most CPU-friendly, larger dims
            (1024/2560d) the highest quality.
            <strong> BGE-M3</strong> (1024d, multilingual) is the recommended
            default for French documents. No key, no data leaves the machine.
            <strong> Ollama</strong> models run on your local Ollama daemon
            (<code>ollama serve</code> + <code>ollama pull &lt;model&gt;</code>).
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
          <SavedKeyInput
            masked={value.embedding_api_key_masked}
            hasKey={hasOwnKey}
            value={value.embedding_api_key || ""}
            onChange={(v) => onChange({ embedding_api_key: v })}
            placeholder={KEY_PLACEHOLDER[value.embedding_provider] || "sk-…"}
          />
          <div className="rag-cfg-hint">Stored encrypted. Only a masked preview is ever shown.</div>
        </>
      )}

      <div className="rag-cfg-warn" style={{ marginTop: 10 }}>
        Each model stores vectors at its own native dimension. Changing the
        embedding source or model requires re-indexing your documents for it
        to take effect (the platform flags this automatically).
      </div>
    </>
  );
};

export default EmbeddingSourceSelector;
