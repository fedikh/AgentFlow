import React, { useEffect, useState } from "react";
import {
  listProviders,
  createProvider,
  updateProvider,
  deleteProvider,
} from "../../services/providersApi";
import ProviderLogo from "../../components/ProviderLogo";
import "../../styles/admin/apiProviders.css";

// Batch 7: the provider family list depends on the provider kind.
const FAMILIES_BY_KIND = {
  LLM: ["OPENAI", "ANTHROPIC", "GOOGLE", "GROQ", "CUSTOM"],
  EMBEDDING: ["OPENAI", "VOYAGE"],
};
const KINDS = ["LLM", "EMBEDDING"];

// Families that can serve BOTH chat and embeddings from a single key. The
// backend confirms this per-provider via `capabilities`; this drives the hint
// shown while adding a provider (before the row exists).
const DUAL_CAPABLE = ["OPENAI"];

// Human label for what a provider (row) can be used for.
const capabilitiesLabel = (p) => {
  const caps = p.capabilities || [p.kind];
  if (caps.includes("LLM") && caps.includes("EMBEDDING"))
    return "LLM + Embedding";
  if (caps.includes("EMBEDDING")) return "Embedding";
  return "LLM";
};

const emptyForm = {
  name: "",
  kind: "LLM",
  family: "OPENAI",
  api_key: "",
  base_url: "",
};

