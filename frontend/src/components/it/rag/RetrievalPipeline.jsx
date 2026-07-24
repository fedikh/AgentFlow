import React, { useState } from "react";

/*
 * RetrievalPipeline — 3-level progressive disclosure.
 *
 *   Level 1 (always visible): Retrieval Profile + Search Mode + Re-ranker.
 *   Level 2 (Advanced ▼):     the pipeline as stages, each driven by PRESETS
 *                             (Fast / Balanced / …) — raw params only on Custom.
 *   Level 3 (Expert ▼):       every raw number (RRF k, k1/b, MMR λ, timeouts…).
 *
 * Presets simply write concrete values into space.retrieval_params — the
 * backend engine is untouched. Extra bookkeeping keys (profile, *_profile)
 * are ignored by the backend config loader (it only applies known fields).
 */

// Mirror of backend defaults (services/retrieval/config.py)
export const RP_DEFAULTS = {
  enable_dense: true, enable_bm25: true, enable_metadata: true, enable_exact: true,
  similarity_threshold: 0, mmr: false, mmr_lambda: 0.6, fetch_k: 30,
  bm25_k: 30, bm25_k1: 1.5, bm25_b: 0.75,
  rewrite_query: false, hyde: false, multi_query: false,
  fusion: "rrf", rrf_k: 60, w_dense: 0, w_bm25: 0, w_metadata: 0,
  reranker_provider: "bge", reranker_model: "", rerank_top_n: 25, rerank_threshold: 0,
  attach_parents: true, auto_merge_parents: false, parent_merge_children: 2,
  context_token_budget: 3000, merge_neighbors: true,
  compress_context: false, compressor: "light",
  timeout_s: 8, bm25_cache_ttl_s: 300,
  // UI bookkeeping (ignored by the backend)
  profile: "balanced", search_mode: "hybrid", dense_profile: "balanced",
  bm25_profile: "balanced", rerank_profile: "best_local",
  enhance_profile: "disabled", doc_context: "balanced", context_size: "medium",
};

/* ── GLOBAL PROFILES: one click tunes the whole pipeline ── */
const PROFILES = {
  fast: {
    icon: "⚡", label: "Fast", desc: "Lowest latency",
    params: { profile: "fast", dense_profile: "fast", bm25_profile: "fast",
      fetch_k: 15, mmr: false, bm25_k: 15, bm25_k1: 1.2, bm25_b: 0.6,
      context_token_budget: 2000, context_size: "small", compress_context: false,
      rewrite_query: false, hyde: false, multi_query: false, enhance_profile: "disabled",
      fusion: "rrf" },
    top_k: 4, rerank: false,
  },
  balanced: {
    icon: "⚖️", label: "Balanced", desc: "Good default", star: true,
    params: { profile: "balanced", dense_profile: "balanced", bm25_profile: "balanced",
      fetch_k: 30, mmr: false, bm25_k: 30, bm25_k1: 1.5, bm25_b: 0.75,
      context_token_budget: 3000, context_size: "medium", compress_context: false,
      rewrite_query: false, hyde: false, multi_query: false, enhance_profile: "disabled",
      fusion: "rrf" },
    top_k: 5, rerank: false,
  },
  precision: {
    icon: "🎯", label: "High Precision", desc: "Rerank, strict scores",
    params: { profile: "precision", dense_profile: "balanced", bm25_profile: "precision",
      fetch_k: 30, mmr: false, bm25_k: 30, bm25_k1: 1.6, bm25_b: 0.9,
      similarity_threshold: 0.25, rerank_threshold: 0.3,
      reranker_provider: "bge", rerank_profile: "best_local",
      context_token_budget: 3000, context_size: "medium",
      fusion: "rrf" },
    top_k: 5, rerank: true,
  },
  recall: {
    icon: "📚", label: "High Recall", desc: "Cast a wide net",
    params: { profile: "recall", dense_profile: "recall", bm25_profile: "balanced",
      fetch_k: 60, mmr: true, bm25_k: 60,
      multi_query: true, enhance_profile: "auto",
      context_token_budget: 4500, context_size: "large",
      fusion: "rrf" },
    top_k: 8, rerank: false,
  },
  custom: { icon: "🧪", label: "Custom", desc: "Tune every stage", params: { profile: "custom" } },
};

