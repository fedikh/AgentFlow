import React from "react";

const API_BASE =
  import.meta.env.VITE_API_URL || "http://localhost:8000/api";

// Same lightweight markdown as the old chat modal (bold + line breaks).
const fmt = (t) =>
  t
    ? t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>")
    : "";

/**
 * EvaluationPanel — manual test chat (Batch 4).
 *
 * The chat used to live inside the document modal. It now lives here, in the
 * Evaluation section, as a manual tool to test a space's config quality: ask a
 * question, read the answer and inspect the retrieved sources. Uses the same
 * query backend (queryRAG) via the handlers passed from RAGSpacesPage.
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
        answer and the sources it retrieved. Use it to judge whether your
        chunking, embedding, LLM and retrieval settings give good results.
      </div>

      <div
        className="rag-chat-body"
        style={{
          marginTop: 12,
          height: "calc(100vh - 320px)",
          minHeight: 320,
        }}
      >
        <div className="rag-chat-messages" style={{ minHeight: 0 }}>
          {chatHistory.length === 0 && (
            <div className="rag-empty-state">
              Ask a question to test this space
            </div>
          )}
          {chatHistory.map((m, i) => (
            <div
              key={i}
              className={`rag-chat-msg ${m.role === "user" ? "rag-chat-msg-user" : "rag-chat-msg-ai"}`}
            >
              <div
                className={`rag-chat-bubble ${m.role === "user" ? "rag-chat-bubble-user" : "rag-chat-bubble-ai"}`}
              >
                {m.role === "user" ? (
                  m.content
                ) : (
                  <div dangerouslySetInnerHTML={{ __html: fmt(m.content) }} />
                )}
                {m.sources?.length > 0 && (
                  <div className="rag-chat-sources">
                    {m.sources.map((s, j) => (
                      <div key={j} style={{ marginBottom: s.type === "image" ? 8 : 0 }}>
                        {s.type === "image" ? "🖼️" : "📄"} {s.document} (p.
                        {s.page}, {s.score})
                        {s.type === "image" && s.image_url && (
                          <div style={{ marginTop: 4 }}>
                            <img
                              src={`${API_BASE}${s.image_url}`}
                              alt={`Source image p.${s.page}`}
                              style={{
                                maxWidth: 220,
                                maxHeight: 180,
                                objectFit: "contain",
                                borderRadius: 8,
                                background: "#F8FAFC",
                                border: "1px solid #E2E8F0",
                                display: "block",
                              }}
                              onError={(e) => {
                                e.target.style.display = "none";
                              }}
                            />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {querying && (
            <div className="rag-chat-msg rag-chat-msg-ai">
              <div className="rag-chat-typing">Thinking…</div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="rag-chat-input-bar">
          <input
            className="rag-chat-input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleQuery()}
            placeholder="Ask a question to test this space…"
          />
          <button
            className="rag-chat-send"
            onClick={handleQuery}
            disabled={querying || !question.trim()}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
};

export default EvaluationPanel;
