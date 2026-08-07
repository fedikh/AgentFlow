import React from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { TrendingDown, TrendingUp } from "lucide-react";
import { card, ink, PALETTE, TIP } from "./tokens";

/*
 * DashKit — the shared building blocks of the role dashboards (IT + Admin).
 * Tokens and formatters live in tokens.js.
 */

const STATUS = {
  ACTIVE: { bg: "#F0FDF4", color: "#166534", label: "DEPLOYED" },
  EDITING: { bg: "#FFFBEB", color: "#92400E", label: "EDITING" },
  DRAFT: { bg: "#F1F5F9", color: "#475569", label: "DRAFT" },
};

export function Badge({ status }) {
  const s = STATUS[status] || STATUS.DRAFT;
  return (
    <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 9px", borderRadius: 20, background: s.bg, color: s.color, flexShrink: 0 }}>
      {s.label}
    </span>
  );
}

/* delta: % vs previous period. invert=true → an increase reads as bad (costs). */
export function Kpi({ icon, label, value, sub, delta, invert = false }) {
  const up = delta != null && delta > 0;
  const good = delta != null && (invert ? delta < 0 : delta > 0);
  return (
    <div style={{ ...card, flex: 1, minWidth: 160, display: "flex", gap: 12, padding: "14px 16px" }}>
      <div style={{
        width: 38, height: 38, borderRadius: 11, background: "#EFF6FF",
        display: "grid", placeItems: "center", color: ink.blue, flexShrink: 0,
      }}>
        {icon}
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <span style={{ fontSize: 21, fontWeight: 800, color: ink.primary, fontVariantNumeric: "tabular-nums" }}>
            {value}
          </span>
          {delta != null && delta !== 0 && (
            <span style={{
              display: "inline-flex", alignItems: "center", gap: 3,
              fontSize: 11, fontWeight: 700,
              color: good ? "#16A34A" : "#DC2626",
            }}>
              {up ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
              {up ? "+" : ""}{delta}%
            </span>
          )}
        </div>
        <div style={{ fontSize: 11.5, color: ink.muted }}>{label}</div>
        {sub && <div style={{ fontSize: 10.5, color: ink.faint, marginTop: 1 }}>{sub}</div>}
      </div>
    </div>
  );
}

/* donut with a CENTER TOTAL + right-side legend (name, value, share) */
export function Donut({ data, total, totalLabel, format = (v) => v, height = 205 }) {
  const sum = total ?? data.reduce((a, x) => a + x.value, 0);
  if (!data.length) {
    return (
      <div style={{ display: "grid", placeItems: "center", height, color: ink.faint, fontSize: 12 }}>
        No data yet
      </div>
    );
  }
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 18, height }}>
      <div style={{ position: "relative", width: 160, height: 160, flexShrink: 0 }}>
        <PieChart width={160} height={160}>
          <Tooltip {...TIP} formatter={(v, n) => [format(v), n]} />
          <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%"
               innerRadius={54} outerRadius={76} paddingAngle={3} strokeWidth={2}>
            {data.map((e, i) => <Cell key={e.name} fill={PALETTE[i % PALETTE.length]} />)}
          </Pie>
        </PieChart>
        <div style={{
          position: "absolute", inset: 0, display: "grid", placeItems: "center",
          pointerEvents: "none",
        }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: ink.primary, fontVariantNumeric: "tabular-nums" }}>
              {format(sum)}
            </div>
            {totalLabel && <div style={{ fontSize: 10, color: ink.muted }}>{totalLabel}</div>}
          </div>
        </div>
      </div>
      <div style={{ display: "grid", gap: 9, minWidth: 0, flex: 1 }}>
        {data.map((e, i) => (
          <div key={e.name} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
            <span style={{ width: 9, height: 9, borderRadius: 3, background: PALETTE[i % PALETTE.length], flexShrink: 0 }} />
            <span style={{ color: ink.muted, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {e.name}
            </span>
            <span style={{ fontWeight: 700, color: ink.primary, fontVariantNumeric: "tabular-nums" }}>
              {format(e.value)}
            </span>
            <span style={{ color: ink.faint, fontSize: 11, width: 34, textAlign: "right" }}>
              {sum ? Math.round((e.value / sum) * 100) : 0}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Metric({ label, value, strong }) {
  return (
    <div>
      <div style={{ fontSize: 10.5, color: ink.muted }}>{label}</div>
      <div style={{ fontSize: strong ? 15 : 13, fontWeight: 700, color: ink.primary, fontVariantNumeric: "tabular-nums" }}>
        {value}
      </div>
    </div>
  );
}

export function SectionTitle({ icon, children }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13.5, fontWeight: 800, color: ink.primary }}>
      {icon} {children}
    </div>
  );
}

/* raw=true → the child manages its own size (e.g. Donut); otherwise the
   child is a Recharts chart wrapped in a ResponsiveContainer */
export function ChartCard({ title, sub, height = 205, span, raw, children }) {
  return (
    <div style={{ ...card, gridColumn: span ? `span ${span}` : undefined, minWidth: 0 }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: ink.primary }}>{title}</div>
      {sub && <div style={{ fontSize: 11, color: ink.faint, marginTop: 1 }}>{sub}</div>}
      <div style={{ marginTop: 10 }}>
        {raw ? children : (
          <ResponsiveContainer width="100%" height={height}>{children}</ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
