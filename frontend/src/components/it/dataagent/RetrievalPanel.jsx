import React, { useState } from "react";
import { updateDataSource } from "../../../services/dataAgentApi";
import RetrievalPipeline from "../rag/RetrievalPipeline";
import SavedBar from "./SavedBar";

/*
 * RetrievalPanel — the RAG-space Retrieval panel, reused as-is.
 *
 * Same component, same engine, same knobs (query enhancement · re-ranker
 * model + Voyage key · RRF k · candidate funnel). One difference: search mode
 * is locked to HYBRID, because the three knowledge indexes are made of rare
 * literal tokens (table / column names, KPI codes) AND business phrasing —
 * dropping either branch could only lose recall.
 *
 * On top of it, the one thing a RAG space doesn't have: this agent searches
 * THREE indexes separately (DDL · Prompt→SQL · Business), so "Top-K" is three
 * numbers instead of one.
 */

export default function RetrievalPanel({ source, onChanged, setError }) {
  const [rp, setRp] = useState(() => ({ ...(source.retrieval || {}) }));
  const [ownKey, setOwnKey] = useState("");     // write-only Voyage key
  const [saving, setSaving] = useState(false);

  // RetrievalPipeline reads a SPACE: config under `retrieval_params`, key
  // fields at the root. Adapt the agent's flat config to that shape.
  const cfg = {
    retrieval_params: rp,
    reranker_api_key: ownKey,
    reranker_api_key_masked: source.reranker_api_key_masked,
    reranker_has_own_key: !!rp.reranker_has_own_key,
  };
  const setC = (key, value) =>
    key === "retrieval_params" ? setRp(value) : setOwnKey(value);

  const set = (k, v) => setRp((c) => ({ ...c, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      const payload = { ...rp };
      delete payload.rerank;              // legacy flag — re-ranking is always on
      if (ownKey.trim()) payload.reranker_api_key = ownKey.trim();
      await updateDataSource(source.id, { retrieval_params: payload });
      setOwnKey("");
      onChanged();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const num = (label, key, min, max, hint) => (
    <div>
      <label className="rag-cfg-label">{label}</label>
      <input className="rag-cfg-select" type="number" min={min} max={max}
             value={rp[key] ?? min}
             onChange={(e) => set(key, Number(e.target.value))} />
      {hint && <div className="rag-cfg-hint">{hint}</div>}
    </div>
  );

  return (
    <>
      <SavedBar title="Retrieval" accent="#10b981" chips={{
        Search: "Hybrid (vector + keyword · RRF)",
        "Top-k (DDL / SQL / Business)":
          `${rp.n_ddl} / ${rp.n_sql} / ${rp.n_business}`,
        "Query enhancement": rp.transform_enabled ? "on" : "off",
        Rerank:
          `${rp.reranker_provider === "voyage" ? "rerank-2.5" : "BGE v2-m3"} · top ${rp.rerank_top_n ?? 10}`,
        "RRF k": rp.rrf_k,
        Scope: source.mode === "base"
          ? "base — everything retrieved" : "rag — subset retrieved",
      }} />

      <div className="rag-cfg-panel">
        <div className="rag-cfg-head">
          <div>
            <div className="rag-cfg-title">Retrieval</div>
            <div className="rag-cfg-sub">
              How the agent searches its three knowledge indexes before writing
              SQL — the RAG-space pipeline, hybrid-only.
              {source.mode === "base" && (
                <> This agent is in <strong>base mode</strong> ({source.table_count} tables),
                  so the whole schema is retrieved — these limits apply once it
                  grows past 40 tables or you force <em>rag</em> mode.</>
              )}
            </div>
          </div>
        </div>

        {/* the RAG retrieval panel, verbatim — re-ranking always on, like RAG */}
        <RetrievalPipeline cfg={cfg} setC={setC} hybridOnly />

        {/* the agent-specific Top-K: one number per index */}
        <div className="rp2-block" style={{ marginTop: 14 }}>
          <div className="rp2-block-t">Results kept per index</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
            {num("DDLs", "n_ddl", 1, 100,
                 "≈ tables a question touches, JOINs included — 8–15 fits most schemas")}
            {num("Prompt→SQL pairs", "n_sql", 0, 50,
                 "Few-shot examples — 3–8; more dilutes the signal")}
            {num("Business", "n_business", 0, 50,
                 "Glossary, sample values, documents — 5–10")}
          </div>
          <div className="rp2-hint">
            Each index is searched separately, so 30 DDL blocks can never crowd
            3 glossary entries out of the prompt. Business also covers the
            knowledge documents retrieved by the RAG engine.
            <br />
            <strong>How to choose:</strong> higher = more context in the prompt
            (better recall, but slower, costlier and noisier) · lower = risk of
            missing the one table or term the query needed. Raise DDLs when
            answers reference wide JOIN paths; raise Business when questions use
            company vocabulary. In <em>base</em> mode these caps are bypassed —
            they take effect in <em>rag</em> mode (&gt;40 tables or forced).
          </div>
        </div>

        <div style={{ marginTop: 16 }}>
          <button className="rag-btn rag-btn-blue" onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save retrieval config"}
          </button>
        </div>
      </div>
    </>
  );
}
