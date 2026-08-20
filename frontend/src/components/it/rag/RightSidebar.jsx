import React from "react";

/*
 * Right sidebar — the configuration journey as a proper stepper.
 *
 * Ordered by USER JOURNEY, not by data flow: "Process" (in Chunking & Indexing)
 * executes chunk + embed + store at once, so the embedding model must be chosen
 * BEFORE the panel that holds the Process button.
 *
 * Each step shows a live hint of its current state (docs count, chosen models,
 * chunk count, top-k) so the whole pipeline is readable at a glance.
 */

// "BAAI/bge-m3" → "bge-m3", clipped so hints never wrap.
const shortModel = (m) => {
  if (!m) return "";
  const tail = String(m).split("/").pop();
  return tail.length > 20 ? tail.slice(0, 19) + "…" : tail;
};

const RightSidebar = ({ panel, setPanel, space = null, docsCount = null }) => {
  const hints = {
    uploads:
      docsCount != null
        ? `${docsCount} document${docsCount === 1 ? "" : "s"}`
        : "Documents & sources",
    embed: shortModel(space?.embedding_model) || "Vector model",
    chunk:
      space?.num_chunks > 0
        ? `${space.num_chunks} chunks indexed`
        : "Split & build the index",
    llm: shortModel(space?.llm_model) || "Answer model",
    retrieval: space?.top_k
      ? `top-k ${space.top_k} · ${(space.retrieval_params?.search_mode || "hybrid").toLowerCase()}`
      : "Search settings",
  };

  const STEPS = [
    { key: "uploads", label: "Uploads" },
    { key: "embed", label: "Embeddings" },
    { key: "chunk", label: "Chunking & Indexing" },
    { key: "llm", label: "LLM Configuration" },
    { key: "retrieval", label: "Retrieval" },
  ];
  const MANAGE = [
    { key: "eval", label: "Evaluation", hint: "Test answer quality" },
    { key: "versions", label: "Versions", hint: "Snapshots & deploy" },
  ];

  return (
    <div className="rag-side">
      <button
        className={`rag-side-flow ${panel === "flow" ? "active" : ""}`}
        onClick={() => setPanel("flow")}
      >
        View flow
      </button>

      <div className="rag-side-eyebrow">Pipeline</div>
      <div className="rag-steps">
        {STEPS.map((s, i) => (
          <button
            key={s.key}
            className={`rag-step ${panel === s.key ? "active" : ""}`}
            onClick={() => setPanel(s.key)}
          >
            <span className="rag-step-badge">{i + 1}</span>
            <span className="rag-step-txt">
              <span className="rag-step-name">{s.label}</span>
              <span className="rag-step-hint">{hints[s.key]}</span>
            </span>
          </button>
        ))}
      </div>

      <div className="rag-side-eyebrow" style={{ marginTop: 18 }}>Manage</div>
      <div className="rag-steps rag-steps-manage">
        {MANAGE.map((s) => (
          <button
            key={s.key}
            className={`rag-step ${panel === s.key ? "active" : ""}`}
            onClick={() => setPanel(s.key)}
          >
            <span className="rag-step-badge rag-step-badge-dot" />
            <span className="rag-step-txt">
              <span className="rag-step-name">{s.label}</span>
              <span className="rag-step-hint">{s.hint}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
};

export default RightSidebar;
