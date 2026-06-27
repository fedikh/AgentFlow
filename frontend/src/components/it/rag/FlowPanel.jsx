import React from "react";

const FLOW_NODES = [
  { key: "docs", label: "Documents", desc: "Upload" },
  { key: "chunk", label: "Chunking", desc: "Splitting" },
  { key: "embed", label: "Embedding", desc: "Vectorize" },
  { key: "llm", label: "LLM", desc: "Generate" },
  { key: "retrieval", label: "Retrieval", desc: "Search" },
  { key: "eval", label: "Evaluation", desc: "Scoring" },
];

const FlowPanel = ({ space }) => {
  const summary = (key) =>
    ({
      docs: `${space.num_documents || 0} docs`,
      chunk: `${space.chunk_strategy} · ${space.chunk_size}`,
      embed: (space.embedding_model || "—").split("/").pop(),
      llm: space.llm_model || space.llm_provider || "—",
      retrieval: `${Math.round((space.semantic_weight || 0.7) * 100)}% · top-${space.top_k}`,
      eval: "Not evaluated",
    })[key];

  return (
    <div className="rag-flow-panel">
      <div className="rag-flow-head">
        <div className="rag-flow-title">Pipeline</div>
        <div className="rag-flow-sub">
          How your documents move from upload to answer
        </div>
      </div>
      <div className="rag-flow-canvas">
        <div className="rag-flow-row">
          {FLOW_NODES.map((n, i) => (
            <React.Fragment key={n.key}>
              <div className="rag-flow-node">
                <div className="rag-flow-node-name">{n.label}</div>
                <div className="rag-flow-node-desc">{n.desc}</div>
                <div className="rag-flow-node-sum">{summary(n.key)}</div>
              </div>
              {i < FLOW_NODES.length - 1 && <div className="rag-flow-link" />}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  );
};

export default FlowPanel;
