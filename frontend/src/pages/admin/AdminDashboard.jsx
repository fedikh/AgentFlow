import React, { useEffect, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  Bot, Building2, Coins, FlaskConical, Gauge, KeyRound, MessageSquare,
  Users, Zap,
} from "lucide-react";
import { getUser } from "../../services/authApi";
import { getAdminDashboard } from "../../services/ragApi";
import {
  Badge, ChartCard, Donut, Kpi, Metric, SectionTitle,
} from "../../components/dashboard/DashKit";
import {
  AXIS, card, compact, day, ink, money, ms, td, th, TIP,
} from "../../components/dashboard/tokens";

/*
 * Admin Dashboard — the whole organization in one call (getAdminDashboard):
 *   org KPIs → cost KPIs → users & departments band →
 *   cost-per-day hero + cost-by-department donut →
 *   all-spaces table → usage charts.
 */

const AdminDashboard = () => {
  const user = getUser();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getAdminDashboard().then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <div style={{ ...card, color: "#B91C1C" }}>{error}</div>;
  if (!data) return <div style={{ ...card, color: ink.muted }}>Loading…</div>;

  const { kpis, users, departments, spaces, charts } = data;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      {/* header */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: ink.primary, letterSpacing: "-0.3px", margin: 0 }}>
            Organization dashboard
          </h1>
          <p style={{ fontSize: 13, color: ink.muted, margin: "3px 0 0" }}>
            Everything at <strong>{user?.org_name}</strong> — people, agents, usage and spend
          </p>
        </div>
        <span style={{ marginLeft: "auto", fontSize: 11, color: ink.muted, background: "#F1F5F9", borderRadius: 20, padding: "4px 11px" }}>
          Last 14 days · costs estimated
        </span>
      </div>

      {/* org KPIs */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Kpi icon={<Users size={16} />} label="Users" value={users.total ?? 0}
             sub={`${users.pending ?? 0} pending · ${users.active_30d ?? 0} active / 30d`} />
        <Kpi icon={<Building2 size={16} />} label="Departments" value={kpis.departments ?? 0} />
        <Kpi icon={<Bot size={16} />} label="RAG spaces" value={kpis.spaces ?? 0}
             sub={`${kpis.deployed ?? 0} deployed`} />
        <Kpi icon={<MessageSquare size={16} />} label="Conversations · 7d" value={kpis.conversations_7d ?? 0}
             delta={kpis.deltas?.conversations_7d} sub="vs previous week" />
        <Kpi icon={<Gauge size={16} />} label="Avg latency" value={ms(kpis.avg_latency_ms)} sub="answers, 7 days" />
      </div>

      {/* cost KPIs */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Kpi icon={<Coins size={16} />} label="Cost today" value={money(kpis.cost_day)} sub="estimated" />
        <Kpi icon={<Coins size={16} />} label="Cost · 7 days" value={money(kpis.cost_week)}
             delta={kpis.deltas?.cost_week} invert sub="vs previous week" />
        <Kpi icon={<Coins size={16} />} label="Cost · 30 days" value={money(kpis.cost_month)} sub="estimated" />
        <Kpi icon={<FlaskConical size={16} />} label="Spent on tests" value={money(kpis.test_cost)} sub="all evaluations" />
        <Kpi icon={<Zap size={16} />} label="Tokens · 30d" value={compact(kpis.tokens_30d ?? 0)} sub="estimated" />
        <Kpi icon={<KeyRound size={16} />} label="API today" value={kpis.api_requests_today ?? 0} sub="requests" />
      </div>

      {/* departments rollup — flex so the last row always fills the width */}
      <SectionTitle icon={<Building2 size={15} />}>Departments</SectionTitle>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {departments.map((d) => (
          <div key={d.name} style={{ ...card, flex: 1, minWidth: 250 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
              <div style={{ fontWeight: 700, fontSize: 13.5 }}>{d.name}</div>
              <div style={{ fontSize: 11, color: ink.muted }}>{d.members} member{d.members > 1 ? "s" : ""}</div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginTop: 12 }}>
              <Metric label="Spaces" value={`${d.deployed}/${d.spaces}`} />
              <Metric label="Docs" value={d.docs} />
              <Metric label="Conv · 30d" value={d.conversations_30d} />
              <Metric label="Cost · 30d" value={money(d.cost_month)} strong />
            </div>
          </div>
        ))}
      </div>

      {/* spend: hero cost/day + donut by department */}
      <SectionTitle icon={<Coins size={15} />}>Spend</SectionTitle>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12 }}>
        <ChartCard title="Cost per day" sub="all spaces, estimated" span={2} height={225}>
          <AreaChart data={charts.cost_per_day}>
            <CartesianGrid stroke="#F1F5F9" vertical={false} />
            <XAxis dataKey="date" tick={AXIS} tickFormatter={day} tickLine={false} axisLine={false} />
            <YAxis tick={AXIS} tickFormatter={(v) => `$${v}`} width={48} tickLine={false} axisLine={false} />
            <Tooltip {...TIP} labelFormatter={day} formatter={(v) => [money(v), "cost"]} />
            <Area dataKey="value" stroke={ink.blue} strokeWidth={2} fill={ink.blue} fillOpacity={0.12} />
          </AreaChart>
        </ChartCard>

        <ChartCard title="Cost by department" sub="30 days, estimated" height={225} raw>
          <Donut data={charts.cost_by_department} totalLabel="30 days"
                 format={money} height={225} />
        </ChartCard>
      </div>

      {/* every space, with owner */}
      <SectionTitle icon={<Bot size={15} />}>All RAG spaces</SectionTitle>
      <div style={{ ...card, padding: 0, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={th}>Space</th><th style={th}>Department</th><th style={th}>Owner</th>
              <th style={th}>Status</th><th style={th}>Docs · Chunks</th><th style={th}>Queries · 30d</th>
              <th style={th}>Tokens · 30d</th><th style={th}>Cost · 30d</th><th style={th}>Tests</th>
              <th style={th}>Latency</th><th style={th}>API today</th>
            </tr>
          </thead>
          <tbody>
            {spaces.map((s) => (
              <tr key={s.id}>
                <td style={{ ...td, fontWeight: 600 }}>{s.name}</td>
                <td style={td}>{s.department}</td>
                <td style={td}>{s.owner}</td>
                <td style={td}><Badge status={s.status} /></td>
                <td style={td}>{s.docs} · {s.chunks}</td>
                <td style={td}>{s.queries_month}</td>
                <td style={td}>{compact(s.tokens_30d)}</td>
                <td style={{ ...td, fontWeight: 700 }}>{money(s.cost.month)}</td>
                <td style={td}>{money(s.cost.tests)}</td>
                <td style={td}>{ms(s.latency_ms)}</td>
                <td style={td}>{s.api.enabled ? s.api.requests_today : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* usage charts — three equal, no orphan cells */}
      <SectionTitle icon={<Gauge size={15} />}>Usage</SectionTitle>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12 }}>
        <ChartCard title="Conversations per day" sub="all agents">
          <AreaChart data={charts.conversations_per_day}>
            <CartesianGrid stroke="#F1F5F9" vertical={false} />
            <XAxis dataKey="date" tick={AXIS} tickFormatter={day} tickLine={false} axisLine={false} />
            <YAxis tick={AXIS} allowDecimals={false} width={28} tickLine={false} axisLine={false} />
            <Tooltip {...TIP} labelFormatter={day} formatter={(v) => [v, "conversations"]} />
            <Area dataKey="value" stroke={ink.blue} strokeWidth={2} fill={ink.blue} fillOpacity={0.12} />
          </AreaChart>
        </ChartCard>

        <ChartCard title="Most used chatbots" sub="conversations, 30 days">
          <BarChart data={charts.most_used} layout="vertical">
            <CartesianGrid stroke="#F1F5F9" horizontal={false} />
            <XAxis type="number" tick={AXIS} allowDecimals={false} tickLine={false} axisLine={false} />
            <YAxis type="category" dataKey="name" tick={AXIS} width={120} tickLine={false} axisLine={false} />
            <Tooltip {...TIP} formatter={(v) => [v, "conversations"]} />
            <Bar dataKey="value" fill={ink.blue} radius={[0, 4, 4, 0]} barSize={15} />
          </BarChart>
        </ChartCard>

        <ChartCard title="Usage per user" sub="questions asked, 30 days">
          <BarChart data={charts.usage_per_user} layout="vertical">
            <CartesianGrid stroke="#F1F5F9" horizontal={false} />
            <XAxis type="number" tick={AXIS} allowDecimals={false} tickLine={false} axisLine={false} />
            <YAxis type="category" dataKey="name" tick={AXIS} width={120} tickLine={false} axisLine={false} />
            <Tooltip {...TIP} formatter={(v) => [v, "questions"]} />
            <Bar dataKey="value" fill={ink.blue} radius={[0, 4, 4, 0]} barSize={15} />
          </BarChart>
        </ChartCard>
      </div>
    </div>
  );
};

export default AdminDashboard;
