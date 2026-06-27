import React from "react";

const SIDE_STEPS = [
  { key: "uploads", label: "Uploads" },
  { key: "chunk", label: "Chunking" },
  { key: "embed", label: "Embeddings" },
  { key: "llm", label: "LLM Configuration" },
  { key: "retrieval", label: "Retrieval" },
  { key: "eval", label: "Evaluation" },
];

const RightSidebar = ({ panel, setPanel }) => (
  <div className="rag-side">
    <button
      className={`rag-side-flow ${panel === "flow" ? "active" : ""}`}
      onClick={() => setPanel("flow")}
    >
      View flow
    </button>
    <div className="rag-side-label">Configure</div>
    {SIDE_STEPS.map((step) => (
      <button
        key={step.key}
        className={`rag-side-item ${panel === step.key ? "active" : ""}`}
        onClick={() => setPanel(step.key)}
      >
        {step.label}
      </button>
    ))}
  </div>
);

export default RightSidebar;
