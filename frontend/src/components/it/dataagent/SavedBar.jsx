import React from "react";

/* "Currently saved" bar — the RAG SavedConfigBar pattern (scfg classes),
   fed directly with chips so each Data Agent panel states what is stored. */
export default function SavedBar({ title, accent = "#2563eb", chips = {} }) {
  const entries = Object.entries(chips).filter(([, v]) => v != null && v !== "");
  if (!entries.length) return null;
  return (
    <div className="scfg" style={{ "--accent": accent, marginBottom: 12 }}>
      <div className="scfg-head">
        <span className="scfg-eyebrow">Currently saved</span>
        <span className="scfg-title">{title}</span>
      </div>
      <div className="scfg-chips">
        {entries.map(([k, v]) => (
          <span className="scfg-chip" key={k}>
            <span className="scfg-chip-k">{k}</span>
            <span className="scfg-chip-v">{String(v)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
