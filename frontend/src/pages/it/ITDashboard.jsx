import React, { useEffect, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  Bot, Building2, Coins, FileText, Gauge, KeyRound, MessageSquare, Search, Zap,
} from "lucide-react";
import { getUser } from "../../services/authApi";
import { getItDashboard } from "../../services/ragApi";

/*
 * IT Dashboard — one call (getItDashboard). Deliberate composition, no
 * orphan cells:
 *   KPI strip
 *   departments (side column)  |  live-space cards (rich, per space)
 *   charts: hero (2/3) + donut (1/3), then three equal charts
 */

import {
  Badge, ChartCard, Donut, Kpi, Metric, SectionTitle,
} from "../../components/dashboard/DashKit";
import {
  AXIS, card, compact, day, ink, mono, money, ms, TIP,
} from "../../components/dashboard/tokens";

/* one rich card per live space */
function SpaceCard({ s, style }) {
  return (
    <div style={{ ...card, display: "grid", gap: 12, alignContent: "start", ...style }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{
          width: 34, height: 34, borderRadius: 10, background: ink.primary, color: "#fff",
          display: "grid", placeItems: "center", fontWeight: 800, fontSize: 14, flexShrink: 0,
        }}>
          {(s.name || "?").trim()[0]?.toUpperCase()}
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 13.5, color: ink.primary, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {s.name}
          </div>
          <div style={{ fontSize: 11, color: ink.muted }}>
            {s.department} · {s.docs} docs · {s.chunks} chunks
          </div>
        </div>
        <Badge status={s.status} />
      </div>

      <div style={{ height: 42 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={s.spark} margin={{ top: 2, bottom: 0, left: 0, right: 0 }}>
            <Tooltip {...TIP} labelFormatter={day} formatter={(v) => [v, "messages"]} />
            <Area dataKey="value" stroke={ink.blue} strokeWidth={1.6} fill={ink.blue} fillOpacity={0.1} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, background: "#F8FAFC", borderRadius: 10, padding: "10px 12px" }}>
        <Metric label="Cost / day" value={money(s.cost.day)} strong />
        <Metric label="Cost / week" value={money(s.cost.week)} strong />
        <Metric label="Cost / month" value={money(s.cost.month)} strong />
        <Metric label="Tests" value={money(s.cost.tests)} strong />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
        <Metric label="Tokens · 30d" value={compact(s.tokens_30d)} />
        <Metric label="Queries · 30d" value={s.queries_month} />
        <Metric label="Latency" value={ms(s.latency_ms)} />
        <Metric label="Retrieval" value={ms(s.retrieval_ms)} />
      </div>

      <div style={{ borderTop: `1px dashed ${ink.line}`, paddingTop: 10, display: "grid", gap: 5 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 11.5 }}>
          <KeyRound size={12} color={s.api.enabled ? "#16A34A" : ink.faint} />
          <span style={{ fontWeight: 700, color: s.api.enabled ? "#166534" : ink.muted }}>
            {s.api.enabled ? `API enabled · ${s.api.keys} key${s.api.keys > 1 ? "s" : ""}` : "API — no key yet"}
          </span>
          {s.api.enabled && (
            <span style={{ marginLeft: "auto", color: ink.muted }}>
              {s.api.requests_today} today · {s.api.requests_30d} / 30d · {money(s.api.cost_30d)}
            </span>
          )}
        </div>
        <div style={{ ...mono, color: ink.muted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          POST {s.api.endpoint}{s.api.key_display ? `  ·  ${s.api.key_display}` : ""}
        </div>
      </div>
    </div>
  );
}

/* ── the page ────────────────────────────────────────────── */

const ITDashboard = () => {
  const user = getUser();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getItDashboard().then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <div style={{ ...card, color: "#B91C1C" }}>{error}</div>;
  if (!data) return <div style={{ ...card, color: ink.muted }}>Loading…</div>;

  const { kpis, departments, spaces, charts } = data;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      {/* header */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: ink.primary, letterSpacing: "-0.3px", margin: 0 }}>
            Dashboard
          </h1>
          <p style={{ fontSize: 13, color: ink.muted, margin: "3px 0 0" }}>
            RAG spaces, costs and API activity at <strong>{user?.org_name}</strong>
          </p>
        </div>
        <span style={{ marginLeft: "auto", fontSize: 11, color: ink.muted, background: "#F1F5F9", borderRadius: 20, padding: "4px 11px" }}>
          Last 14 days · costs estimated
        </span>
      </div>

      {/* KPI strip */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Kpi icon={<Coins size={16} />} label="Cost this month" value={money(kpis.cost_month)} sub="all spaces, estimated" />
        <Kpi icon={<Zap size={16} />} label="Tokens · 30d" value={compact(kpis.tokens_30d ?? 0)} sub="estimated" />
        <Kpi icon={<MessageSquare size={16} />} label="Conversations · 7d" value={kpis.conversations_7d ?? 0}
             delta={kpis.deltas?.conversations_7d} sub="vs previous week" />
        <Kpi icon={<Gauge size={16} />} label="Avg latency" value={ms(kpis.avg_latency_ms)} sub="answers, 7 days" />
        <Kpi icon={<Search size={16} />} label="Avg retrieval" value={ms(kpis.avg_retrieval_ms)} sub="from evaluations" />
        <Kpi icon={<KeyRound size={16} />} label="API today" value={kpis.api_requests_today ?? 0} sub="requests" />
      </div>

      {/* departments (side) | live spaces (main) — one balanced band */}
      <div style={{ display: "grid", gridTemplateColumns: "minmax(260px, 300px) 1fr", gap: 12, alignItems: "start" }}>
        <div style={{ display: "grid", gap: 12 }}>
          <SectionTitle icon={<Building2 size={15} />}>My departments</SectionTitle>
          {departments.map((d) => (
            <div key={d.name} style={card}>
              <div style={{ fontWeight: 700, fontSize: 13.5 }}>{d.name}</div>
              <div style={{ fontSize: 11, color: ink.muted, marginTop: 2 }}>
                <FileText size={10} style={{ verticalAlign: -1 }} /> {d.docs} docs · {d.chunks} chunks
              </div>
              <div style={{ display: "grid", gap: 7, marginTop: 10 }}>
                {d.spaces.map((s) => (
                  <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5 }}>
                    <Badge status={s.status} />
                    <span style={{ fontWeight: 600, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {s.name}
                    </span>
                    <span style={{ color: ink.faint, fontSize: 11 }}>{s.docs}·{s.chunks}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: "grid", gap: 12 }}>
          <SectionTitle icon={<Bot size={15} />}>Live spaces</SectionTitle>
          {/* fixed 2-col grid; an odd last card spans the full row — no orphan gap */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}>
            {spaces.length === 0 && <div style={{ ...card, color: ink.muted }}>No deployed spaces yet.</div>}
            {spaces.map((s, i) => (
              <SpaceCard
                key={s.id}
                s={s}
                style={i === spaces.length - 1 && spaces.length % 2 === 1
                  ? { gridColumn: "span 2" } : undefined}
              />
            ))}
          </div>
        </div>
      </div>

      {/* charts — 2/3 hero + 1/3 donut, then three equal: no orphan cells */}
      <SectionTitle icon={<Gauge size={15} />}>Usage & performance</SectionTitle>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12 }}>
        <ChartCard title="Conversations per day" sub="all my agents" span={2} height={225}>
          <AreaChart data={charts.conversations_per_day}>
            <CartesianGrid stroke="#F1F5F9" vertical={false} />
            <XAxis dataKey="date" tick={AXIS} tickFormatter={day} tickLine={false} axisLine={false} />
            <YAxis tick={AXIS} allowDecimals={false} width={28} tickLine={false} axisLine={false} />
            <Tooltip {...TIP} labelFormatter={day} formatter={(v) => [v, "conversations"]} />
            <Area dataKey="value" stroke={ink.blue} strokeWidth={2} fill={ink.blue} fillOpacity={0.12} />
          </AreaChart>
        </ChartCard>

        <ChartCard title="Cost share by space" sub="this month, estimated" height={225} raw>
          <Donut data={charts.cost_by_space} totalLabel="this month"
                 format={money} height={225} />
        </ChartCard>

        <ChartCard title="Token usage per day" sub="estimated, all agents">
          <BarChart data={charts.tokens_per_day}>
            <CartesianGrid stroke="#F1F5F9" vertical={false} />
            <XAxis dataKey="date" tick={AXIS} tickFormatter={day} tickLine={false} axisLine={false} />
            <YAxis tick={AXIS} tickFormatter={compact} width={40} tickLine={false} axisLine={false} />
            <Tooltip {...TIP} labelFormatter={day} formatter={(v) => [compact(v), "tokens"]} />
            <Bar dataKey="value" fill={ink.blue} radius={[4, 4, 0, 0]} barSize={13} />
          </BarChart>
        </ChartCard>

        <ChartCard title="Average latency" sub="ms per day">
          <LineChart data={charts.latency_per_day}>
            <CartesianGrid stroke="#F1F5F9" vertical={false} />
            <XAxis dataKey="date" tick={AXIS} tickFormatter={day} tickLine={false} axisLine={false} />
            <YAxis tick={AXIS} width={42} tickLine={false} axisLine={false} />
            <Tooltip {...TIP} labelFormatter={day} formatter={(v) => [ms(v), "avg latency"]} />
            <Line dataKey="value" stroke={ink.blue} strokeWidth={2} dot={false} />
          </LineChart>
        </ChartCard>

        <ChartCard title="Usage per user" sub="questions asked, 30 days">
          <BarChart data={charts.usage_per_user} layout="vertical">
            <CartesianGrid stroke="#F1F5F9" horizontal={false} />
            <XAxis type="number" tick={AXIS} allowDecimals={false} tickLine={false} axisLine={false} />
            <YAxis type="category" dataKey="name" tick={AXIS} width={125} tickLine={false} axisLine={false} />
            <Tooltip {...TIP} formatter={(v) => [v, "questions"]} />
            <Bar dataKey="value" fill={ink.blue} radius={[0, 4, 4, 0]} barSize={15} />
          </BarChart>
        </ChartCard>
      </div>
    </div>
  );
};

export default ITDashboard;
