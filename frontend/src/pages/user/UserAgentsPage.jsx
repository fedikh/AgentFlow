import React, { useState, useEffect, useRef } from "react";
import { listSpaces, queryRAG } from "../../services/ragApi";
import "../../styles/it/rag.css";

const UserAgentsPage = () => {
  const [agents, setAgents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [querying, setQuerying] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    loadAgents();
  }, []);
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);
  useEffect(() => {
    if (error) {
      const t = setTimeout(() => setError(""), 6000);
      return () => clearTimeout(t);
    }
  }, [error]);

  const loadAgents = async () => {
    try {
      const all = await listSpaces();
      const u = JSON.parse(localStorage.getItem("user") || "{}");
      const myDepts = u.departments?.map((x) => x.id) || [];

      if (u.role === "admin") {
        setAgents(all);
      } else {
        setAgents(all.filter((a) => myDepts.includes(a.department_id)));
      }
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
  const goBack = () => {
    setSelected(null);
    setChatHistory([]);
  };

  const fmt = (t) =>
    t
      ? t
          .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
          .replace(
            /^## (.+)$/gm,
            '<div style="font-size:15px;font-weight:600;margin:10px 0 4px">$1</div>',
          )
          .replace(
            /^### (.+)$/gm,
            '<div style="font-size:14px;font-weight:600;margin:8px 0 4px">$1</div>',
          )
          .replace(
            /^[•\-\*] (.+)$/gm,
            '<div style="padding-left:12px">• $1</div>',
          )
          .replace(/\n/g, "<br>")
      : "";

  const handleQuery = async () => {
    if (!question.trim() || !selected) return;
    const q = question;
    setQuestion("");
    setChatHistory((h) => [...h, { role: "user", content: q }]);
    setQuerying(true);
    try {
      const res = await queryRAG(selected.id, q);
      setChatHistory((h) => [
        ...h,
        { role: "assistant", content: res.answer, sources: res.sources },
      ]);
    } catch (e) {
      setChatHistory((h) => [
        ...h,
        {
          role: "assistant",
          content: "Sorry, something went wrong. Please try again.",
        },
      ]);
    } finally {
      setQuerying(false);
    }
  };

  if (loading)
    return (
      <div className="rag-page">
        <div className="rag-empty-state">Loading…</div>
      </div>
    );

  // ═══ PAGE 1: Agent cards ═══
  if (!selected)
    return (
      <div className="rag-page" style={{ display: "block" }}>
        <div className="rag-main">
          {error && <div className="rag-toast rag-toast-error">{error}</div>}

          <div className="rag-header">
            <div>
              <div className="rag-header-title">My AI Agents</div>
              <div className="rag-header-desc">
                Ask questions about your department's documents
              </div>
            </div>
          </div>

          {agents.length === 0 && (
            <div className="rag-empty-state" style={{ padding: 60 }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>🤖</div>
              <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>
                No agents available yet
              </div>
              <div style={{ fontSize: 13 }}>
                Your IT team hasn't deployed any AI agents for your department
                yet. Check back later!
              </div>
            </div>
          )}

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
              gap: 12,
            }}
          >
            {agents.map((a) => (
              <div
                key={a.id}
                className="rag-space-card"
                onClick={() => selectAgent(a)}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    marginBottom: 10,
                  }}
                >
                  <div style={{ fontSize: 28 }}>🤖</div>
                  <div>
                    <div className="rag-space-card-name">{a.name}</div>
                    <div className="rag-space-card-desc">
                      {a.description ||
                        "AI assistant powered by your documents"}
                    </div>
                  </div>
                </div>
                <div className="rag-space-card-footer">
                  <span>📄 {a.num_documents || 0} docs</span>
                  <span>🧩 {a.num_chunks || 0} chunks</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );

  // ═══ PAGE 2: Chat with agent ═══
  return (
    <div className="rag-page" style={{ display: "block" }}>
      <div className="rag-main">
        {error && <div className="rag-toast rag-toast-error">{error}</div>}

        <div className="rag-header">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button className="rag-btn rag-btn-sm" onClick={goBack}>
              ← Back
            </button>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 28 }}>🤖</span>
              <div>
                <div className="rag-header-title">{selected.name}</div>
                <div className="rag-header-desc">
                  {selected.description ||
                    "AI assistant powered by your documents"}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div
          style={{
            height: "calc(100vh - 160px)",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div className="rag-chat-messages" style={{ flex: 1 }}>
            {chatHistory.length === 0 && (
              <div className="rag-empty-state" style={{ padding: 60 }}>
                <div style={{ fontSize: 32, marginBottom: 12 }}>👋</div>
                <div style={{ fontSize: 15, marginBottom: 6 }}>
                  Hi! I'm your AI assistant for <strong>{selected.name}</strong>
                </div>
                <div style={{ fontSize: 13, color: "var(--text-3)" }}>
                  Ask me anything about the documents
                </div>
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
                    <div
                      style={{
                        marginTop: 10,
                        paddingTop: 8,
                        borderTop: "1px solid var(--border)",
                      }}
                    >
                      <div
                        style={{
                          fontSize: 11,
                          fontWeight: 600,
                          color: "var(--text-3)",
                          marginBottom: 4,
                        }}
                      >
                        📄 Sources
                      </div>
                      {m.sources.map((s, j) => (
                        <div
                          key={j}
                          style={{
                            fontSize: 11,
                            color: "var(--text-3)",
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
              placeholder="Type your question…"
              disabled={querying}
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
    </div>
  );
};

export default UserAgentsPage;
