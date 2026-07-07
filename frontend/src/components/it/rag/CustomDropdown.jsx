import React, { useEffect, useState, useRef } from "react";
import ProviderLogo from "../../ProviderLogo";

/**
 * CustomDropdown — a select-like control that can render a provider logo next
 * to each option. Native <select> can't put images inside <option>, so both the
 * LLM and Embedding source selectors use this for a consistent look.
 *
 * options: [{ value, label, family? }]  (family drives the logo when showLogo)
 */
export default function CustomDropdown({
  options,
  value,
  onChange,
  placeholder,
  showLogo,
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

  return (
    <div
      ref={ref}
      style={{ position: "relative", width: "100%", marginBottom: 12 }}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          ...rowBase,
          borderRadius: 8,
          border: "1px solid #e2e8f0",
          background: "#fff",
        }}
      >
        {selected ? (
          <>
            {showLogo && <ProviderLogo family={selected.family} size={18} />}
            <span style={{ flex: 1 }}>{selected.label}</span>
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
              <span>{o.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
