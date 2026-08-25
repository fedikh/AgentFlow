import React, { useState, useEffect, useRef, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  listSpaces,
  listPublicDocuments,
  listChatSessions,
  getChatSession,
  sendChatMessage,
  updateChatSession,
  deleteChatSession,
} from "../../services/ragApi";
import DocViewerModal from "../user/DocViewerModal";
import AnswerBody from "./AnswerBody";
import {
  Archive,
  ArrowLeft,
  Bot,
  FileText,
  MessageSquare,
  Pencil,
  Plus,
  Search,
  Send,
  Trash2,
  X,
} from "lucide-react";
import "../../styles/it/rag.css";
import "../../styles/it/spacesgrid.css";
import "../../styles/user/userAgents.css";
import "../../styles/user/agentChat.css";

/* ── same icons as the RAG workspace grid ── */
const IcDoc = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
    <path d="M14 3v5h5M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-5Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
  </svg>
);
const IcLayers = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
    <path d="M12 2 2 7l10 5 10-5-10-5ZM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
  </svg>
);
const IcArrow = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
    <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const monoInitial = (name = "?") => name.trim().charAt(0).toUpperCase() || "?";

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

const timeAgo = (iso) => {
  if (!iso) return "";
  const d = new Date(String(iso).replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return "";
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return "now";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
};

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
 * the exact same experience (same design system as the RAG workspace). When
 * `onlyDeployed` is set (IT preview), the agent list is filtered to ACTIVE.
 */
const AgentsExperience = ({
  title = "My AI Agents",
  subtitle = "Ask questions about your department's documents",
  emptyText = "No agents available yet.",
  onlyDeployed = false,
  basePath = "/user/agents",
}) => {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const [agents, setAgents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [agentSearch, setAgentSearch] = useState("");
  const [question, setQuestion] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [querying, setQuerying] = useState(false);
  const [docs, setDocs] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [docSearch, setDocSearch] = useState("");
  const [showDocs, setShowDocs] = useState(false);   // panel hidden by default
  const [viewerDoc, setViewerDoc] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [loadingChat, setLoadingChat] = useState(false);
  const [renamingId, setRenamingId] = useState(null);
  const [renameVal, setRenameVal] = useState("");
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
    setDocSearch("");
    setSessions([]);
    setSessionId(null);
    setRenamingId(null);
    if (agent.status === "EDITING") return; // offline for updates — skip docs
    setLoadingDocs(true);
    try {
      setDocs(await listPublicDocuments(agent.id));
    } catch {
      /* documents optional — chat still works */
    } finally {
      setLoadingDocs(false);
    }
    // conversation history — reopen the most recent one for continuity
    try {
      const list = await listChatSessions(agent.id);
      setSessions(list);
      if (list.length > 0) openSession(list[0]);
    } catch {
      /* chat history optional — a fresh chat still works */
    }
  };

  /* ── persistent conversations ── */
  const openSession = async (s) => {
    setSessionId(s.id);
    setChatHistory([]);
    setLoadingChat(true);
    try {
      const res = await getChatSession(s.id);
      setChatHistory(
        (res.messages || []).map((m) => ({
          role: m.role,
          content: m.content,
          sources: m.sources,
        })),
      );
    } catch {
      setChatHistory([]);
    } finally {
      setLoadingChat(false);
    }
  };

  const newChat = () => {
    setSessionId(null);
    setChatHistory([]);
    setQuestion("");
  };

  const commitRename = async (s) => {
    const t = renameVal.trim();
    setRenamingId(null);
    if (!t || t === s.title) return;
    setSessions((l) => l.map((x) => (x.id === s.id ? { ...x, title: t } : x)));
    try {
      await updateChatSession(s.id, { title: t });
    } catch {
      /* optimistic — next reload shows the server state */
    }
  };

  const archiveSession = async (s) => {
    setSessions((l) => l.filter((x) => x.id !== s.id));
    if (sessionId === s.id) newChat();
    try {
      await updateChatSession(s.id, { archived: true });
    } catch {
      /* optimistic */
    }
  };

  const removeSession = async (s) => {
    if (!window.confirm(`Delete the conversation “${s.title || "New chat"}”?`))
      return;
    setSessions((l) => l.filter((x) => x.id !== s.id));
    if (sessionId === s.id) newChat();
    try {
      await deleteChatSession(s.id);
    } catch {
      /* optimistic */
    }
  };

  // The URL is the source of truth for which agent is open — refresh and the
  // browser back button both land where they should. Cards navigate; this
  // effect loads/clears the state to match the :agentId param.
  useEffect(() => {
    if (loading) return;
    if (!agentId) {
      if (selected) {
        setSelected(null);
        setChatHistory([]);
        setDocs([]);
        setViewerDoc(null);
        setSessions([]);
        setSessionId(null);
      }
      return;
    }
    if (selected?.id === agentId) return;
    const a = agents.find((x) => x.id === agentId);
    if (a) selectAgent(a);
    else navigate(basePath, { replace: true });   // unknown/forbidden id
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentId, agents, loading]);

  const openAgent = (agent) => navigate(`${basePath}/${agent.id}`);
  const goBack = () => navigate(basePath);

  const handleQuery = async (preset) => {
    const q = (typeof preset === "string" ? preset : question).trim();
    if (!q || !selected || querying) return;
    setQuestion("");
    setChatHistory((h) => [...h, { role: "user", content: q }]);
    setQuerying(true);
    try {
      const res = await sendChatMessage(selected.id, q, sessionId);
      setSessionId(res.session.id);
      // the answered session jumps to the top of the history rail
      setSessions((l) => [res.session, ...l.filter((x) => x.id !== res.session.id)]);
      setChatHistory((h) => [
        ...h,
        { role: "assistant", content: res.answer, sources: res.sources },
      ]);
    } catch {
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

  /* an answer source → the matching document → open it in the viewer */
  const openSource = (src) => {
    const d = docs.find((x) => x.file_name === src.document);
    if (d) setViewerDoc(d);
  };

  const filteredAgents = useMemo(() => {
    const q = agentSearch.trim().toLowerCase();
    if (!q) return agents;
    return agents.filter(
      (a) =>
        (a.name || "").toLowerCase().includes(q) ||
        (a.description || "").toLowerCase().includes(q),
    );
  }, [agents, agentSearch]);

  const filteredDocs = useMemo(() => {
    const q = docSearch.trim().toLowerCase();
    if (!q) return docs;
    return docs.filter((d) => (d.file_name || "").toLowerCase().includes(q));
  }, [docs, docSearch]);

  if (loading)
    return (
      <div className="rag-page">
        <div className="rag-empty-state">Loading…</div>
      </div>
    );

  // ═══ PAGE 1: Agent cards — same design as the RAG workspace grid ═══
  if (!selected) {
    // group agents by department, exactly like the workspace does
    const deptNames = [...new Set(filteredAgents.map((a) => a.department_name || "General"))];
    return (
      <div className="rag-page" style={{ display: "block" }}>
        <div className="rag-main">
          {error && <div className="rag-toast rag-toast-error">{error}</div>}

          <div className="sg-head">
            <div>
              <h1 className="sg-title">{title}</h1>
              <p className="sg-sub">{subtitle}</p>
            </div>
            {agents.length > 3 && (
              <input
                className="rag-cfg-select"
                style={{ width: 240 }}
                value={agentSearch}
                onChange={(e) => setAgentSearch(e.target.value)}
                placeholder="🔍 Search agents…"
              />
            )}
          </div>

          <div className="rag-grid">
            {agents.length === 0 ? (
              <div className="sg-empty">
                <div className="sg-empty-ic">🤖</div>
                <div className="sg-empty-title">No agents available yet</div>
                <div className="sg-empty-sub">{emptyText}</div>
              </div>
            ) : filteredAgents.length === 0 ? (
              <div className="sg-empty">
                <div className="sg-empty-title">No agent matches “{agentSearch}”</div>
                <div className="sg-empty-sub">Try a different search.</div>
              </div>
            ) : (
              deptNames.map((dept) => {
                const ds = filteredAgents.filter(
                  (a) => (a.department_name || "General") === dept,
                );
                return (
                  <section key={dept} className="sg-section">
                    <div className="sg-section-head">
                      <span className="sg-section-name">{dept}</span>
                      <span className="sg-section-count">{ds.length}</span>
                      <span className="sg-section-rule" />
                    </div>
                    <div className="sg-grid">
                      {ds.map((a) => {
                        const editing = a.status === "EDITING";
                        return (
                          <button
                            key={a.id}
                            className="sg-card"
                            onClick={() => openAgent(a)}
                          >
                            <div className="sg-card-head">
                              <span className="sg-mono">{monoInitial(a.name)}</span>
                              <div className="sg-card-titles">
                                <div className="sg-name-row">
                                  <div className="sg-card-name">{a.name}</div>
                                </div>
                              </div>
                              <span className="sg-status-wrap">
                                <span className={`sg-status ${editing ? "editing" : "active"}`}>
                                  {editing ? "UPDATING…" : "ONLINE"}
                                </span>
                              </span>
                            </div>
                            <div className="sg-card-desc">
                              {a.description || "AI assistant powered by your documents"}
                            </div>
                            <div className="sg-card-foot">
                              <span className="sg-stat">
                                <IcDoc /> {a.num_documents || 0} docs
                              </span>
                              <span className="sg-stat">
                                <IcLayers /> {a.num_chunks || 0} chunks
                              </span>
                              <span className="sg-open">
                                <IcArrow />
                              </span>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </section>
                );
              })
            )}
          </div>
        </div>
      </div>
    );
  }

  // ═══ PAGE 2: Chat with agent + documents (black / white / blue) ═══
  const editing = selected.status === "EDITING";
  return (
    <div className="ac-page">
      {error && <div className="rag-toast rag-toast-error">{error}</div>}

      {/* header */}
      <div className="ac-head">
        <button className="ac-back" onClick={goBack}>
          <ArrowLeft size={14} /> Back
        </button>
        <span className="ac-mono">{monoInitial(selected.name)}</span>
        <div style={{ minWidth: 0 }}>
          <div className="ac-head-name">{selected.name}</div>
          <div className="ac-head-sub">
            <span className="ac-dot" />
            {editing
              ? "Updating…"
              : selected.description || "AI assistant powered by your documents"}
          </div>
        </div>
        {!editing && (
          <button
            className={`ac-docs-toggle ${showDocs ? "on" : ""}`}
            onClick={() => setShowDocs((v) => !v)}
            title={showDocs ? "Hide documents" : "Show documents"}
          >
            <FileText size={13} /> Documents
            {docs.length > 0 && (
              <span className="ac-docs-toggle-n">{docs.length}</span>
            )}
          </button>
        )}
      </div>

      {editing ? (
        <div className="ac-editing">
          <div className="ac-empty-ic"><Bot size={26} /></div>
          <div className="ac-empty-t">This agent is being updated</div>
          <div className="ac-empty-s">
            Your IT team is making changes. Please check back soon.
          </div>
        </div>
      ) : (
        <div className="ac-body">
          {/* conversations rail */}
          <aside className="ac-hist">
            <button className="ac-hist-new" onClick={newChat} disabled={querying}>
              <Plus size={14} /> New chat
            </button>
            <div className="ac-hist-list">
              {sessions.length === 0 && (
                <div className="ac-hist-empty">
                  No conversations yet — your chats are saved automatically.
                </div>
              )}
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className={`ac-hist-item ${s.id === sessionId ? "active" : ""}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => renamingId !== s.id && openSession(s)}
                  onKeyDown={(e) => e.key === "Enter" && renamingId !== s.id && openSession(s)}
                >
                  {renamingId === s.id ? (
                    <input
                      className="ac-hist-rename"
                      value={renameVal}
                      autoFocus
                      onChange={(e) => setRenameVal(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitRename(s);
                        if (e.key === "Escape") setRenamingId(null);
                      }}
                      onBlur={() => commitRename(s)}
                    />
                  ) : (
                    <>
                      <MessageSquare size={13} className="ac-hist-ic" />
                      <span className="ac-hist-title">{s.title || "New chat"}</span>
                      <span className="ac-hist-time">{timeAgo(s.last_message_at)}</span>
                      <span
                        className="ac-hist-actions"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          title="Rename"
                          onClick={() => {
                            setRenamingId(s.id);
                            setRenameVal(s.title || "");
                          }}
                        >
                          <Pencil size={12} />
                        </button>
                        <button title="Archive" onClick={() => archiveSession(s)}>
                          <Archive size={12} />
                        </button>
                        <button title="Delete" onClick={() => removeSession(s)}>
                          <Trash2 size={12} />
                        </button>
                      </span>
                    </>
                  )}
                </div>
              ))}
            </div>
          </aside>

          {/* chat column */}
          <div className="ac-chat">
            <div className="ac-stream">
              {loadingChat && (
                <div className="ac-hist-loading">Loading conversation…</div>
              )}
              {chatHistory.length === 0 && !loadingChat && (
                <div className="ac-empty">
                  <div className="ac-empty-ic"><Bot size={26} /></div>
                  <div className="ac-empty-t">Chat with {selected.name}</div>
                  <div className="ac-empty-s">
                    Ask anything about this agent's documents — answers cite
                    the sources they used.
                  </div>
                  <div className="ac-suggests">
                    {SUGGESTS.map((s) => (
                      <button key={s} className="ac-suggest" onClick={() => handleQuery(s)}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {chatHistory.map((m, i) => {
                const me = m.role === "user";
                return (
                  <div key={i} className={`ac-row ${me ? "me" : ""}`}>
                    <span className={`ac-av ${me ? "me" : "ai"}`}>
                      {me ? meInitials : <Bot size={15} />}
                    </span>
                    <div className={`ac-bubble ${me ? "me" : "ai"}`}>
                      {me ? m.content : <AnswerBody text={m.content} />}
                      {m.sources?.length > 0 && (
                        <div className="ac-sources">
                          <div className="ac-sources-t">Sources</div>
                          <div>
                            {m.sources.map((s, j) => (
                              <button
                                key={j}
                                className="ac-source"
                                onClick={() => openSource(s)}
                                title={`Open ${s.document}`}
                              >
                                <FileText size={11} />
                                <span className="ac-source-name">{s.document}</span>
                                <span className="ac-source-page">p.{s.page}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {querying && (
                <div className="ac-row">
                  <span className="ac-av ai"><Bot size={15} /></span>
                  <div className="ac-typing"><i /><i /><i /></div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            <div className="ac-composer">
              <input
                className="ac-input"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleQuery()}
                placeholder="Ask a question…"
                disabled={querying}
              />
              <button
                className="ac-send"
                onClick={() => handleQuery()}
                disabled={querying || !question.trim()}
                aria-label="Send"
              >
                <Send size={16} />
              </button>
            </div>
          </div>

          {/* documents sidebar — hidden until the header toggle opens it */}
          {showDocs && (
          <aside className="ac-side">
            <div className="ac-side-head">
              Documents
              <span className="ac-side-count">{docs.length}</span>
              <button
                className="ac-side-close"
                onClick={() => setShowDocs(false)}
                title="Hide documents"
                aria-label="Hide documents"
              >
                <X size={14} />
              </button>
            </div>
            {docs.length > 0 && (
              <div className="ac-search">
                <Search size={13} />
                <input
                  value={docSearch}
                  onChange={(e) => setDocSearch(e.target.value)}
                  placeholder="Search documents…"
                />
              </div>
            )}
            <div className="ac-docs">
              {loadingDocs && <div className="ac-docs-empty">Loading…</div>}
              {!loadingDocs && docs.length === 0 && (
                <div className="ac-docs-empty">No documents to preview.</div>
              )}
              {!loadingDocs &&
                filteredDocs.map((d) => (
                  <button
                    key={d.id}
                    className="ac-doc"
                    onClick={() => setViewerDoc(d)}
                    title={`Open ${d.file_name}`}
                  >
                    <span className="ac-ext">
                      {(d.file_type || "file").toUpperCase()}
                    </span>
                    <span style={{ minWidth: 0 }}>
                      <span className="ac-doc-name">{d.file_name}</span>
                      <span className="ac-doc-meta">
                        {fmtSize(d.file_size) || (d.file_type || "file").toUpperCase()}
                      </span>
                    </span>
                  </button>
                ))}
              {!loadingDocs && docs.length > 0 && filteredDocs.length === 0 && (
                <div className="ac-docs-empty">
                  No document matches “{docSearch}”.
                </div>
              )}
            </div>
          </aside>
          )}
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
