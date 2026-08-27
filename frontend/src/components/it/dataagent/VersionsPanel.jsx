import React, { useEffect, useState } from "react";
import {
  applyVersion, deleteVersion, deployVersion, listVersions, saveVersion,
} from "../../../services/dataAgentApi";
import "../../../styles/it/versions.css";

/**
 * VersionsPanel (Data Agent) — save/apply/deploy config snapshots, the RAG
 * space lifecycle mirrored.
 *
 * A version stores the pipeline config only — generation, models, retrieval,
 * execution safety — never the connection identity and never the trained
 * index. Deploying a version applies its config and puts the agent live;
 * "Load config" applies it to the working agent without deploying. If the
 * version carries a different embedding model, the agent flips to "stale"
 * (re-train needed) — same rule as editing the Models panel.
 */

const fmtDate = (s) => {
  try { return new Date(String(s).replace(" ", "T")).toLocaleString(); }
  catch { return s; }
};

const cfgChips = (cfg = {}) => {
  const rp = cfg.retrieval_params || {};
  const items = [];
  if (cfg.llm_model) items.push(["llm", cfg.llm_model]);
  if (cfg.embedding_model)
    items.push(["embed", String(cfg.embedding_model).split("/").pop()]);
  items.push(["top-k", `${rp.n_ddl ?? 10}/${rp.n_sql ?? 5}/${rp.n_business ?? 8}`]);
  items.push(["rerank",
    rp.reranker_provider === "voyage" ? "rerank-2.5" : "BGE v2-m3"]);
  items.push(["rows", cfg.row_limit ?? 1000]);
  return items;
};

const configSections = (cfg = {}) => {
  const rp = cfg.retrieval_params || {};
  return [
    ["LLM",
      `${cfg.llm_model || "—"} · temp ${cfg.llm_temperature ?? 0} · ` +
      `max ${cfg.llm_max_tokens ?? 2000} tok · ` +
      `prompt ${cfg.prompt_mode === "custom" ? "custom" : "default"}` +
      (cfg.llm_provider_id ? " · company provider" : "")],
    ["Embedding",
      `${cfg.embedding_model || "—"}` +
      (cfg.embedding_provider_id ? " · company provider"
        : cfg.embedding_provider ? ` · ${cfg.embedding_provider}` : "")],
    ["Retrieval",
      `hybrid · top-k ${rp.n_ddl ?? 10}/${rp.n_sql ?? 5}/${rp.n_business ?? 8} · ` +
      `rrf ${rp.rrf_k ?? 60} · fetch ${rp.fetch_k ?? 20}/${rp.keyword_k ?? 20} · ` +
      `rerank ${rp.reranker_provider === "voyage" ? (rp.reranker_model || "rerank-2.5") : "BGE v2-m3"} ` +
      `(top ${rp.rerank_top_n ?? 10}) · ` +
      `enhance ${rp.transform_enabled ? "on" : "off"}`],
    ["Execution",
      `${cfg.row_limit ?? 1000} rows max · ${Math.round((cfg.timeout_ms ?? 30000) / 1000)}s timeout · ` +
      `mode ${cfg.mode_override || "auto"} · ` +
      `results to LLM ${cfg.send_results_to_llm ? "yes" : "no"}`],
  ];
};

