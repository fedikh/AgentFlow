import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowUp, Bot, Building2, Check, FileText,
  LayoutDashboard, LogOut, MoreHorizontal, Plus, Search, Trash2, User, X,
} from "lucide-react";
import {
  listSpaces, listPublicDocuments, listChatSessions, getChatSession,
  sendChatMessage, deleteChatSession,
} from "../../services/ragApi";
import { getUser, clearSession, logout } from "../../services/authApi";
import AnswerBody from "../../components/rag/AnswerBody";
import DocViewerModal from "../../components/user/DocViewerModal";
import UserDashboard from "./UserDashboard";
import ProfilePage from "../shared/ProfilePage";
import logo from "../../assets/Logo/Agentflowlogowithouttext.png";
import "../../styles/user/userChat.css";

/*
 * UserChatPage — the end-user experience, chat-first (DeepSeek-style):
 *
 *   rail    New chat · history grouped by month · profile row whose ⋯ menu
 *           carries the navigation (Agents · Dashboard · Profile · Log out)
 *   top     a quiet chip naming the current department · agent — changing
 *           agent happens in the Agents overlay opened from the menu
 *   center  hero "What can I do for you?" + floating input card; once a
 *           message is sent, a clean thread with cited sources
 *
 * The open agent lives in the URL (/user/agents/:agentId) so a conversation
 * can be bookmarked and survives a refresh.
 */

const monthOf = (iso) => String(iso || "").replace(" ", "T").slice(0, 7) || "—";

const initialsOf = (name = "?") => {
  const p = String(name).trim().split(/\s+/);
  return ((p.length >= 2 ? p[0][0] + p[1][0] : String(name).slice(0, 2)) || "?")
    .toUpperCase();
};

const fmtSize = (b) => {
  if (!b) return "";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
};

/* ── profile row + popup menu (Dashboard · Profile · Log out) ──
   Dashboard and Profile open IN-PAGE (overlay views) — the user never
   leaves this experience. */
function ProfileMenu({ onView }) {
  const navigate = useNavigate();
  const user = getUser();
  const [open, setOpen] = useState(false);
  const [confirmOut, setConfirmOut] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const go = (view) => {
    setOpen(false);
    onView(view);
  };
  const signOut = () =>
    logout().finally(() => {
      clearSession();
      navigate("/login");
    });

  return (
    <div className="uc-me" ref={ref}>
      {open && (
        <div className="uc-menu">
          <button className="uc-menu-item" onClick={() => go("agents")}>
            <Bot size={15} /> Agents
          </button>
          <button className="uc-menu-item" onClick={() => go("dashboard")}>
            <LayoutDashboard size={15} /> Dashboard
          </button>
          <button className="uc-menu-item" onClick={() => go("profile")}>
            <User size={15} /> Profile
          </button>
          <div className="uc-menu-sep" />
          <button className="uc-menu-item danger"
                  onClick={() => { setOpen(false); setConfirmOut(true); }}>
            <LogOut size={15} /> Log out
          </button>
        </div>
      )}
      {confirmOut && (
        <div className="uc-modal-backdrop" onClick={() => setConfirmOut(false)}>
          <div className="uc-confirm" onClick={(e) => e.stopPropagation()}>
            <span className="uc-confirm-ic"><LogOut size={20} /></span>
            <div className="uc-confirm-t">Sign out?</div>
            <div className="uc-confirm-s">
              Are you sure you want to sign out of AgentFlow?
            </div>
            <div className="uc-confirm-row">
              <button className="uc-confirm-cancel"
                      onClick={() => setConfirmOut(false)}>
                Cancel
              </button>
              <button className="uc-confirm-out" onClick={signOut}>
                Sign out
              </button>
            </div>
          </div>
        </div>
      )}
      <button className="uc-me-row" onClick={() => setOpen((v) => !v)}>
        <span className="uc-me-av">{initialsOf(user?.name || user?.email)}</span>
        <span className="uc-me-name">{user?.name || user?.email || "Me"}</span>
        <MoreHorizontal size={16} className="uc-me-dots" />
      </button>
    </div>
  );
}

/* ── the Agents view — lives in the overlay next to Dashboard · Profile:
   departments on the left, that department's agents as cards ── */
