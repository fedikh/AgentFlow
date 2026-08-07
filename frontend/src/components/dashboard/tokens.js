/*
 * dashkit — shared tokens, formatters and table styles of the role
 * dashboards (IT + Admin). Components live in DashKit.jsx.
 */

export const ink = {
  primary: "#0F172A", muted: "#64748B", faint: "#94A3B8",
  line: "#E5E9F0", blue: "#2563EB",
};
export const PALETTE = ["#2563EB", "#0D9488", "#D97706", "#7C3AED", "#DB2777"]; // CVD-validated
export const card = {
  background: "#fff", border: `1px solid ${ink.line}`,
  borderRadius: 14, padding: "16px 18px",
};
export const mono = { fontFamily: "ui-monospace, Consolas, monospace", fontSize: 11.5 };
export const AXIS = { fontSize: 11, fill: ink.muted };
export const TIP = {
  contentStyle: { fontSize: 12, borderRadius: 10, border: `1px solid ${ink.line}` },
};

export const ms = (v) =>
  v == null ? "—" : v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${Math.round(v)}ms`;
export const money = (v) =>
  v == null ? "—" : v === 0 ? "$0" : `$${v.toFixed(v < 0.01 ? 4 : 2)}`;
export const compact = (v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : `${v}`);
export const day = (iso) =>
  new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

/* table cell styles shared by dashboard tables */
export const th = {
  textAlign: "left", fontSize: 11, color: ink.muted, fontWeight: 600,
  padding: "8px 12px", borderBottom: `1px solid ${ink.line}`, whiteSpace: "nowrap",
};
export const td = {
  fontSize: 12.5, color: ink.primary, padding: "10px 12px",
  borderBottom: "1px solid #F3F4F6", fontVariantNumeric: "tabular-nums",
};
