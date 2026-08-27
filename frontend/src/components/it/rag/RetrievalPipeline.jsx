import React, { useEffect, useState } from "react";
import { listProviders } from "../../../services/providersApi";
import SavedKeyInput from "./SavedKeyInput";

/*
 * RetrievalPipeline — the engine is pro-tuned; the user chooses only what
 * matters. Backend: app/services/retrieval (PostgreSQL-native).
 *
 *   Search mode        Keyword / Vector / Hybrid ★ (switchable any time)
 *   Query enhancement  LLM rewrite + spell + variants (default ON)
 *   Re-ranker model    BGE v2-m3 (local) or rerank-2.5 (Voyage, own key)
 *   Advanced           RRF k
 *
 * Pipeline: Query Transformation → [ pgvector+HNSW ∥ PostgreSQL FTS ] →
 * RRF → Cross-Encoder Re-ranking → Context Construction → LLM.
 */

const RP_DEFAULTS = {
  search_mode: "hybrid",
  transform_enabled: true,
  reranker_provider: "bge", reranker_model: "",
  reranker_key_source: "company",   // voyage key: "company" (admin) | "own"
  rrf_k: 60,
  fetch_k: 30,        // vector candidates before fusion
  keyword_k: 30,      // keyword candidates before fusion
  rerank_top_n: 10,   // candidates re-scored by the cross-encoder
};

const RERANK_MODELS = {
  bge: {
    label: "BGE v2-m3", desc: "Local · free", star: true,
    params: { reranker_provider: "bge", reranker_model: "" },
  },
  voyage: {
    label: "rerank-2.5", desc: "Voyage AI · fastest",
    params: { reranker_provider: "voyage", reranker_model: "rerank-2.5" },
  },
};

const Radio = ({ options, value, onChange }) => (
  <div className="rp2-radios">
    {options.map((o) => (
      <button key={o.value} type="button"
        className={`rp2-radio ${value === o.value ? "on" : ""}`}
        onClick={() => onChange(o.value)}>
        <span className="rp2-radio-l">
          {o.label}{o.star && <span className="rp2-star"> ★</span>}
        </span>
        {o.desc && <span className="rp2-radio-d">{o.desc}</span>}
      </button>
    ))}
  </div>
);

/* hybridOnly — search mode is fixed to hybrid (Data Agent: schema knowledge
 *              needs both branches, so there is nothing to choose). */