function AgentsBrowser({ agents, selected, onPick }) {
  const departments = useMemo(
    () => [...new Set(agents.map((a) => a.department_name || "General"))],
    [agents],
  );
  const [dept, setDept] = useState(
    selected?.department_name || departments[0] || null,
  );
  const current = departments.includes(dept) ? dept : departments[0];
  const deptAgents = agents.filter(
    (a) => (a.department_name || "General") === current,
  );

  if (agents.length === 0) {
    return (
      <div className="uc-agents-empty">
        <b>No agents available yet</b>
        Your IT team hasn&apos;t deployed any AI agents for your department.
        Check back later!
      </div>
    );
  }

  return (
    <div className="uc-agents">
      <aside className="uc-agents-side">
        <div className="uc-agents-label">Departments</div>
        {departments.map((d) => {
          const n = agents.filter(
            (a) => (a.department_name || "General") === d,
          ).length;
          return (
            <button key={d}
                    className={`uc-agents-dept ${d === current ? "on" : ""}`}
                    onClick={() => setDept(d)}>
              <Building2 size={15} />
              <span className="uc-agents-dept-name">{d}</span>
              <span className="uc-agents-dept-n">{n}</span>
            </button>
          );
        })}
      </aside>
      <div className="uc-agents-grid">
        {deptAgents.map((a) => {
          const updating = a.status === "EDITING";
          const on = a.id === selected?.id;
          return (
            <button key={a.id} disabled={updating}
                    className={`uc-agent-card ${on ? "on" : ""}`}
                    onClick={() => onPick(a)}>
              <span className="uc-agent-head">
                <span className="uc-agent-ic"><Bot size={17} /></span>
                <span className="uc-agent-name">{a.name}</span>
                {on && <Check size={15} className="uc-agent-check" />}
              </span>
              <span className="uc-agent-desc">
                {updating
                  ? "Updating — temporarily offline"
                  : a.description || "AI assistant powered by your documents."}
              </span>
              <span className="uc-agent-meta">
                <FileText size={11} /> {a.num_documents || 0} documents
                {on && <em>Current agent</em>}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ── the input card (hero + docked share it) ── */
function InputCard({ agent, value, onChange, onSend, busy, inputRef }) {
  return (
    <div className="uc-inputcard">
      <textarea ref={inputRef} className="uc-input" rows={1} value={value}
                placeholder={agent ? `Message ${agent.name}` : "Choose an agent to start"}
                disabled={!agent || busy}
                onChange={(e) => {
                  onChange(e.target.value);
                  e.target.style.height = "auto";
                  e.target.style.height = `${Math.min(e.target.scrollHeight, 150)}px`;
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(); }
                }} />
      <div className="uc-input-row">
        {agent && (
          <span className="uc-tag blue">
            <FileText size={12} /> {agent.num_documents || 0} documents
          </span>
        )}
        <button className="uc-send" onClick={onSend} aria-label="Send"
                disabled={!agent || busy || !value.trim()}>
          <ArrowUp size={17} />
        </button>
      </div>
    </div>
  );
}

export default function UserChatPage() {
  const { agentId } = useParams();
  const navigate = useNavigate();

  const [agents, setAgents] = useState(null);          // null = loading
  const [selected, setSelected] = useState(null);
  const [docs, setDocs] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loadingChat, setLoadingChat] = useState(false);
  const [question, setQuestion] = useState("");
  const [querying, setQuerying] = useState(false);
  const [viewerDoc, setViewerDoc] = useState(null);
  const [view, setView] = useState("chat");  // chat | agents | dashboard | profile
  const [showDocs, setShowDocs] = useState(false);
  const [docQuery, setDocQuery] = useState("");
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    listSpaces().then((all) => setAgents(all)).catch(() => setAgents([]));
  }, []);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, querying]);

  // URL ⇄ selection: the :agentId param is the source of truth
  useEffect(() => {
    if (agents === null) return;
    if (!agentId) {
      if (!selected && agents.length) pickAgent(agents[0], { navigateTo: true });
      return;
    }
    if (selected?.id === agentId) return;
    const a = agents.find((x) => x.id === agentId);
    if (a) pickAgent(a, { navigateTo: false });
    else navigate("/user/agents", { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentId, agents]);

  const pickAgent = async (agent, { navigateTo = true } = {}) => {
    setSelected(agent);
    setSessions([]);
    setSessionId(null);
    setMessages([]);
    setQuestion("");
    setDocs([]);
    setView("chat");           // a dashboard "chat with…" click lands here
    setShowDocs(false);
    setDocQuery("");
    if (navigateTo) navigate(`/user/agents/${agent.id}`);
    if (agent.status === "EDITING") return;
    listPublicDocuments(agent.id).then(setDocs).catch(() => {});
    listChatSessions(agent.id).then(setSessions).catch(() => {});
  };

  const newChat = () => {
    setSessionId(null);
    setMessages([]);
    setQuestion("");
    inputRef.current?.focus();
  };

  const openSession = async (s) => {
    setSessionId(s.id);
    setMessages([]);
    setLoadingChat(true);
    try {
      const res = await getChatSession(s.id);
      setMessages((res.messages || []).map((m) => ({
        role: m.role, content: m.content, sources: m.sources,
      })));
    } catch {
      setMessages([]);
    } finally {
      setLoadingChat(false);
    }
  };

  const removeSession = async (e, s) => {
    e.stopPropagation();
    if (!window.confirm(`Delete “${s.title || "New chat"}”?`)) return;
    setSessions((l) => l.filter((x) => x.id !== s.id));
    if (sessionId === s.id) newChat();
    try { await deleteChatSession(s.id); } catch { /* optimistic */ }
  };

  const send = async (preset) => {
    const q = (typeof preset === "string" ? preset : question).trim();
    if (!q || !selected || querying) return;
    setQuestion("");
    if (inputRef.current) inputRef.current.style.height = "auto";
    setMessages((m) => [...m, { role: "user", content: q }]);
    setQuerying(true);
    try {
      const res = await sendChatMessage(selected.id, q, sessionId);
      setSessionId(res.session.id);
      setSessions((l) => [res.session, ...l.filter((x) => x.id !== res.session.id)]);
      setMessages((m) => [...m, { role: "assistant", content: res.answer,
                                  sources: res.sources }]);
    } catch {
      setMessages((m) => [...m, {
        role: "assistant",
        content: "Sorry, something went wrong. Please try again.",
      }]);
    } finally {
      setQuerying(false);
    }
  };

  const openSource = (src) => {
    const d = docs.find((x) => x.file_name === src.document);
    if (d) setViewerDoc(d);
  };

  // history grouped by month (newest first), like 2026-05 / 2026-04 …
  const grouped = useMemo(() => {
    const by = new Map();
    for (const s of sessions) {
      const m = monthOf(s.last_message_at || s.created_at);
      if (!by.has(m)) by.set(m, []);
      by.get(m).push(s);
    }
    return [...by.entries()];
  }, [sessions]);

  const updating = selected?.status === "EDITING";
  const empty = messages.length === 0 && !loadingChat;

  // documents filtered by the panel search (case/diacritics-insensitive)
  const norm = (s) => String(s || "")
    .normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const filteredDocs = docQuery.trim()
    ? docs.filter((d) => norm(d.file_name).includes(norm(docQuery)))
    : docs;

  return (
    <div className="uc-page">
      {/* ═══ rail ═══ */}
      <aside className="uc-rail">
        <div className="uc-brand">
          <img src={logo} alt="" />
          <span className="uc-brand-name">AgentFlow<span>.AI</span></span>
        </div>
        <button className="uc-new" onClick={newChat}>
          <Plus size={15} /> New chat
        </button>
        <div className="uc-hist">
          {sessions.length === 0 && (
            <div className="uc-hist-empty">
              {selected
                ? "No conversations yet — they are saved here automatically."
                : "Pick an agent to start chatting."}
            </div>
          )}
          {grouped.map(([month, list]) => (
            <div key={month}>
              <div className="uc-month">{month}</div>
              {list.map((s) => (
                <button key={s.id}
                        className={`uc-hist-item ${s.id === sessionId ? "active" : ""}`}
                        onClick={() => openSession(s)}>
                  <span className="uc-hist-title">{s.title || "New chat"}</span>
                  <span className="uc-hist-del" title="Delete"
                        onClick={(e) => removeSession(e, s)}>
                    <Trash2 size={13} />
                  </span>
                </button>
              ))}
            </div>
          ))}
        </div>
        <ProfileMenu onView={setView} />
      </aside>

      {/* ═══ main ═══ */}
      <main className="uc-main">
        <div className="uc-top">
          <span />
          <div className="uc-current">
            <span className="uc-current-ic"><Bot size={15} /></span>
            <span className="uc-current-txt">
              <span className="uc-current-dept">
                {selected ? selected.department_name || "General" : "AgentFlow"}
              </span>
              <span className="uc-current-name">
                {selected ? selected.name : "No agent selected"}
              </span>
            </span>
          </div>
          <div className="uc-top-right">
            {selected && !updating && (
              <button className={`uc-docsbtn ${showDocs ? "on" : ""}`}
                      onClick={() => setShowDocs((v) => !v)}
                      title={showDocs ? "Hide documents" : "Show the agent's documents"}>
                <FileText size={13} /> Documents
                {docs.length > 0 && (
                  <span className="uc-docsbtn-n">{docs.length}</span>
                )}
              </button>
            )}
          </div>
        </div>

        <div className="uc-mainrow">
        <div className="uc-content">
        {agents !== null && agents.length === 0 ? (
          <div className="uc-blank">
            <b>No agents available yet</b>
            Your IT team hasn&apos;t deployed any AI agents for your department.
            Check back later!
          </div>
        ) : updating ? (
          <div className="uc-blank">
            <b>{selected.name} is being updated</b>
            Your IT team is making changes. Please check back soon.
          </div>
        ) : empty ? (
          <div className="uc-hero">
            <div className="uc-hero-title">
              <img src={logo} alt="" /> What can I do for you?
            </div>
            {selected && (
              <div className="uc-hero-sub">
                Ask {selected.name} anything about your department&apos;s
                documents — every answer cites its sources.
              </div>
            )}
            <InputCard agent={selected} value={question} onChange={setQuestion}
                       onSend={send} busy={querying} inputRef={inputRef} />
          </div>
        ) : (
          <>
            <div className="uc-stream">
              <div className="uc-thread">
                {loadingChat && (
                  <div className="uc-hist-empty">Loading conversation…</div>
                )}
                {messages.map((m, i) =>
                  m.role === "user" ? (
                    <div key={i} className="uc-msg me">
                      <div className="uc-msg-user">{m.content}</div>
                    </div>
                  ) : (
                    <div key={i} className="uc-msg">
                      <div className="uc-msg-ai">
                        <span className="uc-msg-av"><img src={logo} alt="" /></span>
                        <div className="uc-msg-body">
                          <AnswerBody text={m.content} />
                          {m.sources?.length > 0 && (
                            <div className="uc-sources">
                              {m.sources.map((s, j) => (
                                <button key={j} className="uc-source"
                                        onClick={() => openSource(s)}
                                        title={`Open ${s.document}`}>
                                  <FileText size={11} />
                                  <span className="uc-source-name">{s.document}</span>
                                  <span className="uc-source-page">p.{s.page}</span>
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ),
                )}
                {querying && (
                  <div className="uc-msg">
                    <div className="uc-msg-ai">
                      <span className="uc-msg-av"><img src={logo} alt="" /></span>
                      <span className="uc-typing"><i /><i /><i /></span>
                    </div>
                  </div>
                )}
                <div ref={endRef} />
              </div>
            </div>
            <div className="uc-dock">
              <InputCard agent={selected} value={question} onChange={setQuestion}
                         onSend={send} busy={querying} inputRef={inputRef} />
              <div className="uc-dock-hint">
                Enter to send · Shift+Enter for a new line
              </div>
            </div>
          </>
        )}
        </div>

        {/* documents panel — hidden until the toggle opens it */}
        {showDocs && selected && !updating && (
          <aside className="uc-docspanel">
            <div className="uc-docspanel-head">
              Documents
              <span className="uc-docspanel-n">{docs.length}</span>
              <button className="uc-docspanel-x" aria-label="Hide documents"
                      onClick={() => setShowDocs(false)}>
                <X size={14} />
              </button>
            </div>
            {docs.length > 0 && (
              <div className="uc-docsearch">
                <Search size={13} />
                <input value={docQuery}
                       onChange={(e) => setDocQuery(e.target.value)}
                       placeholder="Search documents…" />
              </div>
            )}
            <div className="uc-docspanel-list">
              {docs.length === 0 && (
                <div className="uc-docs-empty">No documents to preview.</div>
              )}
              {docs.length > 0 && filteredDocs.length === 0 && (
                <div className="uc-docs-empty">
                  No document matches “{docQuery}”.
                </div>
              )}
              {filteredDocs.map((d) => (
                <button key={d.id} className="uc-doc"
                        onClick={() => setViewerDoc(d)}
                        title={`Open ${d.file_name}`}>
                  <span className="uc-doc-ext">
                    {(d.file_type || "file").toUpperCase()}
                  </span>
                  <span style={{ minWidth: 0 }}>
                    <span className="uc-doc-name">{d.file_name}</span>
                    <span className="uc-doc-meta">
                      {fmtSize(d.file_size) || (d.file_type || "file").toUpperCase()}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </aside>
        )}
        </div>
      </main>

      {/* ═══ Agents / Dashboard / Profile — floating OVER the chat ═══ */}
      {view !== "chat" && (
        <div className="uc-modal-backdrop" onClick={() => setView("chat")}>
          <div className={`uc-modal ${view === "agents" ? "tall" : ""}`}
               onClick={(e) => e.stopPropagation()}>
            <div className="uc-modal-head">
              <span className="uc-modal-title">
                {view === "agents" ? "Choose an agent"
                  : view === "dashboard" ? "Dashboard" : "My profile"}
              </span>
              <button className="uc-modal-x" aria-label="Close"
                      onClick={() => setView("chat")}>
                <X size={16} />
              </button>
            </div>
            <div className="uc-modal-body">
              {view === "agents" ? (
                <AgentsBrowser agents={agents || []} selected={selected}
                               onPick={(a) => pickAgent(a)} />
              ) : view === "dashboard" ? (
                <UserDashboard onOpenAgent={(id) => {
                  const a = (agents || []).find((x) => x.id === id);
                  if (a) pickAgent(a);
                }} />
              ) : (
                <ProfilePage />
              )}
            </div>
          </div>
        </div>
      )}

      {viewerDoc && selected && (
        <DocViewerModal spaceId={selected.id} doc={viewerDoc}
                        onClose={() => setViewerDoc(null)} />
      )}
    </div>
  );
}
