import React, { useState, useEffect, useRef } from "react";
import { listSpaces, queryRAG, listPublicDocuments } from "../../services/ragApi";
import DocViewerModal from "../user/DocViewerModal";
import "../../styles/it/rag.css";
import "../../styles/user/userAgents.css";
import "../../styles/it/chat.css";

const fmtSize = (b) => {
  if (!b) return "";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
};

const SUGGESTS = [
  "Give me a summary",
  "What topics are covered?",
  "List the key points",
];

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

const meInitials = (() => {
  try {
    const u = JSON.parse(localStorage.getItem("user") || "{}");
    const n = (u.name || u.email || "U").trim();
    const p = n.split(/\s+/);
    return (p.length >= 2 ? p[0][0] + p[1][0] : n.slice(0, 2)).toUpperCase();
  } catch {
    return "U";
  }
})();

/**
 * AgentsExperience — the deployed-agent chat + documents view.
 *
 * Shared by the end-user page and the IT "Deployed Agents" preview so both show
 * the exact same experience. When `onlyDeployed` is set (IT preview), the agent
 * list is filtered to ACTIVE spaces (IT's list includes drafts too).
 */
const AgentsExperience = ({
  title = "My AI Agents",
  subtitle = "Ask questions about your department's documents",
  emptyText = "No agents available yet.",
  onlyDeployed = false,
}) => {
  const [agents, setAgents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [querying, setQuerying] = useState(false);
  const [docs, setDocs] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [viewerDoc, setViewerDoc] = useState(null);
  const chatEndRef = useRef(null);

  useEffect(() => {
    loadAgents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      let all = await listSpaces();
      if (onlyDeployed) all = all.filter((a) => a.status === "ACTIVE");
      setAgents(all);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const selectAgent = async (agent) => {
    setSelected(agent);
    setChatHistory([]);
    setQuestion("");
    setDocs([]);
    if (agent.status === "EDITING") return; // offline for updates — skip docs
    setLoadingDocs(true);
    try {
      setDocs(await listPublicDocuments(agent.id));
    } catch (e) {
      /* documents optional — chat still works */
    } finally {
      setLoadingDocs(false);
    }
  };
  const goBack = () => {
    setSelected(null);
    setChatHistory([]);
    setDocs([]);
    setViewerDoc(null);
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
          .replace(/^[•\-\*] (.+)$/gm, '<div style="padding-left:12px">• $1</div>')
          .replace(/\n/g, "<br>")
      : "";

  const handleQuery = async (preset) => {
    const q = (typeof preset === "string" ? preset : question).trim();
    if (!q || !selected || querying) return;
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
              <div className="rag-header-title">{title}</div>
              <div className="rag-header-desc">{subtitle}</div>
            </div>
          </div>

          {agents.length === 0 ? (
            <div className="rag-empty-state" style={{ padding: 60 }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>🤖</div>
              <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>
                No agents available yet
              </div>
              <div style={{ fontSize: 13 }}>{emptyText}</div>
            </div>
          ) : (
            <div className="ua-grid">
              {agents.map((a) => (
                <button
                  key={a.id}
                  className="ua-card"
                  onClick={() => selectAgent(a)}
                >
                  <div className="ua-card-top">
                    <div className="ua-avatar">🤖</div>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div className="ua-card-name">{a.name}</div>
                    </div>
                    {a.status === "EDITING" && (
                      <span className="ua-badge-editing">Updating…</span>
                    )}
                  </div>
                  <div className="ua-card-desc">
                    {a.description || "AI assistant powered by your documents"}
                  </div>
                  <div className="ua-card-foot">
                    <span>📄 {a.num_documents || 0} docs</span>
                    <span>🧩 {a.num_chunks || 0} chunks</span>
                    <span className="ua-cta">Open →</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    );

  // ═══ PAGE 2: Chat with agent + documents ═══
  const editing = selected.status === "EDITING";
  return (
    <div className="chat-page">
      {error && <div className="rag-toast rag-toast-error">{error}</div>}

      <div className="chat-header">
        <div className="chat-header-left">
          <button className="rag-btn rag-btn-sm" onClick={goBack}>
            ← Back
          </button>
          <span className="chat-agent-av">🤖</span>
          <div style={{ minWidth: 0 }}>
            <div className="chat-agent-name">{selected.name}</div>
            <div className="chat-agent-desc">
              {selected.description || "AI assistant powered by your documents"}
            </div>
          </div>
        </div>
      </div>

      {editing ? (
        <div className="chat-body">
          <div className="cx-empty">
            <div className="cx-empty-ic">🛠️</div>
            <div className="cx-empty-t">This agent is being updated</div>
            <div className="cx-empty-s">
              Your IT team is making changes. Please check back soon.
            </div>
          </div>
        </div>
      ) : (
        <div className="chat-body">
          {/* Chat column */}
          <div className="chat-main">
            <div className="cx-stream">
              {chatHistory.length === 0 && (
                <div className="cx-empty">
                  <div className="cx-empty-ic">🤖</div>
                  <div className="cx-empty-t">Chat with {selected.name}</div>
                  <div className="cx-empty-s">
                    Ask anything about this agent's documents — I'll answer and
                    cite the sources I used.
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
                <div
                  key={i}
                  className={`cx-row ${m.role === "user" ? "me" : ""}`}
                >
                  <span
                    className={`cx-avatar ${m.role === "user" ? "me" : "ai"}`}
                  >
                    {m.role === "user" ? meInitials : "🤖"}
                  </span>
                  <div
                    className={`cx-bubble ${m.role === "user" ? "me" : "ai"}`}
                  >
                    {m.role === "user" ? (
                      m.content
                    ) : (
                      <div
                        dangerouslySetInnerHTML={{ __html: fmt(m.content) }}
                      />
                    )}
                    {m.sources?.length > 0 && (
                      <div className="cx-sources">
                        <div className="cx-sources-t">Sources</div>
                        <div className="cx-source-list">
                          {m.sources.map((s, j) => (
                            <span key={j} className="cx-source" title={s.document}>
                              📄 {s.document} · p.{s.page}
                            </span>
                          ))}
                        </div>
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
                placeholder="Ask a question…"
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

          {/* Documents sidebar */}
          <aside className="ua-docs">
            <div className="ua-docs-head">
              📚 Documents
              <span
                style={{ marginLeft: "auto", color: "#94a3b8", fontWeight: 500 }}
              >
                {docs.length}
              </span>
            </div>
            <div className="ua-docs-list">
              {loadingDocs && <div className="ua-docs-empty">Loading…</div>}
              {!loadingDocs && docs.length === 0 && (
                <div className="ua-docs-empty">No documents to preview.</div>
              )}
              {!loadingDocs &&
                docs.map((d) => (
                  <button
                    key={d.id}
                    className="ua-doc"
                    onClick={() => setViewerDoc(d)}
                    title={`Open ${d.file_name}`}
                  >
                    <span className="ua-doc-ic">
                      {(d.file_type || "").toLowerCase() === "pdf" ? "📕" : "📄"}
                    </span>
                    <span className="ua-doc-txt">
                      <span className="ua-doc-name">{d.file_name}</span>
                      <span className="ua-doc-meta">
                        {(d.file_type || "file").toUpperCase()}
                        {d.file_size ? ` · ${fmtSize(d.file_size)}` : ""}
                      </span>
                    </span>
                  </button>
                ))}
            </div>
          </aside>
        </div>
      )}

      {viewerDoc && (
        <DocViewerModal
          spaceId={selected.id}
          doc={viewerDoc}
          onClose={() => setViewerDoc(null)}
        />
      )}
    </div>
  );
};

export default AgentsExperience;