export default function RetrievalPipeline({ cfg, setC, hybridOnly = false }) {
  const rp = { ...RP_DEFAULTS, ...(cfg.retrieval_params || {}) };
  const setMany = (obj) =>
    setC("retrieval_params", { ...(cfg.retrieval_params || {}), ...obj });

  const [showAdvanced, setShowAdvanced] = useState(false);
  const rerankKey = rp.reranker_provider === "voyage" ? "voyage" : "bge";

  // Company-deployed Voyage provider (admin "API Providers" page), if any —
  // decides what the "Company key" option shows.
  const [voyageProvider, setVoyageProvider] = useState(null);
  useEffect(() => {
    listProviders()
      .then((all) => setVoyageProvider(all.find((p) => p.family === "VOYAGE") || null))
      .catch(() => setVoyageProvider(null));
  }, []);

  const keySource = rp.reranker_key_source || "company";

  return (
    <div className="rp2">
      {/* ── Search mode (switchable: keyword / vector / hybrid) ── */}
      <div className="rp2-block">
        <div className="rp2-block-t">Search mode</div>
        {hybridOnly ? (
          <div className="rp2-locked">
            <span className="rp2-locked-badge">HYBRID</span>
            <span>
              <strong>Vector</strong> (pgvector + HNSW) and{" "}
              <strong>keyword</strong> (FTS) always run together, merged with
              Reciprocal Rank Fusion.
            </span>
          </div>
        ) : (
          <Radio
            value={rp.search_mode}
            onChange={(v) => setMany({ search_mode: v })}
            options={[
              { value: "vector", label: "Vector", desc: "Meaning (pgvector + HNSW)" },
              { value: "hybrid", label: "Hybrid", desc: "Both + RRF merge", star: true },
              { value: "keyword", label: "Keyword", desc: "Exact words (FTS)" },
            ]}
          />
        )}
        <div className="rp2-hint">
          {hybridOnly ? (
            <>
              Not a toggle here: table and column names are rare literal tokens
              that embeddings match poorly, while business phrasing is invisible
              to keyword search. Each branch covers the other&apos;s blind spot,
              so turning either off could only lose recall.
            </>
          ) : (
            <>
              <strong>Vector</strong> understands meaning ("vacation days" finds
              "annual leave"). <strong>Keyword</strong> nails exact terms, IDs and
              codes, in every indexed language. <strong>Hybrid</strong> runs both
              and merges them with Reciprocal Rank Fusion — recommended for
              enterprise documents.
            </>
          )}
        </div>
      </div>

      {/* ── Query enhancement ── */}
      <div className="rp2-block">
        <div className="rp2-block-t">Query enhancement</div>
        <label className="rpl-check">
          <input type="checkbox" checked={!!rp.transform_enabled}
            onChange={(e) => setMany({ transform_enabled: e.target.checked })} />
          <span>Improve queries with the LLM before searching</span>
        </label>
        <div className="rp2-hint">
          One call to this space's LLM per question: rewrite, spelling fixes,
          noise removal and alternative phrasings. Identifiers, codes and
          filenames are never altered. Disable for the lowest latency.
        </div>
      </div>

      {/* ── Re-ranker model ── */}
      <div className="rp2-block">
        <div className="rp2-block-t">Re-ranker model</div>
        <Radio
          value={rerankKey}
          onChange={(v) => setMany(RERANK_MODELS[v].params)}
          options={Object.entries(RERANK_MODELS).map(([value, m]) => ({
            value, label: m.label, desc: m.desc, star: m.star,
          }))}
        />
        {rerankKey === "voyage" && (
          <>
            <label className="rag-cfg-label" style={{ marginTop: 10 }}>
              Voyage API key
            </label>
            <Radio
              value={keySource}
              onChange={(v) => setMany({ reranker_key_source: v })}
              options={[
                {
                  value: "company", label: "Company key", star: !!voyageProvider,
                  desc: voyageProvider ? voyageProvider.name : "None deployed",
                },
                { value: "own", label: "My own key", desc: "Enter a Voyage key" },
              ]}
            />
            {keySource === "company" && (
              <div className={voyageProvider ? "rp2-hint" : "rag-cfg-warn"}>
                {voyageProvider
                  ? `Uses the key of "${voyageProvider.name}" deployed by your admin — nothing to enter.`
                  : "No Voyage provider deployed by your admin. Ask them to add one in \"API Providers\", or switch to your own key."}
              </div>
            )}
            {keySource === "own" && (
              <>
                <SavedKeyInput
                  masked={cfg.reranker_api_key_masked}
                  hasKey={cfg.reranker_has_own_key}
                  value={cfg.reranker_api_key || ""}
                  onChange={(v) => setC("reranker_api_key", v)}
                  placeholder="pa-…"
                />
                <div className="rp2-hint">Stored encrypted. Only a masked preview is ever shown.</div>
              </>
            )}
          </>
        )}
        <div className="rp2-hint">
          Always on: a cross-encoder
          re-reads the top candidates together with
          the question and re-orders them — the biggest quality win in the
          pipeline. <strong>BGE v2-m3</strong> runs locally and free;
          <strong> rerank-2.5</strong> answers in ~0.5s via the Voyage API.
          If the model or key is unavailable, the merged order is kept — a
          query never breaks.
        </div>
      </div>

      {/* ── Advanced ── */}
      <button type="button" className="rp2-expander" onClick={() => setShowAdvanced(!showAdvanced)}>
        {showAdvanced ? "▾" : "▸"} Advanced
      </button>
      {showAdvanced && (
        <div className="rp2-block">
          <label className="rpl-field" style={{ maxWidth: 240 }}>
            <span>RRF k · {rp.rrf_k}</span>
            <input type="range" min="20" max="100" step="5" value={rp.rrf_k}
              onChange={(e) => setMany({ rrf_k: parseInt(e.target.value, 10) })} />
          </label>
          <div className="rp2-hint">
            Hybrid fusion constant (default 60). RRF merges the two rankings
            by rank alone — no score normalization needed, since cosine
            similarity and ts_rank are on completely different scales.
          </div>

          <div className="rpl-grid" style={{ marginTop: 12 }}>
            <label className="rpl-field">
              <span>Vector candidates (fetch_k)</span>
              <input type="number" min="5" max="200" value={rp.fetch_k}
                onChange={(e) => setMany({ fetch_k: parseInt(e.target.value, 10) || 30 })} />
            </label>
            <label className="rpl-field">
              <span>Keyword candidates (keyword_k)</span>
              <input type="number" min="5" max="200" value={rp.keyword_k}
                onChange={(e) => setMany({ keyword_k: parseInt(e.target.value, 10) || 30 })} />
            </label>
            <label className="rpl-field">
              <span>Re-ranked candidates (top_n)</span>
              <input type="number" min="5" max="50" value={rp.rerank_top_n}
                onChange={(e) => setMany({ rerank_top_n: parseInt(e.target.value, 10) || 10 })} />
            </label>
          </div>
          <div className="rp2-hint">
            The funnel: each search pulls its <strong>candidates</strong>{" "}
            (default 30 each) → fusion merges them → the top{" "}
            <strong>{rp.rerank_top_n}</strong> are re-scored by the
            cross-encoder → the best <strong>Top-K</strong> go to the LLM.
            Raising candidates improves recall but costs speed; with the
            local BGE re-ranker, top_n is the main latency knob (~0.5s per
            candidate on CPU — rerank-2.5 via API doesn't have this cost).
          </div>
        </div>
      )}

      <div className="rpl-note" style={{ marginTop: 12 }}>
        Applied at <strong>query time</strong> — no re-indexing needed. Saved
        per space with <strong>Save</strong>.
      </div>
    </div>
  );
}
