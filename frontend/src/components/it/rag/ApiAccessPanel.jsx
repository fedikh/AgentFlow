import React, { useEffect, useState } from "react";
import {
  BookOpen,
  Check,
  Copy,
  KeyRound,
  Plus,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { listApiKeys, createApiKey, revokeApiKey } from "../../../services/ragApi";

/*
 * ApiAccessPanel — shown with the deploy workflow (Versions panel).
 *
 * Lets the owner mint per-integration API keys for this agent and shows the
 * consume documentation (endpoint, examples, identity, error codes). The full
 * key is displayed ONCE at creation — the backend stores only its hash.
 */

const API_ROOT = (import.meta.env.VITE_API_URL || "http://localhost:8000/api")
  .replace(/\/api\/?$/, "");

const ink = { primary: "#0f172a", muted: "#64748b" };

const mono = {
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
  fontSize: 12,
};

const fmtDate = (s) => {
  if (!s) return "—";
  const d = new Date(String(s).replace(" ", "T"));
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString();
};

function CopyBtn({ text, small = false }) {
  const [ok, setOk] = useState(false);
  return (
    <button
      className="rag-btn rag-btn-sm"
      style={{ display: "inline-flex", alignItems: "center", gap: 5 }}
      onClick={() => {
        navigator.clipboard.writeText(text);
        setOk(true);
        setTimeout(() => setOk(false), 1500);
      }}
    >
      {ok ? <Check size={small ? 11 : 13} /> : <Copy size={small ? 11 : 13} />}
      {ok ? "Copied" : "Copy"}
    </button>
  );
}

function CodeBlock({ title, code }) {
  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: 10, overflow: "hidden" }}>
      <div
        style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "7px 12px", background: "#f8fafc",
          borderBottom: "1px solid #e2e8f0",
          fontSize: 11.5, fontWeight: 600, color: ink.muted,
        }}
      >
        {title}
        <CopyBtn text={code} small />
      </div>
      <pre
        style={{
          ...mono, margin: 0, padding: "12px 14px", background: "#0f172a",
          color: "#e2e8f0", overflowX: "auto", lineHeight: 1.6,
        }}
      >
        {code}
      </pre>
    </div>
  );
}