/* ── Per-stage presets ── */
const DENSE_PROFILES = {
  fast: { fetch_k: 15, similarity_threshold: 0, mmr: false },
  balanced: { fetch_k: 30, similarity_threshold: 0, mmr: false },
  recall: { fetch_k: 60, similarity_threshold: 0, mmr: true },
};
const BM25_PROFILES = {
  fast: { bm25_k: 15, bm25_k1: 1.2, bm25_b: 0.6 },
  balanced: { bm25_k: 30, bm25_k1: 1.5, bm25_b: 0.75 },
  precision: { bm25_k: 30, bm25_k1: 1.6, bm25_b: 0.9 },
};
const RERANK_PROFILES = {
  fast_local: { reranker_provider: "flashrank", reranker_model: "" },
  best_local: { reranker_provider: "bge", reranker_model: "" },
  cloud: { reranker_provider: "cohere", reranker_model: "" },
};
const ENHANCE_PROFILES = {
  disabled: { rewrite_query: false, hyde: false, multi_query: false },
  auto: { rewrite_query: true, hyde: false, multi_query: true },
};
const DOC_CONTEXT = {
  minimal: { attach_parents: false, auto_merge_parents: false },
  balanced: { attach_parents: true, auto_merge_parents: false },
  full: { attach_parents: true, auto_merge_parents: true },
};
const CONTEXT_SIZES = {
  small: { context_token_budget: 2000, merge_neighbors: true },
  medium: { context_token_budget: 3000, merge_neighbors: true },
  large: { context_token_budget: 5000, merge_neighbors: true },
};
const SEARCH_MODES = {
  semantic: { enable_dense: true, enable_bm25: false, enable_metadata: true, enable_exact: true },
  hybrid: { enable_dense: true, enable_bm25: true, enable_metadata: true, enable_exact: true },
  keyword: { enable_dense: false, enable_bm25: true, enable_metadata: true, enable_exact: true },
  metadata: { enable_dense: false, enable_bm25: false, enable_metadata: true, enable_exact: true },
};

const RERANKERS = [
  { value: "bge", label: "BGE v2-m3 (local · best)" },
  { value: "jina_local", label: "Jina v2 (local)" },
  { value: "flashrank", label: "FlashRank (local · fastest)" },
  { value: "cross_encoder", label: "CrossEncoder MiniLM (local · light)" },
  { value: "cohere", label: "Cohere Rerank (API key)" },
  { value: "jina", label: "Jina AI (API key)" },
  { value: "voyage", label: "Voyage (API key)" },
];

/* ── small controls ── */
const Radio = ({ options, value, onChange }) => (
  <div className="rp2-radios">
    {options.map((o) => (
      <button key={o.value} type="button"
        className={`rp2-radio ${value === o.value ? "on" : ""}`}
        onClick={() => onChange(o.value)}>
        {o.icon && <span className="rp2-radio-ic">{o.icon}</span>}
        <span className="rp2-radio-l">
          {o.label}{o.star && <span className="rp2-star"> ★</span>}
        </span>
        {o.desc && <span className="rp2-radio-d">{o.desc}</span>}
      </button>
    ))}
  </div>
);
const Num = ({ label, value, onChange, min, max, step = 1 }) => (
  <label className="rpl-field">
    <span>{label}</span>
    <input type="number" value={value} min={min} max={max} step={step}
      onChange={(e) => onChange(step < 1 ? parseFloat(e.target.value) : parseInt(e.target.value, 10))} />
  </label>
);
const Check = ({ label, value, onChange }) => (
  <label className="rpl-check">
    <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />
    <span>{label}</span>
  </label>
);

/* Pipeline stage row: green dot + name + summary; click to expand. */
function Stage({ on = true, title, summary, open, onOpen, children }) {
  return (
    <div className={`rp2-stage ${open ? "open" : ""}`}>
      <button type="button" className="rp2-stage-head" onClick={onOpen}>
        <span className={`rp2-dot ${on ? "on" : ""}`} />
        <span className="rp2-stage-t">{title}</span>
        <span className="rp2-stage-s">{summary}</span>
        <span className="rp2-caret">{open ? "▾" : "▸"}</span>
      </button>
      {open && <div className="rp2-stage-body">{children}</div>}
    </div>
  );
}

