import React, { useCallback, useEffect, useState } from "react";
import { listProviders, getProviderModels } from "../../../services/providersApi";
import { getLLMModels, updateSpace } from "../../../services/ragApi";
import CustomDropdown from "./CustomDropdown";
import ProviderLogo from "../../ProviderLogo";
import SavedKeyInput from "./SavedKeyInput";

/**
 * JudgeSelector — the evaluation judge LLM, configured EXACTLY like the LLM
 * source selector (same three cards, same logo dropdowns):
 *
 *   Local   → Ollama, models listed LIVE from the daemon (free, no key)
 *   Company → an admin-deployed LLM provider + its model catalog
 *   My key  → own key (encrypted per space: judge_api_key_enc) + family/model
 *
 * The judge grades the RAG's answers, so it should be DIFFERENT from the
 * space's own LLM — a model grading itself inflates scores. Saved in
 * space.eval_params {judge_source, judge_provider_id, judge_family,
 * judge_model} via its own Save button.
 */
const FAMILIES = ["OPENAI", "ANTHROPIC", "GOOGLE", "GROQ"];
const KEY_PLACEHOLDER = { OPENAI: "sk-…", ANTHROPIC: "sk-ant-…", GOOGLE: "AIza…", GROQ: "gsk_…" };

const JudgeSelector = ({ spaceId, space, onError }) => {
  const ep = space?.eval_params || {};
  const [mode, setMode] = useState(ep.judge_source || "company");
  const [providerId, setProviderId] = useState(ep.judge_provider_id || "");
  const [family, setFamily] = useState(ep.judge_family || "OPENAI");
  const [model, setModel] = useState(ep.judge_model || "");
  const [apiKey, setApiKey] = useState("");
  const [saved, setSaved] = useState(true);
  const [saving, setSaving] = useState(false);

  const [providers, setProviders] = useState([]);
  const [companyModels, setCompanyModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [ollamaModels, setOllamaModels] = useState([]);
  const [loadingOllama, setLoadingOllama] = useState(false);
  const [ollamaError, setOllamaError] = useState("");

  const dirty = (fn) => (v) => { fn(v); setSaved(false); };

  useEffect(() => {
    listProviders()
      .then((all) => setProviders(all.filter((p) =>
        p.capabilities ? p.capabilities.includes("LLM") : p.kind === "LLM")))
      .catch(() => setProviders([]));
  }, []);

  useEffect(() => {
    if (mode !== "company" || !providerId) { setCompanyModels([]); return; }
    setLoadingModels(true);
    getProviderModels(providerId, "LLM")
      .then((r) => setCompanyModels(r.models || []))
      .catch(() => setCompanyModels([]))
      .finally(() => setLoadingModels(false));
  }, [mode, providerId]);

  const loadOllama = useCallback(() => {
    setLoadingOllama(true);
    setOllamaError("");
    getLLMModels("OLLAMA")
      .then((r) => {
        setOllamaModels(r.models || []);
        if (!r.available)
          setOllamaError(r.error || "Ollama is not running. Start it (`ollama serve`).");
      })
      .catch(() => {
        setOllamaModels([]);
        setOllamaError("Couldn't reach the server to list local models.");
      })
      .finally(() => setLoadingOllama(false));
  }, []);
  useEffect(() => { if (mode === "local") loadOllama(); }, [mode, loadOllama]);

  const pick = (next) => {
    setMode(next);
    setModel("");                 // never carry a model across sources
    if (next === "company") setProviderId(providers[0]?.id || "");
    setSaved(false);
  };

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        eval_params: {
          judge_source: mode,
          judge_provider_id: mode === "company" ? providerId || undefined : undefined,
          judge_family: mode === "own" ? family : undefined,
          judge_model: model || undefined,
        },
      };
      if (apiKey) payload.judge_api_key = apiKey;
      await updateSpace(spaceId, payload);
      setApiKey("");
      setSaved(true);
    } catch (e) { onError?.(e.message); }
    finally { setSaving(false); }
  };

  const ragLLM = space?.llm_model || space?.llm_provider || "";
  const sameAsRag = mode === "company" && providerId &&
    providerId === space?.llm_provider_id && (!model || model === space?.llm_model);

  return (
    <>
      <label className="rag-cfg-label">Judge source</label>
      <div className="rag-cfg-cards">
        {[
          { k: "local", n: "Local", d: "Ollama, free" },
          { k: "company", n: "Company", d: "Admin provider" },
          { k: "own", n: "My key", d: "Your own API key" },
        ].map((m) => (
          <button key={m.k}
            className={`rag-cfg-card ${mode === m.k ? "active" : ""}`}
            onClick={() => pick(m.k)}>
            <div className="rag-cfg-card-n">{m.n}</div>
            <div className="rag-cfg-card-d">{m.d}</div>
          </button>
        ))}
      </div>

      {/* LOCAL — Ollama live models */}
      {mode === "local" && (
        <>
          <label className="rag-cfg-label" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <ProviderLogo family="OLLAMA" size={16} /> Ollama model
          </label>
          {loadingOllama ? (
            <div className="rag-cfg-hint">Loading installed models…</div>
          ) : ollamaModels.length > 0 ? (
            <CustomDropdown
              options={ollamaModels.map((m) => ({ value: m.id, label: m.label || m.id }))}
              value={model}
              onChange={dirty(setModel)}
              placeholder={`Select a model… (${ollamaModels.length})`}
            />
          ) : (
            <div className="rag-cfg-warn">
              {ollamaError || "No local models found."}
              <button type="button" className="rag-btn rag-btn-sm" style={{ marginLeft: 8 }}
                onClick={loadOllama} disabled={loadingOllama}>Retry</button>
            </div>
          )}
        </>
      )}

      {/* COMPANY */}
      {mode === "company" && (
        <>
          {providers.length === 0 ? (
            <div className="rag-cfg-hint">
              No company LLM providers yet — ask your admin, or use your own key.
            </div>
          ) : (
            <>
              <label className="rag-cfg-label">Provider</label>
              <CustomDropdown
                showLogo
                options={providers.map((p) => ({
                  value: p.id, label: `${p.name} (${p.family})`, family: p.family,
                }))}
                value={providerId}
                onChange={dirty(setProviderId)}
                placeholder="Select a provider…"
              />
              <label className="rag-cfg-label">Model</label>
              {loadingModels ? (
                <div className="rag-cfg-hint">Loading models…</div>
              ) : (
                <CustomDropdown
                  options={companyModels.map((m) => ({ value: m.id, label: m.label || m.id }))}
                  value={model}
                  onChange={dirty(setModel)}
                  placeholder={companyModels.length
                    ? `Select a model… (${companyModels.length})`
                    : "Select a provider first"}
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
            options={FAMILIES.map((f) => ({ value: f, label: f, family: f }))}
            value={family}
            onChange={dirty(setFamily)}
            placeholder="Select a provider…"
          />
          <label className="rag-cfg-label">Model</label>
          <input className="rag-cfg-select" value={model}
            onChange={(e) => dirty(setModel)(e.target.value)}
            placeholder={family === "OPENAI" ? "gpt-5" : family === "ANTHROPIC"
              ? "claude-sonnet-4-6" : family === "GOOGLE" ? "gemini-2.5-pro" : "model name"} />
          <label className="rag-cfg-label">API key</label>
          <SavedKeyInput
            masked={space?.judge_api_key_masked}
            hasKey={space?.judge_has_own_key}
            value={apiKey}
            onChange={dirty(setApiKey)}
            placeholder={KEY_PLACEHOLDER[family] || "sk-…"}
          />
          <div className="rag-cfg-hint">Stored encrypted. Only a masked preview is ever shown.</div>
        </>
      )}

      {sameAsRag && (
        <div className="rag-cfg-warn" style={{ marginTop: 8 }}>
          ⚠ This is the same provider{model ? " and model" : ""} as the RAG's own
          LLM ({ragLLM}) — a model grading itself inflates scores. Prefer a
          different judge.
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10 }}>
        <button className="rag-btn rag-btn-dark" disabled={saved || saving} onClick={save}>
          {saving ? "Saving…" : saved ? "Judge saved ✓" : "Save judge"}
        </button>
        <span className="rag-cfg-hint" style={{ margin: 0 }}>
          Grades correctness and powers Ragas — independent from the RAG's LLM.
        </span>
      </div>
    </>
  );
};

export default JudgeSelector;
