/* Data Agent — shared UI constants (components import from here). */
import { ink } from "../../dashboard/tokens";

export const DIALECTS = [
  { name: "postgres", label: "PostgreSQL", port: 5432 },
  { name: "mysql", label: "MySQL", port: 3306 },
  { name: "mssql", label: "SQL Server", port: 1433 },
];
export const dialectLabel = (d) =>
  DIALECTS.find((x) => x.name === d)?.label || d;

export const STATUS = {
  draft: { bg: "#F1F5F9", color: "#475569", label: "DRAFT" },
  connected: { bg: "#EFF6FF", color: "#1D4ED8", label: "CONNECTED" },
  trained: { bg: "#EEF2FF", color: "#4338CA", label: "TRAINED" },
  stale: { bg: "#FFFBEB", color: "#92400E", label: "RE-TRAIN NEEDED" },
  deployed: { bg: "#F0FDF4", color: "#166534", label: "DEPLOYED" },
  error: { bg: "#FEF2F2", color: "#991B1B", label: "ERROR" },
};

export const inputStyle = {
  width: "100%", border: `1px solid ${ink.line}`, borderRadius: 9,
  padding: "9px 12px", font: "500 13px system-ui", color: ink.primary,
  outline: "none", boxSizing: "border-box",
};

export const btn = (primary) => ({
  display: "inline-flex", alignItems: "center", gap: 7, padding: "9px 16px",
  borderRadius: 10, font: "600 13px system-ui", cursor: "pointer",
  border: primary ? "none" : `1px solid ${ink.blue}`,
  background: primary ? ink.blue : "#fff", color: primary ? "#fff" : ink.blue,
});
