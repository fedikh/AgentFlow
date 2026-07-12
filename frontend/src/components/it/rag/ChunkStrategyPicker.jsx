import React from "react";

const GROUP_ORDER = [
  "Basic",
  "Structure-aware",
  "Layout",
  "Semantic",
  "Advanced",
  "Tabular",
  "Other",
];

const Stars = ({ n = 0 }) => (
  <span className="chk-stars" aria-label={`${n} of 5`}>
    {"★".repeat(n)}
    <span className="chk-stars-empty">{"★".repeat(Math.max(0, 5 - n))}</span>
  </span>
);

/**
 * ChunkStrategyPicker — grouped, rated strategy selector for the space's
 * default chunking strategy. Reads the catalog from the backend so new
 * strategies appear automatically.
 */
export default function ChunkStrategyPicker({
  strategies = [],
  value,
  onChange,
  recommended = [],
  allowed = null, // array of strategy names to restrict to (null = all)
}) {
  if (!strategies.length) {
    return <div className="rag-cfg-hint">Loading strategies…</div>;
  }

  const allowSet = allowed && allowed.length ? new Set(allowed) : null;
  const visible = allowSet
    ? strategies.filter((s) => allowSet.has(s.name))
    : strategies;

  const groups = {};
  visible.forEach((s) => {
    (groups[s.group] = groups[s.group] || []).push(s);
  });
  const cur = (value || "FIXED").toUpperCase();
  const recSet = new Set(recommended);

  return (
    <div className="chk">
      {GROUP_ORDER.filter((g) => groups[g]).map((g) => (
        <div className="chk-group" key={g}>
          <div className="chk-group-title">{g}</div>
          <div className="chk-list">
            {groups[g].map((s) => {
              const active = cur === s.name;
              const cons = s.cons && s.cons !== "—" ? ` · Cons: ${s.cons}` : "";
              return (
                <button
                  type="button"
                  key={s.name}
                  className={`chk-item ${active ? "active" : ""}`}
                  onClick={() => onChange(s.name)}
                  title={`${s.pros || ""}${cons}`}
                >
                  <span className="chk-radio" />
                  <span className="chk-item-body">
                    <span className="chk-item-top">
                      <span className="chk-item-name">{s.label}</span>
                      <Stars n={s.stars || 0} />
                    </span>
                    <span className="chk-item-for">
                      {recSet.has(s.name) && (
                        <span className="chk-rec">Recommended</span>
                      )}
                      {(s.best_for || []).slice(0, 3).join(" · ")}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
