import React, { useEffect, useState } from "react";
import {
  listProviders,
  getProviderModels,
} from "../../../services/providersApi";
import ProviderLogo from "../../ProviderLogo";

/**
 * LLMSourceSelector — Local / Company / Own key.
 * Company mode fetches the provider's models LIVE from its API.
 * Uses rag-cfg-* classes to match ConfigPanel.
 */
const FAMILIES = ["GROQ", "OPENAI", "ANTHROPIC", "GOOGLE", "OLLAMA", "CUSTOM"];

const LLMSourceSelector = ({ value, onChange, hasOwnKey }) => {
  const [providers, setProviders] = useState([]);
  const [companyModels, setCompanyModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelError, setModelError] = useState("");
  const [mode, setMode] = useState(
    value.llm_provider_id ? "company" : hasOwnKey ? "own" : "local",
  );

  useEffect(() => {
    listProviders()
      .then((all) => setProviders(all.filter((p) => p.kind === "LLM")))
      .catch(() => setProviders([]));
  }, []);

  // Fetch live models whenever a company provider is selected
  useEffect(() => {
    if (mode !== "company" || !value.llm_provider_id) {
      setCompanyModels([]);
      setModelError("");
      return;
    }
    setLoadingModels(true);
    setModelError("");
    getProviderModels(value.llm_provider_id)
      .then((r) => setCompanyModels(r.models || []))
      .catch((e) => {
        setCompanyModels([]);
        setModelError(e.message || "Could not load models");
      })
      .finally(() => setLoadingModels(false));
  }, [mode, value.llm_provider_id]);

  const pick = (next) => {
    setMode(next);
    if (next === "local") {
      onChange({
        llm_provider: "GROQ",
        llm_provider_id: null,
        llm_api_key: "",
      });
    } else if (next === "company") {
      onChange({ llm_provider_id: providers[0]?.id || null });
    } else if (next === "own") {
      onChange({ llm_provider_id: null });
    }
  };

  return (
    <>
      <label className="rag-cfg-label">LLM source</label>
      <div className="rag-cfg-cards">
        {[
          { k: "local", n: "Local", d: "Groq, free" },
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
          Uses the free local model (Groq Llama). No key needed — a good
          baseline to compare paid providers against.
        </div>
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
              <div className="rag-cfg-provider-list">
                {providers.map((p) => (
                  <button
                    key={p.id}
                    className={`rag-cfg-provider ${value.llm_provider_id === p.id ? "active" : ""}`}
                    onClick={() =>
                      onChange({ llm_provider_id: p.id, llm_model: "" })
                    }
                  >
                    <ProviderLogo family={p.family} size={16} />
                    <span>{p.name}</span>
                    <span className="rag-cfg-provider-fam">{p.family}</span>
                  </button>
                ))}
              </div>

              <label className="rag-cfg-label">Model</label>
              {loadingModels ? (
                <div className="rag-cfg-hint">
                  Loading models from the provider…
                </div>
              ) : modelError ? (
                <div className="rag-cfg-warn">{modelError}</div>
              ) : companyModels.length === 0 ? (
                <div className="rag-cfg-hint">
                  Select a provider to load its models.
                </div>
              ) : (
                <select
                  className="rag-cfg-select"
                  value={value.llm_model || ""}
                  onChange={(e) => onChange({ llm_model: e.target.value })}
                >
                  <option value="">
                    Select a model… ({companyModels.length} available)
                  </option>
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
            value={value.llm_provider || "OPENAI"}
            onChange={(e) => onChange({ llm_provider: e.target.value })}
          >
            {FAMILIES.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>

          <label className="rag-cfg-label">Model</label>
          <input
            className="rag-cfg-select"
            value={value.llm_model || ""}
            onChange={(e) => onChange({ llm_model: e.target.value })}
            placeholder="gpt-4o-mini"
          />

          <label className="rag-cfg-label">API key</label>
          <input
            className="rag-cfg-select"
            type="password"
            onChange={(e) => onChange({ llm_api_key: e.target.value })}
            placeholder={hasOwnKey ? "Key saved — type to replace" : "sk-..."}
          />
          <div className="rag-cfg-hint">
            Stored encrypted. Never shown again.
          </div>

          <label className="rag-cfg-label">Base URL (optional)</label>
          <input
            className="rag-cfg-select"
            value={value.llm_base_url || ""}
            onChange={(e) => onChange({ llm_base_url: e.target.value })}
            placeholder="For custom endpoints"
          />
        </>
      )}
    </>
  );
};

export default LLMSourceSelector;