export default function VersionsPanel({ source, onChanged, setError }) {
  const [versions, setVersions] = useState(null);       // null = loading
  const [showSave, setShowSave] = useState(false);
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");
  const [openCfg, setOpenCfg] = useState({});
  const [busy, setBusy] = useState("");

  const load = () =>
    listVersions(source.id).then(setVersions).catch((e) => {
      setVersions([]);
      setError(e.message);
    });
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source.id]);

  const nextLabel = `v${(versions?.[0]?.version_number || 0) + 1}`;
  const deployed = source.status === "deployed";

  const act = (key, fn) => async (...args) => {
    setBusy(key);
    try {
      await fn(...args);
      await load();
      onChanged();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  const submitSave = act("save", async () => {
    await saveVersion(source.id, label.trim() || nextLabel, notes.trim());
    setLabel(""); setNotes(""); setShowSave(false);
  });
  const onApply = act("apply", (v) => applyVersion(source.id, v.id));
  const onDeploy = act("deploy", (v) => deployVersion(source.id, v.id));
  const onDelete = (v) => {
    if (!window.confirm(`Delete version “${v.label}”?`)) return;
    act("delete", () => deleteVersion(source.id, v.id))();
  };

  const toggleCfg = (id) => setOpenCfg((o) => ({ ...o, [id]: !o[id] }));
  const trainable = ["trained", "stale", "deployed"].includes(source.status);

  return (
    <div className="rag-cfg-panel">
      <div className="vp-head">
        <div>
          <div className="vp-head-title">Versions</div>
          <div className="vp-head-sub">
            Save config snapshots of this agent, compare them, and deploy the
            one you want. Connection and trained index are not part of a
            version.
          </div>
        </div>
        <button className="rag-btn rag-btn-sm rag-btn-dark"
                onClick={() => setShowSave((v) => !v)}>
          {showSave ? "Cancel" : "＋ Save current config"}
        </button>
      </div>

      {showSave && (
        <div className="vp-card" style={{ marginBottom: 12 }}>
          <label className="rag-cfg-label">Version name</label>
          <input className="rag-cfg-select" value={label} placeholder={nextLabel}
                 onChange={(e) => setLabel(e.target.value)} />
          <label className="rag-cfg-label">Notes (optional)</label>
          <input className="rag-cfg-select" value={notes}
                 placeholder="e.g. gpt-4o + reranking top 20"
                 onChange={(e) => setNotes(e.target.value)} />
          <div className="vp-actions">
            <button className="rag-btn rag-btn-sm rag-btn-blue"
                    onClick={submitSave} disabled={busy === "save"}>
              {busy === "save" ? "Saving…" : "Save version"}
            </button>
          </div>
        </div>
      )}

      {deployed && (
        <div className="rag-cfg-hint" style={{
          marginBottom: 12, padding: "8px 11px", borderRadius: 8,
          background: "rgba(22,163,74,.08)",
          border: "1px solid rgba(22,163,74,.3)", color: "#166534",
        }}>
          🔒 This agent is <strong>deployed &amp; live</strong> — loading a
          config is blocked. Pause the deployment first, or deploy another
          version directly to switch the live config.
        </div>
      )}

      {versions === null ? (
        <div className="vp-banner empty">Loading versions…</div>
      ) : versions.length === 0 ? (
        <div className="vp-banner empty">
          No versions yet. Tune the agent, then “Save current config” to
          create v1.
        </div>
      ) : (
        <div className="vp-list">
          {versions.map((v) => {
            const isDeployedV = v.status === "DEPLOYED";
            const isLive = isDeployedV && deployed;
            const badge = isLive ? "deployed"
              : isDeployedV ? "paused"
              : v.status === "ARCHIVED" ? "archived" : "saved";
            return (
              <div key={v.id}
                   className={`vp-card ${isLive ? "deployed" : isDeployedV ? "paused" : ""}`}>
                <div className="vp-card-top">
                  <span className="vp-label">{v.label}</span>
                  <span className={`vp-badge ${badge}`}>
                    {isLive ? "Deployed" : isDeployedV ? "Paused" : v.status}
                  </span>
                  <span className="vp-when">{fmtDate(v.created_at)}</span>
                </div>
                {v.notes && <p className="vp-notes">{v.notes}</p>}
                <div className="vp-chips">
                  {cfgChips(v.config).map(([k, val]) => (
                    <span className="vp-chip" key={k}>
                      <b>{k}</b> {String(val)}
                    </span>
                  ))}
                </div>
                <button type="button" onClick={() => toggleCfg(v.id)}
                        style={{ background: "none", border: "none",
                                 padding: "4px 0", cursor: "pointer",
                                 fontSize: 12, color: "#2563eb",
                                 fontWeight: 600 }}>
                  {openCfg[v.id] ? "▾ Hide full config" : "▸ Full config"}
                </button>
                {openCfg[v.id] && (
                  <table style={{ width: "100%", fontSize: 12,
                                  borderCollapse: "collapse",
                                  margin: "2px 0 6px" }}>
                    <tbody>
                      {configSections(v.config).map(([k, val]) => (
                        <tr key={k} style={{ borderTop: "1px solid #f1f5f9" }}>
                          <td style={{ fontWeight: 600, width: 84,
                                       padding: "5px 8px 5px 0",
                                       verticalAlign: "top",
                                       color: "#334155" }}>{k}</td>
                          <td style={{ padding: "5px 0",
                                       color: "#64748b" }}>{val}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <div className="vp-actions">
                  <button className="rag-btn rag-btn-sm"
                          onClick={() => onApply(v)}
                          disabled={deployed || !!busy}
                          title={deployed
                            ? "Deployed & live — pause the deployment first"
                            : "Load this config into the agent (no deploy)"}>
                    Load config
                  </button>
                  <button className="rag-btn rag-btn-sm rag-btn-blue"
                          onClick={() => onDeploy(v)}
                          disabled={isLive || !trainable || !!busy}
                          title={!trainable
                            ? "Train the agent before deploying"
                            : isDeployedV && !deployed
                              ? "Bring this version back online" : undefined}>
                    {isLive ? "Live"
                      : isDeployedV && !deployed ? "Re-deploy" : "Deploy"}
                  </button>
                  <button className="rag-btn rag-btn-sm rag-btn-red"
                          onClick={() => onDelete(v)}
                          disabled={isDeployedV || !!busy}
                          title={isDeployedV
                            ? "Can't delete the deployed version" : "Delete"}>
                    Delete
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
