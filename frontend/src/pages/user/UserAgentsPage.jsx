import React, { useState, useEffect } from "react";
import { listSpaces, queryRAG } from "../../services/ragApi";
import "../../styles/it/rag.css";

/**
 * End User Agents Page
 * Shows only ACTIVE RAG spaces from the user's departments.
 * Clean chat interface — no config pills, no upload, no delete, no debug.
 * Just pick an agent and ask questions.
 */
const UserAgentsPage = () => {
  const [agents, setAgents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Chat
  const [question, setQuestion] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [querying, setQuerying] = useState(false);

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    setLoading(true);
    try {
      const data = await listSpaces();
      // End user sees all spaces returned by the backend
      // (backend already filters by user's departments)
      setAgents(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const selectAgent = (agent) => {
    setSelected(agent);
    setChatHistory([]);
    setQuestion("");
  };

  // Format markdown
  const formatAnswer = (text) => {
    if (!text) return "";
    return text
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/^## (.+)$/gm, '<div class="rag-md-h2">$1</div>')
      .replace(/^### (.+)$/gm, '<div class="rag-md-h3">$1</div>')
      .replace(/^[•\-\*] (.+)$/gm, '<div class="rag-md-li">$1</div>')
      .replace(
        /^(\d+)\. (.+)$/gm,
        '<div class="rag-md-li"><span class="rag-md-num">$1.</span> $2</div>',
      )
      .replace(/\n/g, "<br>");
  };

  const handleQuery = async () => {
    if (!question.trim() || !selected) return;
    const q = question;
    setQuestion("");
    setChatHistory((prev) => [...prev, { role: "user", content: q }]);
    setQuerying(true);
    try {
      const res = await queryRAG(selected.id, q);
      setChatHistory((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, sources: res.sources },
      ]);
    } catch (e) {
      setChatHistory((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Sorry, something went wrong. Please try again.`,
        },
      ]);
    } finally {
      setQuerying(false);
    }
  };

  return (
    <div className="rag-page">
      <h1 className="rag-title">My AI Agents</h1>
      <p className="rag-sub">Ask questions about your department's documents</p>

      {error && (
        <div className="rag-error">
          {error}{" "}
          <span
            onClick={() => setError("")}
            style={{ cursor: "pointer", marginLeft: 8 }}
          >
            x
          </span>
        </div>
      )}

      {loading && <p style={{ color: "#9CA3AF", fontSize: 13 }}>Loading...</p>}

      {!loading && agents.length === 0 && (
        <div
          style={{
            textAlign: "center",
            padding: "60px 20px",
            color: "#6B7280",
          }}
        >
          <div style={{ fontSize: 48, marginBottom: 16 }}>🤖</div>
          <div
            style={{
              fontSize: 16,
              fontWeight: 600,
              color: "#374151",
              marginBottom: 6,
            }}
          >
            No agents available yet
          </div>
          <div style={{ fontSize: 13 }}>
            Your IT team hasn't deployed any AI agents for your department yet.
            Check back later!
          </div>
        </div>
      )}

      {!loading && agents.length > 0 && (
        <div className="rag-layout">
          {/* ── Left: agent cards ── */}
          <div className="rag-sidebar">
            <div className="rag-sidebar-header">
              <span className="rag-sidebar-title">Agents</span>
            </div>

            {agents.map((a) => (
              <div
                key={a.id}
                className={`rag-space-item ${selected?.id === a.id ? "active" : ""}`}
                onClick={() => selectAgent(a)}
                style={{ cursor: "pointer" }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 18 }}>🤖</span>
                  <div>
                    <div className="rag-space-name">{a.name}</div>
                    <div className="rag-space-meta">
                      {a.num_documents} document
                      {a.num_documents !== 1 ? "s" : ""}
                      {a.department_name && (
                        <span
                          style={{
                            marginLeft: 6,
                            fontSize: 10,
                            fontWeight: 500,
                            padding: "1px 5px",
                            borderRadius: 4,
                            background: "#F0FDF4",
                            color: "#166534",
                            border: "1px solid #BBF7D0",
                          }}
                        >
                          {a.department_name}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* ── Right: chat ── */}
          <div className="rag-main">
            {!selected ? (
              <div className="rag-placeholder">
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 48, marginBottom: 12 }}>💬</div>
                  <p style={{ color: "#6B7280", fontSize: 14 }}>
                    Select an agent to start chatting
                  </p>
                </div>
              </div>
            ) : (
              <>
                {/* Agent header — clean, no config pills */}
                <div className="rag-detail-header">
                  <div
                    style={{ display: "flex", alignItems: "center", gap: 10 }}
                  >
                    <span style={{ fontSize: 28 }}>🤖</span>
                    <div>
                      <h2 className="rag-detail-title">{selected.name}</h2>
                      <p className="rag-detail-desc">
                        {selected.description ||
                          "AI assistant powered by your documents"}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Chat — clean, no debug info */}
                <div className="rag-section" style={{ flex: 1 }}>
                  <div className="rag-chat-box" style={{ minHeight: 350 }}>
                    {chatHistory.length === 0 && (
                      <div className="rag-chat-empty">
                        <div style={{ fontSize: 20, marginBottom: 8 }}>👋</div>
                        Hi! I'm your AI assistant for{" "}
                        <strong>{selected.name}</strong>.
                        <br />
                        Ask me anything about the documents.
                      </div>
                    )}
                    {chatHistory.map((msg, i) => (
                      <div key={i} className={`rag-chat-msg ${msg.role}`}>
                        <div className="rag-chat-bubble">
                          <div
                            className="rag-md"
                            dangerouslySetInnerHTML={{
                              __html: formatAnswer(msg.content),
                            }}
                          />
                          {/* Sources — clean display, no raw scores */}
                          {msg.sources && msg.sources.length > 0 && (
                            <div
                              style={{
                                marginTop: 10,
                                paddingTop: 8,
                                borderTop: "1px solid #E5E7EB",
                              }}
                            >
                              <div
                                style={{
                                  fontSize: 11,
                                  fontWeight: 600,
                                  color: "#6B7280",
                                  marginBottom: 4,
                                }}
                              >
                                📄 Sources
                              </div>
                              {msg.sources.map((s, j) => (
                                <div
                                  key={j}
                                  style={{
                                    fontSize: 11,
                                    color: "#6B7280",
                                    padding: "2px 0",
                                  }}
                                >
                                  {s.document} — page {s.page}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                    {querying && (
                      <div className="rag-chat-msg assistant">
                        <div className="rag-chat-bubble rag-typing">
                          Thinking...
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="rag-chat-input">
                    <input
                      type="text"
                      placeholder="Type your question..."
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleQuery()}
                      disabled={querying}
                    />
                    <button
                      onClick={handleQuery}
                      disabled={querying || !question.trim()}
                    >
                      Send
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default UserAgentsPage;
