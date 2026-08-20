import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Database, Table2, X } from "lucide-react";
import { listDataSources } from "../../services/dataAgentApi";
import DataChat from "../../components/it/dataagent/DataChat";
import { btn, dialectLabel } from "../../components/it/dataagent/ui";
import { card, ink } from "../../components/dashboard/tokens";
import "../../styles/it/spacesgrid.css";

/*
 * Deployed Data Agents — the consumption page (mirrors RAG deployed agents).
 * Shared by the IT preview and the end-user page: the backend already
 * role-scopes the list (end users only see DEPLOYED agents of their
 * department they're authorized on).
 *
 * The open agent lives in the URL (basePath/:sourceId), so a conversation can
 * be bookmarked, shared and reopened with the browser Back button — the same
 * deep-linking the workspace page uses.
 */
const DeployedDataAgentsPage = ({
  title = "Deployed Data Agents",
  subtitle = "Ask your enterprise databases in plain language",
  basePath = "/it/data-agent/deployed",
}) => {
  const { sourceId } = useParams();
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listDataSources()
      .then((all) => setRows(all.filter((s) => s.status === "deployed")))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Derived from the URL — never mirrored into state, so a deep link, a Back
  // button and a card click all end up in exactly the same place.
  const selected = sourceId ? rows.find((s) => s.id === sourceId) : null;
  const openAgent = (s) => navigate(`${basePath}/${s.id}`);
  const goBack = () => navigate(basePath);

  if (loading) return <div style={{ ...card, color: ink.muted }}>Loading…</div>;

  /* deep link to an agent that is gone, unpublished, or not shared with you */
  if (sourceId && !selected) {
    return (
      <div style={{ ...card, textAlign: "center", padding: 40, color: ink.muted }}>
        <Database size={26} />
        <div style={{ fontWeight: 700, marginTop: 8, color: ink.primary }}>
          This data agent isn&apos;t available
        </div>
        <div style={{ fontSize: 12.5, margin: "4px 0 14px" }}>
          It may have been undeployed, or you may not have access to it.
        </div>
        <button onClick={goBack}
                style={{ ...btn(false), borderColor: ink.line, color: ink.primary }}>
          <ArrowLeft size={14} /> Back to agents
        </button>
      </div>
    );
  }

  /* chat view */
  if (selected) {
    return (
      <div style={{ display: "grid", gap: 14 }}>
        <div style={{ ...card, display: "flex", alignItems: "center", gap: 12, padding: "12px 16px" }}>
          <button onClick={goBack}
                  style={{ ...btn(false), borderColor: ink.line, color: ink.primary }}>
            <ArrowLeft size={14} /> Back
          </button>
          <span style={{ width: 40, height: 40, borderRadius: 11, background: ink.primary, color: "#fff", display: "grid", placeItems: "center", flexShrink: 0 }}>
            <Database size={17} />
          </span>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 800, fontSize: 15.5, color: ink.primary }}>{selected.name}</div>
            <div style={{ fontSize: 12, color: ink.muted, display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#22C55E", flexShrink: 0 }} />
              {selected.description || `${dialectLabel(selected.dialect)} · every answer shows its SQL`}
            </div>
          </div>
        </div>
        {error && (
          <div style={{ ...card, color: "#B91C1C", display: "flex", justifyContent: "space-between" }}>
            <span>{error}</span>
            <button onClick={() => setError("")} style={{ border: "none", background: "none", cursor: "pointer" }}><X size={14} /></button>
          </div>
        )}
        <DataChat source={selected} setError={setError} withHistory
                  height="calc(100vh - 240px)"
                  placeholder="Ask a question about this data…" />
      </div>
    );
  }

  /* grid view */
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 800, color: ink.primary, letterSpacing: "-0.3px", margin: 0 }}>
          {title}
        </h1>
        <p style={{ fontSize: 13, color: ink.muted, margin: "3px 0 0" }}>{subtitle}</p>
      </div>
      {error && <div style={{ ...card, color: "#B91C1C" }}>{error}</div>}
      {rows.length === 0 ? (
        <div style={{ ...card, textAlign: "center", padding: 40, color: ink.muted }}>
          <Database size={26} />
          <div style={{ fontWeight: 700, marginTop: 8, color: ink.primary }}>No deployed data agents yet</div>
          <div style={{ fontSize: 12.5, marginTop: 4 }}>
            Agents appear here once your IT team deploys them.
          </div>
        </div>
      ) : (
        <div className="sg-grid">
          {rows.map((s) => (
            <button key={s.id} className="sg-card" onClick={() => openAgent(s)}>
              <div className="sg-card-head">
                <span className="sg-mono"><Database size={16} /></span>
                <div className="sg-card-titles">
                  <div className="sg-name-row"><div className="sg-card-name">{s.name}</div></div>
                </div>
                <span className="sg-status-wrap">
                  <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 9px", borderRadius: 20, background: "#F0FDF4", color: "#166534" }}>
                    ONLINE
                  </span>
                </span>
              </div>
              <div className="sg-card-desc">
                {s.description || "Ask questions in plain language — the agent writes the SQL."}
              </div>
              <div className="sg-card-foot">
                <span className="sg-stat"><Table2 size={13} /> {s.table_count || 0} tables</span>
                <span className="sg-stat">{dialectLabel(s.dialect)}</span>
                <span className="sg-open">→</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default DeployedDataAgentsPage;