const ApiAccessPanel = ({ space, canManage }) => {
  const [keys, setKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [expires, setExpires] = useState("");
  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState(null); // {api_key, name} — shown once
  const [error, setError] = useState("");
  const [showDocs, setShowDocs] = useState(false);

  const deployed = space?.status === "ACTIVE";
  const chatUrl = `${API_ROOT}/v1/agents/${space?.id}/chat`;

  useEffect(() => {
    let on = true;
    setLoading(true);
    listApiKeys(space.id)
      .then((k) => on && setKeys(k))
      .catch(() => on && setKeys([]))
      .finally(() => on && setLoading(false));
    return () => {
      on = false;
    };
  }, [space.id]);

  const handleCreate = async () => {
    if (!name.trim() || creating) return;
    setCreating(true);
    setError("");
    try {
      const k = await createApiKey(space.id, {
        name: name.trim(),
        expires_days: expires ? Number(expires) : null,
      });
      setNewKey(k);
      setKeys((l) => [{ ...k, api_key: undefined }, ...l]);
      setName("");
      setExpires("");
    } catch (e) {
      setError(e.message);
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (k) => {
    if (!window.confirm(`Revoke "${k.name}"? Apps using this key stop working immediately.`))
      return;
    try {
      const updated = await revokeApiKey(space.id, k.id);
      setKeys((l) => l.map((x) => (x.id === k.id ? updated : x)));
    } catch (e) {
      setError(e.message);
    }
  };

  const curlExample = `curl -X POST ${chatUrl} \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "question": "What is the vacation policy?",
    "external_user_id": "employee-1042",
    "session_id": null
  }'`;

  const jsExample = `// From YOUR backend only — never ship the key to a browser
const res = await fetch("${chatUrl}", {
  method: "POST",
  headers: {
    "Authorization": \`Bearer \${process.env.AGENT_API_KEY}\`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    question: userQuestion,
    external_user_id: currentUser.id,  // your app's user → isolated history
    session_id: savedSessionId ?? null, // null = new conversation
  }),
});
const { answer, sources, session_id } = await res.json();`;

  const pyExample = `import os, requests

r = requests.post(
    "${chatUrl}",
    headers={"Authorization": f"Bearer {os.environ['AGENT_API_KEY']}"},
    json={
        "question": "What is the vacation policy?",
        "external_user_id": "employee-1042",
        "session_id": None,
    },
    timeout=60,
)
data = r.json()  # answer, sources, session_id`;

  return (
    <div className="rag-cfg-panel" style={{ marginTop: 14 }}>
      <div className="rag-cfg-head">
        <div>
          <div className="rag-cfg-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <KeyRound size={16} /> API Access
          </div>
          <div className="rag-cfg-sub">
            Use this agent from your own apps — BI dashboards, intranet portals,
            mobile backends. One key per app; revoke any time.
          </div>
        </div>
        <button
          className="rag-btn rag-btn-sm"
          style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          onClick={() => setShowDocs((v) => !v)}
        >
          <BookOpen size={13} /> {showDocs ? "Hide docs" : "How to use"}
        </button>
      </div>

      {!deployed && (
        <div className="rag-cfg-hint" style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <ShieldAlert size={14} />
          The agent must be <strong>deployed & published</strong> for API calls to
          work — keys created now activate as soon as you deploy.
        </div>
      )}
      {error && <div className="rag-toast rag-toast-error">{error}</div>}

      {/* ── create ── */}
      {canManage && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "10px 0" }}>
          <input
            className="rag-cfg-select"
            style={{ flex: 1, minWidth: 220 }}
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            placeholder='Integration name — e.g. "BI dashboard", "HR portal"'
          />
          <select
            className="rag-cfg-select"
            style={{ width: 150 }}
            value={expires}
            onChange={(e) => setExpires(e.target.value)}
          >
            <option value="">Never expires</option>
            <option value="30">Expires in 30 days</option>
            <option value="90">Expires in 90 days</option>
            <option value="365">Expires in 1 year</option>
          </select>
          <button
            className="rag-btn rag-btn-primary rag-btn-sm"
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            onClick={handleCreate}
            disabled={creating || !name.trim()}
          >
            <Plus size={14} /> {creating ? "Creating…" : "Create key"}
          </button>
        </div>
      )}

      {/* ── the one-time key reveal ── */}
      {newKey && (
        <div
          style={{
            border: "1px solid #fbbf24", background: "#fffbeb", borderRadius: 10,
            padding: "12px 14px", margin: "0 0 12px",
          }}
        >
          <div style={{ fontSize: 12.5, fontWeight: 700, color: "#92400e" }}>
            Copy this key now — it is shown only once and never stored.
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
            <code
              style={{
                ...mono, background: "#fff", border: "1px solid #f1d48a",
                borderRadius: 8, padding: "7px 10px", wordBreak: "break-all", flex: 1,
                minWidth: 240,
              }}
            >
              {newKey.api_key}
            </code>
            <CopyBtn text={newKey.api_key} />
            <button className="rag-btn rag-btn-sm" onClick={() => setNewKey(null)}>
              Done
            </button>
          </div>
        </div>
      )}

      {/* ── keys table ── */}
      {loading ? (
        <div className="rag-cfg-hint">Loading keys…</div>
      ) : keys.length === 0 ? (
        <div className="rag-cfg-hint">
          No API keys yet — create one per app that will use this agent.
        </div>
      ) : (
        <table className="ev-table">
          <thead>
            <tr>
              <th>Name</th><th>Key</th><th>Created</th><th>Last used</th>
              <th>Requests</th><th>Status</th><th></th>
            </tr>
          </thead>
          <tbody>
            {keys.map((k) => (
              <tr key={k.id} style={k.status !== "active" ? { opacity: 0.55 } : undefined}>
                <td>{k.name}</td>
                <td style={mono}>{k.key_display}</td>
                <td>{fmtDate(k.created_at)}</td>
                <td>{fmtDate(k.last_used_at)}</td>
                <td>{k.request_count ?? 0}</td>
                <td>
                  <span
                    style={{
                      fontSize: 10.5, fontWeight: 700, padding: "2px 8px",
                      borderRadius: 20,
                      background: k.status === "active" ? "#f0fdf4" : "#fef2f2",
                      color: k.status === "active" ? "#166534" : "#991b1b",
                    }}
                  >
                    {k.status.toUpperCase()}
                  </span>
                </td>
                <td>
                  {canManage && k.status === "active" && (
                    <button
                      className="rag-btn rag-btn-sm"
                      title="Revoke key"
                      style={{ display: "inline-flex", alignItems: "center", gap: 5 }}
                      onClick={() => handleRevoke(k)}
                    >
                      <Trash2 size={12} /> Revoke
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* ── consume docs ── */}
      {showDocs && (
        <div style={{ display: "grid", gap: 12, marginTop: 14 }}>
          <div className="rag-cfg-hint" style={{ margin: 0 }}>
            <strong>Endpoint</strong> — <code style={mono}>POST {chatUrl}</code>
            <br />
            Send <code style={mono}>question</code>, keep the returned{" "}
            <code style={mono}>session_id</code> and send it back for follow-up
            questions (the agent keeps the conversation memory). Pass{" "}
            <code style={mono}>external_user_id</code> = the logged-in user of
            YOUR app (employee id…) so every worker gets an isolated, private
            history. Response: <code style={mono}>answer</code>,{" "}
            <code style={mono}>sources</code> (document, page, excerpt),{" "}
            <code style={mono}>session_id</code>.
          </div>

          <CodeBlock title="curl" code={curlExample} />
          <CodeBlock title="JavaScript / Node backend" code={jsExample} />
          <CodeBlock title="Python" code={pyExample} />

          <div className="rag-cfg-hint" style={{ margin: 0 }}>
            <strong>Security rules</strong>
            <br />• Keep the key on your <strong>server</strong> (env variable /
            secret manager) — never in browser or mobile app code, where anyone
            can read it.
            <br />• One key per app. Rotating = create a new key, switch your
            app, revoke the old one — zero downtime.
            <br />• Limits per key: 60 requests/min, 5000/day → HTTP{" "}
            <code style={mono}>429</code>. Other codes:{" "}
            <code style={mono}>401</code> invalid/revoked key,{" "}
            <code style={mono}>403</code> wrong agent or unpublished,{" "}
            <code style={mono}>409</code> agent being updated (retry later).
            <br />• Also available:{" "}
            <code style={mono}>
              GET /v1/agents/&lt;id&gt;/sessions?external_user_id=…
            </code>{" "}
            and <code style={mono}>GET /v1/agents/&lt;id&gt;/sessions/&lt;session_id&gt;</code>{" "}
            to rebuild a user's conversation list in your app.
          </div>
        </div>
      )}
    </div>
  );
};

export default ApiAccessPanel;