const ApiProvidersPage = () => {
  const [providers, setProviders] = useState(null);
  const [msg, setMsg] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  const load = () =>
    listProviders()
      .then(setProviders)
      .catch((e) => setMsg({ type: "error", text: e.message }));

  useEffect(() => {
    load();
  }, []);
  useEffect(() => {
    if (msg) {
      const t = setTimeout(() => setMsg(null), 4000);
      return () => clearTimeout(t);
    }
  }, [msg]);

  const openCreate = () => {
    setEditingId(null);
    setForm(emptyForm);
    setModalOpen(true);
  };
  const openEdit = (p) => {
    setEditingId(p.id);
    setForm({
      name: p.name,
      kind: p.kind,
      family: p.family,
      api_key: "",
      base_url: p.base_url || "",
    });
    setModalOpen(true);
  };
  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const handleSave = async () => {
    if (!form.name.trim()) {
      setMsg({ type: "error", text: "Provider name is required" });
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        kind: form.kind,
        family: form.family,
        base_url: form.base_url.trim() || null,
      };
      if (form.api_key.trim()) payload.api_key = form.api_key.trim();

      if (editingId) {
        await updateProvider(editingId, payload);
        setMsg({ type: "success", text: "Provider updated" });
      } else {
        if (!form.api_key.trim() && form.family !== "OLLAMA") {
          setMsg({ type: "error", text: "API key is required" });
          setSaving(false);
          return;
        }
        await createProvider(payload);
        setMsg({ type: "success", text: "Provider added" });
      }
      setModalOpen(false);
      load();
    } catch (e) {
      setMsg({ type: "error", text: e.message });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (p) => {
    if (!window.confirm(`Delete provider "${p.name}"?`)) return;
    try {
      await deleteProvider(p.id);
      setMsg({ type: "success", text: "Provider deleted" });
      load();
    } catch (e) {
      setMsg({ type: "error", text: e.message });
    }
  };

  if (providers === null) return <p className="ap-loading">Loading...</p>;

  return (
    <div className="ap-page">
      <div className="ap-head">
        <div>
          <h1 className="ap-title">API Providers</h1>
          <p className="ap-subtitle">
            Add a provider with just a name and API key. IT teams then pick any
            model the provider offers — the list is fetched live from the API.
            Keys are encrypted and never shown in full.
          </p>
        </div>
        <button className="ap-btn" onClick={openCreate}>
          + Add provider
        </button>
      </div>

      {msg && (
        <div className={`ap-banner ap-banner-${msg.type}`}>{msg.text}</div>
      )}

      {providers.length === 0 ? (
        <div className="ap-empty">
          <div className="ap-empty-title">No providers yet</div>
          <div>Add OpenAI, Anthropic, Gemini, or Groq to get started.</div>
        </div>
      ) : (
        <div className="ap-grid">
          {providers.map((p) => (
            <div className="ap-card" key={p.id}>
              <div className="ap-card-head">
                <div className="ap-card-icon">
                  <ProviderLogo family={p.family} size={18} />
                </div>
                <span className="ap-card-name">{p.name}</span>
                <span
                  className={`ap-kind-badge ${p.kind === "LLM" ? "ap-kind-llm" : "ap-kind-emb"}`}
                >
                  {p.kind}
                </span>
              </div>
              <div className="ap-card-body">
                <div className="ap-row">
                  <span className="ap-row-label">Provider</span>
                  <span
                    className="ap-row-value"
                    style={{ display: "flex", alignItems: "center", gap: 6 }}
                  >
                    <ProviderLogo family={p.family} size={14} /> {p.family}
                  </span>
                </div>
                <div className="ap-row">
                  <span className="ap-row-label">API key</span>
                  <span className="ap-row-value mono">
                    {p.has_key ? p.api_key_masked : "— none —"}
                  </span>
                </div>
                <div className="ap-row">
                  <span className="ap-row-label">Usable for</span>
                  <span className="ap-row-value">{capabilitiesLabel(p)}</span>
                </div>
              </div>
              <div className="ap-card-actions">
                <button className="ap-btn-ghost" onClick={() => openEdit(p)}>
                  Edit
                </button>
                <button
                  className="ap-btn-danger"
                  onClick={() => handleDelete(p)}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {modalOpen && (
        <div
          className="ap-overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget) setModalOpen(false);
          }}
        >
          <div className="ap-modal">
            <div className="ap-modal-head">
              <span className="ap-modal-title">
                {editingId ? "Edit provider" : "Add provider"}
              </span>
              <button
                className="ap-modal-close"
                onClick={() => setModalOpen(false)}
              >
                ✕
              </button>
            </div>
            <div className="ap-modal-body">
              <div className="ap-field">
                <label className="ap-label">Name</label>
                <input
                  className="ap-input"
                  value={form.name}
                  onChange={(e) => setField("name", e.target.value)}
                  placeholder="e.g. Company OpenAI"
                />
              </div>

              <div className="ap-field-row">
                <div className="ap-field">
                  <label className="ap-label">Type</label>
                  <select
                    className="ap-select"
                    value={form.kind}
                    onChange={(e) => {
                      const kind = e.target.value;
                      const fams = FAMILIES_BY_KIND[kind] || [];
                      const family = fams.includes(form.family)
                        ? form.family
                        : fams[0];
                      setForm((f) => ({ ...f, kind, family }));
                    }}
                  >
                    {KINDS.map((k) => (
                      <option key={k} value={k}>
                        {k}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="ap-field">
                  <label className="ap-label">Provider</label>
                  <select
                    className="ap-select"
                    value={form.family}
                    onChange={(e) => setField("family", e.target.value)}
                  >
                    {(FAMILIES_BY_KIND[form.kind] || []).map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {DUAL_CAPABLE.includes(form.family) && (
                <div className="ap-hint" style={{ marginTop: -4 }}>
                  ✨ One {form.family} key works for <strong>both</strong> LLM and
                  Embedding models — add it once and IT teams can pick it in
                  either config.
                </div>
              )}

              <div className="ap-field">
                <label className="ap-label">API key</label>
                <input
                  className="ap-input"
                  type="password"
                  value={form.api_key}
                  onChange={(e) => setField("api_key", e.target.value)}
                  placeholder={
                    editingId ? "Leave blank to keep current key" : "sk-..."
                  }
                />
                <span className="ap-hint">
                  {editingId
                    ? "Only enter a key to replace the stored one."
                    : "Required (except Ollama). Stored encrypted."}
                </span>
              </div>

              <div className="ap-field">
                <label className="ap-label">Base URL (optional)</label>
                <input
                  className="ap-input"
                  value={form.base_url}
                  onChange={(e) => setField("base_url", e.target.value)}
                  placeholder="For custom / self-hosted endpoints"
                />
              </div>
            </div>
            <div className="ap-modal-foot">
              <button
                className="ap-btn-ghost"
                onClick={() => setModalOpen(false)}
              >
                Cancel
              </button>
              <button className="ap-btn" onClick={handleSave} disabled={saving}>
                {saving
                  ? "Saving…"
                  : editingId
                    ? "Save changes"
                    : "Add provider"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ApiProvidersPage;
