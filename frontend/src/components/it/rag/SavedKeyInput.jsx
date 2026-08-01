import React, { useState } from "react";

/**
 * SavedKeyInput — API-key field with saved-key UX, shared by the LLM,
 * Embedding and Re-ranker "own key" fields.
 *
 *   · key saved   → read-only masked preview ("sk-•••4f2") + a Change button
 *   · Change      → empty password input (+ Cancel to keep the saved key)
 *   · no key yet  → plain password input
 *
 * The full key never reaches the frontend — the backend only sends the
 * masked preview. Typing a new key replaces the old one on Save.
 */
const btn = {
  padding: "9px 14px",
  borderRadius: 8,
  border: "1px solid #e2e8f0",
  background: "#fff",
  color: "#334155",
  fontSize: 13,
  cursor: "pointer",
  whiteSpace: "nowrap",
  flexShrink: 0,
};

export default function SavedKeyInput({ masked, hasKey, value, onChange, placeholder }) {
  const [editing, setEditing] = useState(false);
  const showSaved = hasKey && !editing && !value;

  if (showSaved) {
    return (
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input
          className="rag-cfg-select"
          type="text"
          readOnly
          value={masked || "•••"}
          style={{ flex: 1, color: "#64748b", background: "#f8fafc",
                   letterSpacing: "0.5px", cursor: "default" }}
          title="Key saved (encrypted). Click Change to replace it."
        />
        <button type="button" style={btn} onClick={() => setEditing(true)}>
          Change
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <input
        className="rag-cfg-select"
        type="password"
        value={value || ""}
        autoFocus={editing}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        style={{ flex: 1 }}
      />
      {hasKey && (
        <button type="button" style={btn}
          onClick={() => { setEditing(false); onChange(""); }}>
          Cancel
        </button>
      )}
    </div>
  );
}
