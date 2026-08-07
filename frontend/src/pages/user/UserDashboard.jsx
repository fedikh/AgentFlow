import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Area, AreaChart, CartesianGrid, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  ArrowRight, Bot, Gauge, MessageSquare, Sparkles, Star, Timer,
} from "lucide-react";
import { getUser } from "../../services/authApi";
import { getUserDashboard } from "../../services/ragApi";
import { ChartCard, Donut, Kpi, SectionTitle } from "../../components/dashboard/DashKit";
import { AXIS, card, day, ink, ms, TIP } from "../../components/dashboard/tokens";

/*
 * End-user dashboard — continuity, not analytics:
 *   personal stats → my agents (most-used first, click to chat) →
 *   what's new in my department (recent deploys).
 */

const timeAgo = (iso) => {
  const d = new Date(String(iso).replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return "";
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 3600) return "just now";
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
};

/* end-user language: ONLINE / UPDATING */
function OnlineBadge({ status }) {
  const editing = status === "EDITING";
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: "2px 9px", borderRadius: 20,
      background: editing ? "#FFFBEB" : "#F0FDF4",
      color: editing ? "#92400E" : "#166534", flexShrink: 0,
    }}>
      {editing ? "UPDATING…" : "ONLINE"}
    </span>
  );
}

const UserDashboard = () => {
  const user = getUser();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getUserDashboard().then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <div style={{ ...card, color: "#B91C1C" }}>{error}</div>;
  if (!data) return <div style={{ ...card, color: ink.muted }}>Loading…</div>;

  const { stats, agents, whats_new: whatsNew, charts } = data;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 800, color: ink.primary, letterSpacing: "-0.3px", margin: 0 }}>
          Welcome back, {user?.name?.split(" ")[0] || "there"}
        </h1>
        <p style={{ fontSize: 13, color: ink.muted, margin: "3px 0 0" }}>
          Your AI assistants, ready to answer from your department's documents.
        </p>
      </div>

      {/* 1 — personal stats */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Kpi icon={<MessageSquare size={16} />} label="Questions asked" value={stats.questions_7d}
             delta={stats.questions_delta} sub="vs previous week" />
        <Kpi icon={<Bot size={16} />} label="My conversations" value={stats.conversations} sub="all time" />
        <Kpi icon={<Timer size={16} />} label="Avg answer time" value={ms(stats.avg_answer_ms)} sub="last 7 days" />
        <Kpi icon={<Star size={16} />} label="Most used agent" value={stats.favorite_agent || "—"} />
      </div>

      {/* 2 — my agents, most-used first */}
      <SectionTitle icon={<Bot size={15} />}>My agents</SectionTitle>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {agents.length === 0 && (
          <div style={{ ...card, color: ink.muted }}>
            No agents available yet — your IT team hasn't deployed one for your department.
          </div>
        )}
        {agents.map((a) => (
          <button
            key={a.id}
            onClick={() => navigate(`/user/agents/${a.id}`)}
            style={{
              ...card, flex: 1, minWidth: 260, maxWidth: 420, textAlign: "left",
              cursor: "pointer", display: "grid", gap: 10, font: "inherit",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{
                width: 34, height: 34, borderRadius: 10, background: ink.primary,
                color: "#fff", display: "grid", placeItems: "center",
                fontWeight: 800, fontSize: 14, flexShrink: 0,
              }}>
                {(a.name || "?").trim()[0]?.toUpperCase()}
              </span>
              <span style={{ minWidth: 0, flex: 1 }}>
                <span style={{ display: "block", fontWeight: 700, fontSize: 13.5, color: ink.primary, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {a.name}
                </span>
                <span style={{ display: "block", fontSize: 11, color: ink.muted }}>{a.department}</span>
              </span>
              <OnlineBadge status={a.status} />
            </div>
            <div style={{ fontSize: 12, color: ink.muted, minHeight: 16, overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
              {a.description || "AI assistant powered by your documents."}
            </div>
            <div style={{ display: "flex", alignItems: "center", fontSize: 11.5, color: ink.muted }}>
              {a.my_conversations > 0
                ? `${a.my_conversations} conversation${a.my_conversations > 1 ? "s" : ""}`
                : "Never used yet"}
              <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 4, color: ink.blue, fontWeight: 600 }}>
                Open chat <ArrowRight size={12} />
              </span>
            </div>
          </button>
        ))}
      </div>

      {/* my activity charts */}
      <SectionTitle icon={<Gauge size={15} />}>My activity</SectionTitle>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12 }}>
        <ChartCard title="Questions per day" sub="last 14 days" span={2} height={200}>
          <AreaChart data={charts.activity}>
            <CartesianGrid stroke="#F1F5F9" vertical={false} />
            <XAxis dataKey="date" tick={AXIS} tickFormatter={day} tickLine={false} axisLine={false} />
            <YAxis tick={AXIS} allowDecimals={false} width={26} tickLine={false} axisLine={false} />
            <Tooltip {...TIP} labelFormatter={day} formatter={(v) => [v, "questions"]} />
            <Area dataKey="value" stroke={ink.blue} strokeWidth={2} fill={ink.blue} fillOpacity={0.12} />
          </AreaChart>
        </ChartCard>
        <ChartCard title="My conversations by agent" sub="all time" height={200} raw>
          <Donut data={charts.by_agent} totalLabel="conversations" height={200} />
        </ChartCard>
      </div>

      {/* 3 — what's new in my department */}
      <SectionTitle icon={<Sparkles size={15} />}>New in my department</SectionTitle>
      <div style={card}>
        {whatsNew.length === 0 ? (
          <div style={{ fontSize: 12.5, color: ink.muted }}>
            Nothing new these last 14 days — updates from your IT team will appear here.
          </div>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {whatsNew.map((w, i) => (
              <div key={i} style={{ display: "flex", alignItems: "baseline", gap: 9, fontSize: 12.5 }}>
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: ink.blue, flexShrink: 0, alignSelf: "center" }} />
                <span>
                  <button
                    onClick={() => navigate(`/user/agents/${w.agent_id}`)}
                    style={{ border: "none", background: "none", padding: 0, font: "inherit", fontWeight: 700, color: ink.primary, cursor: "pointer" }}
                  >
                    {w.agent}
                  </button>{" "}
                  was updated ({w.label}){w.notes ? ` — ${w.notes}` : ""}
                </span>
                <span style={{ marginLeft: "auto", fontSize: 11, color: ink.faint, flexShrink: 0 }}>
                  {timeAgo(w.date)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default UserDashboard;