export default function RetrievalPipeline({ cfg, setC }) {
  const rp = { ...RP_DEFAULTS, ...(cfg.retrieval_params || {}) };
  const setMany = (obj) =>
    setC("retrieval_params", { ...(cfg.retrieval_params || {}), ...obj });
  const set = (k, v) => setMany({ [k]: v });

  const [showAdvanced, setShowAdvanced] = useState(rp.profile === "custom");
  const [showExpert, setShowExpert] = useState(false);
  const [open, setOpen] = useState({});
  const toggle = (k) => setOpen((o) => ({ ...o, [k]: !o[k] }));

  const applyProfile = (key) => {
    const p = PROFILES[key];
    setMany(p.params);
    if (p.top_k != null) setC("top_k", p.top_k);
    if (p.rerank != null) setC("reranking_enabled", p.rerank);
    if (key === "custom") setShowAdvanced(true);
  };

  const cap = (s) => (s || "").charAt(0).toUpperCase() + (s || "").slice(1).replace("_", " ");

  return (
    <div className="rp2">
      {/* ═══ LEVEL 1 — what every user sees ═══ */}
      <div className="rp2-block">
        <div className="rp2-block-t">Retrieval profile</div>
        <Radio
          value={rp.profile}
          onChange={applyProfile}
          options={Object.entries(PROFILES).map(([value, p]) => ({
            value, icon: p.icon, label: p.label, desc: p.desc, star: p.star,
          }))}
        />
        <div className="rp2-hint">
          One click tunes the whole pipeline — candidates, keyword search,
          re-ranking and context size. Pick <strong>Custom</strong> to tune stages yourself.
        </div>
      </div>

      <div className="rp2-block">
        <div className="rp2-block-t">Search mode</div>
        <Radio
          value={rp.search_mode}
          onChange={(v) => setMany({ search_mode: v, ...SEARCH_MODES[v] })}
          options={[
            { value: "semantic", label: "Semantic", desc: "Meaning only" },
            { value: "hybrid", label: "Hybrid", desc: "Meaning + keywords", star: true },
            { value: "keyword", label: "Keyword", desc: "Exact words" },
            { value: "metadata", label: "Metadata", desc: "Names & pages" },
          ]}
        />
      </div>

      <div className="rp2-block">
        <div className="rp2-block-t">Re-ranker</div>
        <Radio
          value={!cfg.reranking_enabled ? "off" : (rp.rerank_profile || "best_local")}
          onChange={(v) => {
            if (v === "off") { setC("reranking_enabled", false); return; }
            setC("reranking_enabled", true);
            if (v !== "custom") setMany({ rerank_profile: v, ...RERANK_PROFILES[v] });
            else setMany({ rerank_profile: "custom" });
          }}
          options={[
            { value: "off", label: "Disabled", desc: "Fastest" },
            { value: "fast_local", label: "Fast Local", desc: "FlashRank" },
            { value: "best_local", label: "Best Local", desc: "BGE v2-m3", star: true },
            { value: "cloud", label: "Cloud", desc: "Cohere (key)" },
            { value: "custom", label: "Custom", desc: "Pick provider" },
          ]}
        />
        {cfg.reranking_enabled && rp.rerank_profile === "custom" && (
          <div className="rpl-grid" style={{ marginTop: 10 }}>
            <label className="rpl-field">
              <span>Provider</span>
              <select value={rp.reranker_provider} onChange={(e) => set("reranker_provider", e.target.value)}>
                {RERANKERS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </label>
            <label className="rpl-field">
              <span>Model (empty = default)</span>
              <input value={rp.reranker_model} placeholder="provider default"
                onChange={(e) => set("reranker_model", e.target.value)} />
            </label>
          </div>
        )}
      </div>

      {/* ═══ LEVEL 2 — Advanced: the pipeline, preset-driven ═══ */}
      <button type="button" className="rp2-expander" onClick={() => setShowAdvanced(!showAdvanced)}>
        {showAdvanced ? "▾" : "▸"} Advanced settings
      </button>

      {showAdvanced && (
        <div className="rp2-pipe">
          <Stage title="Query enhancement" on={rp.enhance_profile !== "disabled"}
            summary={rp.enhance_profile === "custom" ? "Custom" : rp.enhance_profile === "auto" ? "Automatic" : "Disabled"}
            open={!!open.enh} onOpen={() => toggle("enh")}>
            <Radio
              value={rp.enhance_profile}
              onChange={(v) => setMany({ enhance_profile: v, ...(ENHANCE_PROFILES[v] || {}) })}
              options={[
                { value: "disabled", label: "Disabled", desc: "Query as typed" },
                { value: "auto", label: "Automatic", desc: "Rewrite + variants", star: true },
                { value: "custom", label: "Custom", desc: "Pick techniques" },
              ]}
            />
            {rp.enhance_profile === "custom" && (
              <div className="rpl-grid" style={{ marginTop: 10 }}>
                <Check label="Rewrite query" value={rp.rewrite_query} onChange={(v) => set("rewrite_query", v)} />
                <Check label="HyDE (embed a hypothetical answer)" value={rp.hyde} onChange={(v) => set("hyde", v)} />
                <Check label="Multi-query variants" value={rp.multi_query} onChange={(v) => set("multi_query", v)} />
              </div>
            )}
            <div className="rp2-hint">Uses this space's LLM. Identifiers and filenames always stay literal.</div>
          </Stage>

          <Stage title="Semantic search" on={rp.enable_dense}
            summary={rp.enable_dense ? cap(rp.dense_profile) : "Off"}
            open={!!open.dense} onOpen={() => toggle("dense")}>
            <Radio
              value={rp.dense_profile}
              onChange={(v) => setMany({ dense_profile: v, ...(DENSE_PROFILES[v] || {}) })}
              options={[
                { value: "fast", label: "Fast", desc: "Few candidates" },
                { value: "balanced", label: "Balanced", star: true, desc: "Default" },
                { value: "recall", label: "High Recall", desc: "Wide + diverse" },
                { value: "custom", label: "Custom", desc: "Raw values" },
              ]}
            />
            {rp.dense_profile === "custom" && (
              <div className="rpl-grid" style={{ marginTop: 10 }}>
                <Num label="Fetch K (candidates)" value={rp.fetch_k} min={5} max={200} onChange={(v) => set("fetch_k", v)} />
                <Num label="Similarity threshold" value={rp.similarity_threshold} min={0} max={1} step={0.05}
                  onChange={(v) => set("similarity_threshold", v)} />
                <Check label="MMR (diversify)" value={rp.mmr} onChange={(v) => set("mmr", v)} />
              </div>
            )}
          </Stage>

          <Stage title="Keyword search" on={rp.enable_bm25}
            summary={rp.enable_bm25 ? cap(rp.bm25_profile) : "Off"}
            open={!!open.bm25} onOpen={() => toggle("bm25")}>
            <Radio
              value={rp.bm25_profile}
              onChange={(v) => setMany({ bm25_profile: v, ...(BM25_PROFILES[v] || {}) })}
              options={[
                { value: "fast", label: "Fast", desc: "Few candidates" },
                { value: "balanced", label: "Balanced", star: true, desc: "Default" },
                { value: "precision", label: "High Precision", desc: "Strict matching" },
                { value: "custom", label: "Custom", desc: "k1 / b values" },
              ]}
            />
            {rp.bm25_profile === "custom" && (
              <div className="rpl-grid" style={{ marginTop: 10 }}>
                <Num label="Top K" value={rp.bm25_k} min={5} max={200} onChange={(v) => set("bm25_k", v)} />
                <Num label="k1" value={rp.bm25_k1} min={0.5} max={3} step={0.1} onChange={(v) => set("bm25_k1", v)} />
                <Num label="b" value={rp.bm25_b} min={0} max={1} step={0.05} onChange={(v) => set("bm25_b", v)} />
              </div>
            )}
          </Stage>

          <Stage title="Fusion" on
            summary={rp.fusion === "rrf" ? "Automatic" : "Weighted"}
            open={!!open.fusion} onOpen={() => toggle("fusion")}>
            <Radio
              value={rp.fusion}
              onChange={(v) => set("fusion", v)}
              options={[
                { value: "rrf", label: "Automatic", desc: "Rank-based merge", star: true },
                { value: "weighted", label: "Weighted", desc: "You set the mix" },
              ]}
            />
            {rp.fusion === "weighted" && (
              <div className="rpl-grid" style={{ marginTop: 10 }}>
                <Num label="Semantic weight" value={rp.w_dense || cfg.semantic_weight || 0.7}
                  min={0} max={1} step={0.05} onChange={(v) => set("w_dense", v)} />
                <Num label="Keyword weight" value={rp.w_bm25 || 0.3} min={0} max={1} step={0.05}
                  onChange={(v) => set("w_bm25", v)} />
              </div>
            )}
          </Stage>

          <Stage title="Document context" on={rp.attach_parents || rp.auto_merge_parents}
            summary={rp.doc_context === "full" ? "Full section" : rp.doc_context === "minimal" ? "Minimal" : "Balanced"}
            open={!!open.doc} onOpen={() => toggle("doc")}>
            <Radio
              value={rp.doc_context}
              onChange={(v) => setMany({ doc_context: v, ...DOC_CONTEXT[v] })}
              options={[
                { value: "minimal", label: "Minimal", desc: "Chunks only" },
                { value: "balanced", label: "Balanced", desc: "Add parent context", star: true },
                { value: "full", label: "Full Section", desc: "Rebuild whole sections" },
              ]}
            />
          </Stage>

          <Stage title="Context size" on
            summary={rp.context_size === "custom" ? `${rp.context_token_budget} tokens` : cap(rp.context_size)}
            open={!!open.ctx} onOpen={() => toggle("ctx")}>
            <Radio
              value={rp.context_size}
              onChange={(v) => setMany({ context_size: v, ...(CONTEXT_SIZES[v] || {}) })}
              options={[
                { value: "small", label: "Small", desc: "~2000 tokens" },
                { value: "medium", label: "Medium", desc: "~3000 tokens", star: true },
                { value: "large", label: "Large", desc: "~5000 tokens" },
                { value: "custom", label: "Custom", desc: "Budget & merging" },
              ]}
            />
            {rp.context_size === "custom" && (
              <div className="rpl-grid" style={{ marginTop: 10 }}>
                <Num label="Token budget" value={rp.context_token_budget} min={500} max={12000} step={100}
                  onChange={(v) => set("context_token_budget", v)} />
                <Check label="Merge adjacent chunks" value={rp.merge_neighbors} onChange={(v) => set("merge_neighbors", v)} />
                <Check label="Compress context" value={rp.compress_context} onChange={(v) => set("compress_context", v)} />
              </div>
            )}
          </Stage>
        </div>
      )}

      {/* ═══ LEVEL 3 — Expert: every raw number ═══ */}
      {showAdvanced && (
        <button type="button" className="rp2-expander rp2-expander-expert" onClick={() => setShowExpert(!showExpert)}>
          {showExpert ? "▾" : "▸"} Expert settings
        </button>
      )}
      {showAdvanced && showExpert && (
        <div className="rp2-expert">
          <div className="rpl-grid">
            <Num label="RRF k" value={rp.rrf_k} min={10} max={200} onChange={(v) => set("rrf_k", v)} />
            <Num label="BM25 k1" value={rp.bm25_k1} min={0.5} max={3} step={0.1} onChange={(v) => set("bm25_k1", v)} />
            <Num label="BM25 b" value={rp.bm25_b} min={0} max={1} step={0.05} onChange={(v) => set("bm25_b", v)} />
            <Num label="MMR λ" value={rp.mmr_lambda} min={0} max={1} step={0.05} onChange={(v) => set("mmr_lambda", v)} />
            <Num label="Fetch K" value={rp.fetch_k} min={5} max={200} onChange={(v) => set("fetch_k", v)} />
            <Num label="Similarity threshold" value={rp.similarity_threshold} min={0} max={1} step={0.05}
              onChange={(v) => set("similarity_threshold", v)} />
            <Num label="Rerank top N" value={rp.rerank_top_n} min={5} max={100} onChange={(v) => set("rerank_top_n", v)} />
            <Num label="Rerank threshold" value={rp.rerank_threshold} min={0} max={1} step={0.05}
              onChange={(v) => set("rerank_threshold", v)} />
            <Num label="Parent merge ≥ N children" value={rp.parent_merge_children} min={2} max={6}
              onChange={(v) => set("parent_merge_children", v)} />
            <Num label="Retriever timeout (s)" value={rp.timeout_s} min={2} max={60} onChange={(v) => set("timeout_s", v)} />
            <Num label="BM25 cache TTL (s)" value={rp.bm25_cache_ttl_s} min={30} max={3600} step={30}
              onChange={(v) => set("bm25_cache_ttl_s", v)} />
          </div>
          <div className="rp2-hint" style={{ marginTop: 8 }}>
            Raw engine parameters — the presets above already set sensible values.
          </div>
        </div>
      )}

      <div className="rpl-note" style={{ marginTop: 12 }}>
        Applied at <strong>query time</strong> — no re-indexing needed. Saved per
        space with <strong>Save</strong>.
      </div>
    </div>
  );
}
