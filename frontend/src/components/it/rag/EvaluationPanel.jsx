import React from "react";
import "../../../styles/it/chat.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

// Same lightweight markdown as the old chat modal (bold + line breaks).
const fmt = (t) =>
  t
    ? t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>")
    : "";

const IcSend = () => (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
    <path
      d="M12 19V5M6 11l6-6 6 6"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const SUGGESTS = [
  "Summarize the documents",
  "What are the key points?",
  "Give an example from the data",
];

/**
 * EvaluationPanel — manual test chat.
 *
 * A tool to test a space's config quality: ask a question, read the answer and
 * inspect the retrieved sources. Uses the same query backend (queryRAG) via the
 * handlers passed from RAGSpacesPage.
 */
const EvaluationPanel = ({
  chatHistory = [],
  chatEndRef,
  question,
  setQuestion,
  querying,
  handleQuery,
}) => {
  return (
    <div className="rag-cfg-panel">
      <div className="rag-cfg-head">
        <div className="rag-cfg-title">Evaluation</div>
      </div>

      <div className="rag-cfg-hint">
        Manually test this space's configuration: ask a question, then check the
        answer and the sources it retrieved — a quick way to judge whether your
        chunking, embedding, LLM and retrieval settings give good results.
      </div>

      <div className="cx-eval">
        <div className="cx-stream">
          {chatHistory.length === 0 && (
            <div className="cx-empty">
              <div className="cx-empty-ic">🧪</div>
              <div className="cx-empty-t">Test this space</div>
              <div className="cx-empty-s">
                Ask a question to see the generated answer and the exact chunks
                it retrieved.
              </div>
              <div className="cx-suggests">
                {SUGGESTS.map((s) => (
                  <button
                    key={s}
                    className="cx-suggest"
                    onClick={() => handleQuery(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {chatHistory.map((m, i) => (
            <div key={i} className={`cx-row ${m.role === "user" ? "me" : ""}`}>
              <span className={`cx-avatar ${m.role === "user" ? "me" : "ai"}`}>
                {m.role === "user" ? "🧑" : "🤖"}
              </span>
              <div className={`cx-bubble ${m.role === "user" ? "me" : "ai"}`}>
                {m.role === "user" ? (
                  m.content
                ) : (
                  <div dangerouslySetInnerHTML={{ __html: fmt(m.content) }} />
                )}
                {m.sources?.length > 0 && (
                  <div className="cx-sources">
                    <div className="cx-sources-t">
                      Retrieved sources · {m.sources.length}
                    </div>
                    <div className="cx-source-list">
                      {m.sources.map((s, j) => (
                        <span key={j} className="cx-source" title={s.document}>
                          {s.type === "image" ? "🖼️" : "📄"} {s.document} · p.
                          {s.page}
                          {s.score != null ? ` · ${s.score}` : ""}
                        </span>
                      ))}
                    </div>
                    {m.sources
                      .filter((s) => s.type === "image" && s.image_url)
                      .map((s, j) => (
                        <img
                          key={`img-${j}`}
                          src={`${API_BASE}${s.image_url}`}
                          alt={`Source p.${s.page}`}
                          style={{
                            display: "block",
                            marginTop: 8,
                            maxWidth: 220,
                            maxHeight: 170,
                            objectFit: "contain",
                            borderRadius: 8,
                            border: "1px solid #e2e8f0",
                            background: "#f8fafc",
                          }}
                          onError={(e) => {
                            e.target.style.display = "none";
                          }}
                        />
                      ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {querying && (
            <div className="cx-row">
              <span className="cx-avatar ai">🤖</span>
              <div className="cx-typing">
                <span className="cx-dot" />
                <span className="cx-dot" />
                <span className="cx-dot" />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="cx-composer">
          <input
            className="cx-input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleQuery()}
            placeholder="Ask a question to test this space…"
            disabled={querying}
          />
          <button
            className="cx-send"
            onClick={() => handleQuery()}
            disabled={querying || !question.trim()}
            aria-label="Send"
          >
            <IcSend />
          </button>
        </div>
      </div>
    </div>
  );
};

export default EvaluationPanel;
