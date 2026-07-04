import React, { useEffect, useState, useRef } from "react";
import {
  listProviders,
  getProviderModels,
} from "../../../services/providersApi";
import ProviderLogo from "../../ProviderLogo";

/**
 * LLMSourceSelector — Local / Company / Own key.
 * Provider dropdown shows logos; Model dropdown uses the same custom design
 * without logos. Native <select> can't render logos inside <option>, so both
 * use a custom dropdown for a consistent look.
 */
const FAMILIES = ["GROQ", "OPENAI", "ANTHROPIC", "GOOGLE", "OLLAMA", "CUSTOM"];

/* ── Custom dropdown. If an option has `family`, its logo is shown. ── */
function CustomDropdown({ options, value, onChange, placeholder, showLogo }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const selected = options.find((o) => o.value === value);

  const rowBase = {
    width: "100%",
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "10px 12px",
    fontSize: 13,
    color: "#0d1f35",
    textAlign: "left",
    cursor: "pointer",
  };

  return (
    <div
      ref={ref}
      style={{ position: "relative", width: "100%", marginBottom: 12 }}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          ...rowBase,
          borderRadius: 8,
          border: "1px solid #e2e8f0",
          background: "#fff",
        }}
      >
        {selected ? (
          <>
            {showLogo && <ProviderLogo family={selected.family} size={18} />}
            <span style={{ flex: 1 }}>{selected.label}</span>
          </>
        ) : (
          <span style={{ flex: 1, color: "#94a3b8" }}>{placeholder}</span>
        )}
        <span style={{ color: "#94a3b8", fontSize: 10 }}>▼</span>
      </button>

      {open && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            right: 0,
            background: "#fff",
            border: "1px solid #e2e8f0",
            borderRadius: 8,
            boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
            zIndex: 50,
            overflow: "hidden",
            maxHeight: 260,
            overflowY: "auto",
          }}
        >
          {options.map((o) => (
            <button
              key={o.value}
              type="button"
              onClick={() => {
                onChange(o.value);
                setOpen(false);
              }}
              style={{
                ...rowBase,
                border: "none",
                background: o.value === value ? "#eff6ff" : "#fff",
              }}
              onMouseEnter={(e) => {
                if (o.value !== value)
                  e.currentTarget.style.background = "#f8fafc";
              }}
              onMouseLeave={(e) => {
                if (o.value !== value)
                  e.currentTarget.style.background = "#fff";
              }}
            >
              {showLogo && <ProviderLogo family={o.family} size={18} />}
              <span>{o.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

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
              label: f,
              family: f,
            }))}
            value={value.llm_provider || "OPENAI"}
            onChange={(f) => onChange({ llm_provider: f, llm_model: "" })}
            placeholder="Select a provider…"
          />

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
