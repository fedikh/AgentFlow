import React, { useEffect, useRef, useState } from "react";
import { listProviders } from "../../../services/providersApi";
import ProviderLogo from "../../ProviderLogo";
import { embSource, llmSource, useEffectiveModels } from "../rag/pipelineConfig";
import { dialectLabel } from "./ui";
import StatusBadge from "./StatusBadge";
import "../../../styles/it/flowview.css";

/**
 * DataFlowPanel — the Data Agent "View flow" page, in the exact RAG FlowPanel
 * format (same flowview.css classes, same interactions):
 *   1. A horizontal pipeline rail (Connection → … → Answer).
 *   2. Detail cards showing HOW each stage works and the exact config saved.
 * Clicking a node highlights and scrolls to its detail card.
 */
const num = (i) => String(i + 1).padStart(2, "0");

/* Ordered sections for a data agent. Same shape as the RAG ones:
 * { key, accent, tag, title, how, family?, summary, rows:[[k,v]] } */
function buildAgentSections(source, providers, eff) {
  const rp = source.retrieval || {};
  const gen = source.generation || {};
  const llm = llmSource(source, providers);
  const emb = embSource(source, providers);
  const llmModel = eff.llm || source.llm_model || "Not set";
  const embModel = (eff.emb || source.embedding_model || "BAAI/bge-m3")
    .split("/").pop();
  const topK = `${rp.n_ddl ?? 10} / ${rp.n_sql ?? 5} / ${rp.n_business ?? 8}`;

  return [
    {
      key: "connection",
      accent: "#64748b",
      tag: "Database",
      title: "Connection",
      how: "Every query runs over this connection with a read-only user — the agent can only SELECT, so a bad query can never touch the data.",
      summary: `${dialectLabel(source.dialect)} · ${source.database || "—"}`,
      rows: [
        ["Dialect", dialectLabel(source.dialect)],
        ["Host", `${source.host || "—"}${source.port ? `:${source.port}` : ""}`],
        ["Database", source.database || "—"],
        ["Read-only user", source.username || "—"],
      ],
    },
    {
      key: "schema",
      accent: "#0ea5e9",
      tag: "Introspect",
      title: "Schema & Training",
      how: "Introspection reads tables, columns, keys and comments. You curate which tables the agent may see, then training writes them into its knowledge indexes.",
      summary: `${source.table_count || 0} tables · ${source.mode} mode`,
      rows: [
        ["Tables", source.table_count || 0],
        ["Mode", source.mode === "base"
          ? "base · full schema in prompt"
          : "rag · vector retrieval"],
        ["Last introspected", (source.last_introspected_at || "—").split("T")[0] || "—"],
      ],
    },
    {
      key: "knowledge",
      accent: "#8b5cf6",
      tag: "Vectorize",
      title: "Knowledge indexes",
      family: emb.family,
      how: "Three separate indexes are embedded into pgvector: table DDL, verified Prompt→SQL examples, and business knowledge (glossary + documents). Kept apart so 30 DDL blocks can never crowd 3 glossary entries out of the prompt.",
      summary: embModel,
      rows: [
        ["Embedding source", emb.label],
        ["Model", embModel],
        ["Dimensions", eff.embDim ? `${eff.embDim}d` : "—"],
        ["Indexes", "DDL · Prompt→SQL · Business"],
        ["Knowledge docs", source.knowledge_space_id ? "Linked RAG space" : "None"],
      ],
    },
    {
      key: "retrieval",
      accent: "#10b981",
      tag: "Search",
      title: "Retrieval",
      how: "Each question searches the three indexes in hybrid mode — vector (business meaning) and keyword (exact table / column names) merged by Reciprocal Rank Fusion — then re-ranked by a cross-encoder.",
      summary: `Hybrid · top-k ${topK}`,
      rows: [
        ["Search mode", "Hybrid (locked)"],
        ["Query enhancement", rp.transform_enabled === false ? "Off" : "On"],
        ["Top-K (DDL / SQL / Business)", topK],
        ["Re-rank",
          `${rp.reranker_provider === "voyage" ? "rerank-2.5" : "BGE v2-m3"} · top ${rp.rerank_top_n ?? 10}`],
        ["RRF k", rp.rrf_k ?? 60],
      ],
    },
    {
      key: "generate",
      accent: "#2563eb",
      tag: "Generate",
      title: "SQL generation",
      family: llm.family,
      how: "The LLM writes one SELECT from the retrieved context, inside a LangGraph loop: if validation or execution fails, the error is fed back and it retries — up to 3 attempts.",
      summary: llmModel,
      rows: [
        ["Source", llm.label],
        ["Model", llmModel],
        ["Temperature", gen.temperature ?? 0],
        ["Max tokens", gen.max_tokens ?? 2000],
        ["Retry cap", "3 attempts (LangGraph)"],
      ],
    },
    {
      key: "guard",
      accent: "#f59e0b",
      tag: "Protect",
      title: "Validation & execution",
      how: "Before running, the SQL is parsed with sqlglot (a real parser, not regex): SELECT-only, schema allow-list, automatic LIMIT injection. Then it executes with the saved timeout.",
      summary: `SELECT-only · LIMIT ${source.row_limit ?? 1000}`,
      rows: [
        ["Validator", "sqlglot AST"],
        ["Statements", "SELECT only"],
        ["Row cap", source.row_limit ?? 1000],
        ["Timeout", `${source.timeout_ms ?? 30000} ms`],
        ["On failure", "Error fed back → retry"],
      ],
    },
    {
      key: "answer",
      accent: "#ec4899",
      tag: "Respond",
      title: "Answer",
      how: "The user gets the result table plus the exact SQL — always shown, never hidden. Sending rows back to the LLM for a natural-language summary is opt-in, so data leaves the database only if you allow it.",
      summary: gen.send_results_to_llm ? "Rows + LLM summary" : "Rows + SQL only",
      rows: [
        ["SQL shown", "Always"],
        ["Rows sent to LLM", gen.send_results_to_llm ? "Yes (summary)" : "No"],
        ["Visibility", source.is_private ? "Private" : "Department"],
        ["Authorization", (source.allowed_user_ids || []).length
          ? `${source.allowed_user_ids.length} allowed user(s)`
          : "Open to the department"],
      ],
    },
  ];
}

