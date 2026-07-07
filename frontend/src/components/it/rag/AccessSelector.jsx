import React, { useMemo, useState } from "react";
import "../../../styles/it/access.css";

/**
 * AccessSelector — "who can use this space", exclusion model.
 *
 * Default: EVERY department member (current and future) can use the space.
 * To personalize, you DEACTIVATE specific members to exclude them.
 *
 * Backend stays an allow-list (`allowed_user_ids`):
 *   []        → everyone (open, includes future members)
 *   [subset]  → only these members (the deactivated ones are excluded)
 * When you switch every member back on, we normalise to [] (open again).
 */
const AVATAR_COLORS = [
  "#2563eb", "#7c3aed", "#0891b2", "#059669",
  "#d97706", "#dc2626", "#db2777", "#4f46e5",
];

const initialsOf = (u) => {
  const s = (u.name || u.email || "?").trim();
  const parts = s.split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return s.slice(0, 2).toUpperCase();
};

const colorOf = (key = "") =>
  AVATAR_COLORS[
    Array.from(key).reduce((a, c) => a + c.charCodeAt(0), 0) %
      AVATAR_COLORS.length
  ];

const SearchIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden>
    <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
    <path d="M21 21l-4.3-4.3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

export default function AccessSelector({
  users = [],
  allowedIds = [],
  onChange,
  loading = false,
  compact = false,
}) {
  const [q, setQ] = useState("");
  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return users;
    return users.filter(
      (u) =>
        (u.name || "").toLowerCase().includes(s) ||
        (u.email || "").toLowerCase().includes(s),
    );
  }, [users, q]);

  const [notice, setNotice] = useState("");
  const everyone = allowedIds.length === 0;
  const isOn = (id) => everyone || allowedIds.includes(id);
  const excludedCount = everyone
    ? 0
    : Math.max(0, users.length - allowedIds.length);

  const toggle = (id) => {
    // Work on the effective set of ACTIVE members (everyone → all ids).
    const active = new Set(everyone ? users.map((u) => u.id) : allowedIds);
    if (active.has(id)) {
      // Deactivating (excluding) — but the list must never become empty, because
      // an empty allow-list means "everyone" on the backend (it would silently
      // re-open the space). At least one member must keep access.
      if (active.size <= 1) {
        setNotice(
          "At least one member must keep access. Use “Allow everyone” to open the space to the whole department.",
        );
        return;
      }
      active.delete(id);
    } else {
      active.add(id);
    }
    setNotice("");
    let next = [...active];
    // Everyone active again → "open" (empty list, also re-includes future members)
    if (users.length > 0 && next.length === users.length) next = [];
    onChange(next);
  };

  const allowEveryone = () => {
    setNotice("");
    onChange([]);
  };

  return (
    <div className={`acx ${compact ? "acx-compact" : ""}`}>
      <div className={`acx-banner ${everyone ? "acx-open" : "acx-restricted"}`}>
        <span className="acx-banner-dot" />
        <div className="acx-banner-txt">
          <div className="acx-banner-title">
            {everyone
              ? "Everyone in the department"
              : `Personalized · ${excludedCount} excluded`}
          </div>
          <div className="acx-banner-sub">
            {everyone
              ? "All current and future department members can use this space. Admin & IT always can."
              : "Deactivated members below can't use this space. Everyone else can."}
          </div>
        </div>
      </div>

      {users.length > 0 && (
        <div className="acx-toolbar">
          <div className="acx-search">
            <span className="acx-search-ic">
              <SearchIcon />
            </span>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search members…"
            />
          </div>
          {!everyone && (
            <button type="button" className="acx-mini" onClick={allowEveryone}>
              Allow everyone
            </button>
          )}
        </div>
      )}

      {notice && <div className="acx-notice">{notice}</div>}

      <div className="acx-list">
        {loading && <div className="acx-empty">Loading members…</div>}
        {!loading && users.length === 0 && (
          <div className="acx-empty">
            No end-users in this department yet. Everyone added later gets access
            by default.
          </div>
        )}
        {!loading && users.length > 0 && filtered.length === 0 && (
          <div className="acx-empty">No member matches “{q}”.</div>
        )}
        {!loading &&
          filtered.map((u) => {
            const on = isOn(u.id);
            return (
              <button
                type="button"
                key={u.id}
                className={`acx-user ${on ? "" : "off"}`}
                onClick={() => toggle(u.id)}
                aria-pressed={on}
                title={on ? "Active — click to exclude" : "Excluded — click to allow"}
              >
                <span
                  className="acx-avatar"
                  style={{ background: colorOf(u.id || u.email) }}
                >
                  {initialsOf(u)}
                </span>
                <span className="acx-user-txt">
                  <span className="acx-user-name">{u.name || u.email}</span>
                  <span className="acx-user-mail">
                    {u.email}
                    {u.status && u.status !== "ACTIVE" ? ` · ${u.status}` : ""}
                  </span>
                </span>
                <span className="acx-user-state">{on ? "Active" : "Excluded"}</span>
                <span className="acx-switch" aria-hidden />
              </button>
            );
          })}
      </div>
    </div>
  );
}
