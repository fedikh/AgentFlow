import React, { useEffect, useState, useRef } from "react";
import ProviderLogo from "../../ProviderLogo";

/**
 * CustomDropdown — a select-like control that can render a provider logo next
 * to each option. Native <select> can't put images inside <option>, so both the
 * LLM and Embedding source selectors use this for a consistent look.
 *
 * options: [{ value, label, family?, sub?, tag? }]
 *   family → logo when showLogo · sub → small second line in the open list
 *   tag    → small pill on the right (e.g. "Ollama" / "Local")
 */
export default function CustomDropdown({
  options,
  value,
  onChange,
  placeholder,
  showLogo,
  disabled,
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const selected = options.find((o) => o.value === value);

  const rowBase = {
    width: "100%",
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "10px 12px",
    fontSize: 13,
    color: "#0d1f35",
    textAlign: "left",
    cursor: "pointer",
  };

  const tagStyle = {
    fontSize: 10,
    padding: "2px 7px",
    borderRadius: 999,
    background: "#eef2f7",
    color: "#475569",
    flexShrink: 0,
  };

  return (
    <div
      ref={ref}
      style={{ position: "relative", width: "100%", marginBottom: 12 }}
    >
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setOpen((o) => !o)}
        style={{
          ...rowBase,
          borderRadius: 8,
          border: "1px solid #e2e8f0",
          background: disabled ? "#f8fafc" : "#fff",
          cursor: disabled ? "default" : "pointer",
          opacity: disabled ? 0.7 : 1,
        }}
      >
        {selected ? (
          <>
            {showLogo && <ProviderLogo family={selected.family} size={18} />}
            <span style={{ flex: 1 }}>{selected.label}</span>
            {selected.tag && <span style={tagStyle}>{selected.tag}</span>}
          </>
        ) : (
          <span style={{ flex: 1, color: "#94a3b8" }}>{placeholder}</span>
        )}
        <span style={{ color: "#94a3b8", fontSize: 10 }}>▼</span>
      </button>

      {open && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            right: 0,
            background: "#fff",
            border: "1px solid #e2e8f0",
            borderRadius: 8,
            boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
            zIndex: 50,
            overflow: "hidden",
            maxHeight: 260,
            overflowY: "auto",
          }}
        >
          {options.map((o) => (
            <button
              key={o.value}
              type="button"
              onClick={() => {
                onChange(o.value);
                setOpen(false);
              }}
              style={{
                ...rowBase,
                border: "none",
                background: o.value === value ? "#eff6ff" : "#fff",
              }}
              onMouseEnter={(e) => {
                if (o.value !== value)
                  e.currentTarget.style.background = "#f8fafc";
              }}
              onMouseLeave={(e) => {
                if (o.value !== value)
                  e.currentTarget.style.background = "#fff";
              }}
            >
              {showLogo && <ProviderLogo family={o.family} size={18} />}
              <span style={{ flex: 1, minWidth: 0 }}>
                <span style={{ display: "block" }}>{o.label}</span>
                {o.sub && (
                  <span
                    style={{
                      display: "block",
                      fontSize: 11,
                      color: "#64748b",
                      marginTop: 2,
                    }}
                  >
                    {o.sub}
                  </span>
                )}
              </span>
              {o.tag && <span style={tagStyle}>{o.tag}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