const DataFlowPanel = ({ source }) => {
  const [providers, setProviders] = useState([]);
  const [active, setActive] = useState(null);
  const cardRefs = useRef({});
  const eff = useEffectiveModels(source);

  useEffect(() => {
    listProviders()
      .then(setProviders)
      .catch(() => setProviders([]));
  }, []);

  if (!source) return null;
  const sections = buildAgentSections(source, providers, eff);

  const focus = (key) => {
    setActive(key);
    cardRefs.current[key]?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  };

  return (
    <div className="pf">
      <div className="pf-head">
        <div>
          <div className="pf-title">Pipeline</div>
          <div className="pf-sub">
            How a question becomes a safe SQL answer — every stage and the
            exact configuration saved for <strong>{source.name}</strong>.
          </div>
        </div>
        <StatusBadge status={source.status} />
      </div>

      {/* ── Flow rail ── */}
      <div className="pf-rail-wrap">
        <div className="pf-rail">
          {sections.map((s, i) => (
            <React.Fragment key={s.key}>
              <button
                type="button"
                className={`pf-step ${active === s.key ? "active" : ""}`}
                style={{ "--accent": s.accent }}
                onClick={() => focus(s.key)}
              >
                <span className="pf-step-top">
                  <span className="pf-step-num">{num(i)}</span>
                  <span className="pf-step-dot" />
                </span>
                <span className="pf-step-tag">{s.tag}</span>
                <span className="pf-step-title">{s.title}</span>
                <span className="pf-step-sum">
                  {s.family && <ProviderLogo family={s.family} size={13} />}
                  <span className="pf-step-sum-t">{s.summary}</span>
                </span>
              </button>
              {i < sections.length - 1 && <span className="pf-rail-line" />}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* ── Detail cards ── */}
      <div className="pf-cards">
        {sections.map((s, i) => (
          <div
            key={s.key}
            ref={(el) => (cardRefs.current[s.key] = el)}
            className={`pf-card ${active === s.key ? "active" : ""}`}
            style={{ "--accent": s.accent }}
          >
            <div className="pf-card-head">
              <span className="pf-card-eyebrow">
                <span className="pf-card-num">{num(i)}</span>
                <span className="pf-card-tag">{s.tag}</span>
              </span>
              {s.family && (
                <span className="pf-card-logo">
                  <ProviderLogo family={s.family} size={18} />
                </span>
              )}
            </div>
            <div className="pf-card-title">{s.title}</div>
            <div className="pf-card-how">{s.how}</div>
            <dl className="pf-rows">
              {s.rows.map(([k, v]) => (
                <div className="pf-row" key={k}>
                  <dt className="pf-row-k">{k}</dt>
                  <dd className="pf-row-v">{String(v)}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </div>
  );
};

export default DataFlowPanel;
