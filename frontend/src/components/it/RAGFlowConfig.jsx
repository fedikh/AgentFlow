import React from "react";
import "../../styles/it/ragflow.css";
import { chunkSummary } from "./rag/pipelineConfig";

/**
 * RAGFlowConfig — view-only RAG pipeline flow (Langflow style).
 *
 * Just visualizes the pipeline as connected horizontal cards.
 * Configuration is done in the right sidebar of the space page,
 * so this is read-only — it shows the flow and a short summary per node.
 *
 * Props: space, onClose
 */

const NODES = [
  { key: "docs", label: "Documents", icon: "📄", desc: "Upload & parsing" },
  { key: "chunk", label: "Chunking", icon: "✂️", desc: "Text splitting" },
  { key: "embed", label: "Embedding", icon: "🔢", desc: "Vectorization" },
  { key: "llm", label: "LLM", icon: "🤖", desc: "Generation" },
  { key: "retrieval", label: "Retrieval", icon: "🔍", desc: "Hybrid search" },
  { key: "eval", label: "Evaluation", icon: "📊", desc: "Scoring" },
];

const RAGFlowConfig = ({ space, onClose }) => {
  const summary = (key) => {
    switch (key) {
      case "docs":
        return `${space.num_documents || 0} docs · ${space.num_chunks || 0} chunks`;
      case "chunk":
        return chunkSummary(space);
      case "embed":
        return (space.embedding_model || "—").split("/").pop();
      case "llm":
        return space.llm_model || space.llm_provider || "—";
      case "retrieval": {
        const mode = (space.retrieval_params || {}).search_mode || "hybrid";
        return `${mode} · top-${space.top_k}`;
      }
      case "eval":
        return "Not evaluated";
      default:
        return "";
    }
  };

  return (
    <div
      className="rf-overlay"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="rf-modal">
        <div className="rf-topbar">
          <div className="rf-topbar-left">
            <span className="rf-dot" />
            <div>
              <div className="rf-title">Pipeline flow</div>
              <div className="rf-subtitle">{space.name}</div>
            </div>
          </div>
          <div className="rf-topbar-right">
            <button className="rf-btn rf-btn-icon" onClick={onClose}>
              ✕
            </button>
          </div>
        </div>

        <div className="rf-flow-only">
          <div className="rf-flow-row">
            {NODES.map((n, i) => (
              <React.Fragment key={n.key}>
                <div className="rf-card">
                  <div className="rf-card-head">
                    <span className="rf-card-icon">{n.icon}</span>
                    <span className="rf-card-title">{n.label}</span>
                  </div>
                  <div className="rf-card-desc">{n.desc}</div>
                  <div className="rf-card-summary">{summary(n.key)}</div>
                  <div className="rf-card-port rf-port-in" />
                  <div className="rf-card-port rf-port-out" />
                </div>
                {i < NODES.length - 1 && (
                  <svg
                    className="rf-connector"
                    width="48"
                    height="120"
                    viewBox="0 0 48 120"
                  >
                    <path
                      d="M0 60 C 24 60, 24 60, 48 60"
                      fill="none"
                      stroke="var(--rf-line)"
                      strokeWidth="2"
                    />
                  </svg>
                )}
              </React.Fragment>
            ))}
          </div>
          <div className="rf-flow-hint">
            Configure each step from the right sidebar
          </div>
        </div>
      </div>
    </div>
  );
};

export default RAGFlowConfig;
