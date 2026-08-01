import React, { useEffect, useState, useCallback } from "react";
import {
  listProviders,
  getProviderModels,
} from "../../../services/providersApi";
import { getLLMModels } from "../../../services/ragApi";
import CustomDropdown from "./CustomDropdown";
import ProviderLogo from "../../ProviderLogo";
import SavedKeyInput from "./SavedKeyInput";

/**
 * LLMSourceSelector — Batch 8. Three finalized sources:
 *   Local   → Ollama, models listed LIVE from the local daemon (no key).
 *   Company → an LLM provider the admin deployed.
 *   Own key → the IT's own key for OPENAI / ANTHROPIC / GOOGLE / GROQ / CUSTOM
 *             (CUSTOM = any OpenAI-compatible base_url, e.g. OpenRouter).
 */
const FAMILIES = ["OPENAI", "ANTHROPIC", "GOOGLE", "GROQ", "CUSTOM"];

const MODEL_PLACEHOLDER = {
  OPENAI: "gpt-4o-mini",
  ANTHROPIC: "claude-haiku-4-5",
  GOOGLE: "gemini-2.5-flash",
  GROQ: "llama-3.3-70b-versatile",
  CUSTOM: "e.g. anthropic/claude-3.5-sonnet",
};

const LLMSourceSelector = ({ value, onChange, hasOwnKey }) => {
  const [providers, setProviders] = useState([]);
  const [companyModels, setCompanyModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelError, setModelError] = useState("");

  // Local Ollama models (live from the daemon)
  const [ollamaModels, setOllamaModels] = useState([]);
  const [loadingOllama, setLoadingOllama] = useState(false);
  const [ollamaError, setOllamaError] = useState("");

  const [mode, setMode] = useState(
    value.llm_provider_id ? "company" : hasOwnKey ? "own" : "local",
  );

  useEffect(() => {
    listProviders()
      // A provider shows up here if its family can serve LLM — so a dual-capable
      // OpenAI key added as EMBEDDING still appears for LLM, and vice versa.
      .then((all) =>
        setProviders(
          all.filter((p) =>
            p.capabilities
              ? p.capabilities.includes("LLM")
              : p.kind === "LLM",
          ),
        ),
      )
      .catch(() => setProviders([]));
  }, []);

  useEffect(() => {
    if (mode !== "company" || !value.llm_provider_id) {
      setCompanyModels([]);
      setModelError("");
      return;
    }
    setLoadingModels(true);
    setModelError("");
    getProviderModels(value.llm_provider_id, "LLM")
      .then((r) => setCompanyModels(r.models || []))
      .catch((e) => {
        setCompanyModels([]);
        setModelError(e.message || "Could not load models");
      })
      .finally(() => setLoadingModels(false));
  }, [mode, value.llm_provider_id]);

  // Live Ollama model list for the Local source. Extracted so a Retry button
  // can re-run it without reloading the page (the daemon may come up later).
  const loadOllama = useCallback(() => {
    setLoadingOllama(true);
    setOllamaError("");
    getLLMModels("OLLAMA")
      .then((r) => {
        setOllamaModels(r.models || []);
        // available=false → the backend reached us but Ollama itself is down.
        if (!r.available)
          setOllamaError(
            r.error || "Ollama is not running. Start it (`ollama serve`).",
          );
      })
      .catch(() => {
        // The request never reached the backend (server down / wrong URL).
        setOllamaModels([]);
        setOllamaError(
          "Couldn't reach the AgentFlow server to list local models. Is the backend running?",
        );
      })
      .finally(() => setLoadingOllama(false));
  }, []);

  useEffect(() => {
    if (mode === "local") loadOllama();
  }, [mode, loadOllama]);

  const pick = (next) => {
    setMode(next);
    // Always clear the model on a source switch so a model from the previous
    // source (e.g. an Ollama model left over when moving to a Company OpenAI
    // provider) can never mismatch the new source.
    if (next === "local") {
      onChange({
        llm_provider: "OLLAMA",
        llm_provider_id: null,
        llm_api_key: "",
        llm_model: "",
      });
    } else if (next === "company") {
      onChange({ llm_provider_id: providers[0]?.id || null, llm_model: "" });
    } else if (next === "own") {
      const fam = FAMILIES.includes(value.llm_provider)
        ? value.llm_provider
        : "OPENAI";
      onChange({ llm_provider_id: null, llm_provider: fam, llm_model: "" });
    }
  };

  const ownFamily = FAMILIES.includes(value.llm_provider)
    ? value.llm_provider
    : "OPENAI";

  return (
    <>
      <label className="rag-cfg-label">LLM source</label>
      <div className="rag-cfg-cards">
        {[
          { k: "local", n: "Local", d: "Ollama, free" },
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

      {/* LOCAL — Ollama live models */}
      {mode === "local" && (
        <>
          <label
            className="rag-cfg-label"
            style={{ display: "flex", alignItems: "center", gap: 6 }}
          >
            <ProviderLogo family="OLLAMA" size={16} /> Ollama model
          </label>
          {loadingOllama ? (
            <div className="rag-cfg-hint">Loading installed models…</div>
          ) : ollamaModels.length > 0 ? (
            <CustomDropdown
              options={ollamaModels.map((m) => ({
                value: m.id,
                label: m.label || m.id,
              }))}
              value={value.llm_model || ""}
              onChange={(id) => onChange({ llm_model: id })}
              placeholder={`Select a model… (${ollamaModels.length})`}
            />
          ) : (
            <div className="rag-cfg-warn">
              {ollamaError ||
                "No local models found. Pull one with `ollama pull llama3.1:8b`."}
              <button
                type="button"
                className="rag-btn rag-btn-sm"
                style={{ marginLeft: 8 }}
                onClick={loadOllama}
                disabled={loadingOllama}
              >
                {loadingOllama ? "Checking…" : "Retry"}
              </button>
            </div>
          )}
          <div className="rag-cfg-hint">
            Runs fully locally via Ollama — no key, no data leaves the machine.
            Models are listed live from <code>localhost:11434</code>.
          </div>
        </>
      )}

      {/* COMPANY */}
      {mode === "company" && (
        <>
          {providers.length === 0 ? (
            <div className="rag-cfg-hint">
              No company LLM providers yet. Ask your admin to add one in “API
              Providers”, or use your own key.
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
                value={value.llm_provider_id || ""}
                onChange={(id) =>
                  onChange({ llm_provider_id: id, llm_model: "" })
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
                  value={value.llm_model || ""}
                  onChange={(id) => onChange({ llm_model: id })}
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
            options={FAMILIES.map((f) => ({
              value: f,
              label: f === "CUSTOM" ? "CUSTOM (OpenAI-compatible)" : f,
              family: f,
            }))}
            value={ownFamily}
            onChange={(f) => onChange({ llm_provider: f, llm_model: "" })}
            placeholder="Select a provider…"
          />

          <label className="rag-cfg-label">Model</label>
          <input
            className="rag-cfg-select"
            value={value.llm_model || ""}
            onChange={(e) => onChange({ llm_model: e.target.value })}
            placeholder={MODEL_PLACEHOLDER[ownFamily] || "model name"}
          />

          <label className="rag-cfg-label">
            API key{ownFamily === "CUSTOM" ? " (optional)" : ""}
          </label>
          <SavedKeyInput
            masked={value.llm_api_key_masked}
            hasKey={hasOwnKey}
            value={value.llm_api_key || ""}
            onChange={(v) => onChange({ llm_api_key: v })}
            placeholder="sk-..."
          />
          <div className="rag-cfg-hint">
            Stored encrypted. Only a masked preview is ever shown.
          </div>

          <label className="rag-cfg-label">
            Base URL{ownFamily === "CUSTOM" ? " (required)" : " (optional)"}
          </label>
          <input
            className="rag-cfg-select"
            value={value.llm_base_url || ""}
            onChange={(e) => onChange({ llm_base_url: e.target.value })}
            placeholder={
              ownFamily === "CUSTOM"
                ? "https://openrouter.ai/api/v1"
                : "For custom endpoints"
            }
          />
          {ownFamily === "CUSTOM" && (
            <div className="rag-cfg-hint">
              CUSTOM routes to any OpenAI-compatible endpoint (e.g. OpenRouter,
              vLLM, LM Studio). Set the base URL and, if the endpoint needs one,
              a key.
            </div>
          )}
        </>
      )}
    </>
  );
};

export default LLMSourceSelector;
