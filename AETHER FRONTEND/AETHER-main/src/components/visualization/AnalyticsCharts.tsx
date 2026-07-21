/**
 * Analytics charts — driven by real session data, no hardcoded values.
 */
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, Legend,
} from "recharts";
import type { ResearchSession } from "@/types";

const COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];
const TOOLTIP_STYLE = {
  background: "oklch(0.20 0.025 265)",
  border: "1px solid oklch(1 0 0 / 0.1)",
  borderRadius: 8,
  fontSize: 12,
};

// ── Sessions over time ────────────────────────────────────────────────────

interface SessionsAreaChartProps {
  sessions: ResearchSession[];
}

export function SessionsAreaChart({ sessions }: SessionsAreaChartProps) {
  // Build daily counts for last 14 days
  const now = Date.now();
  const days = Array.from({ length: 14 }, (_, i) => {
    const d = new Date(now - (13 - i) * 86_400_000);
    return {
      day: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      ts: d.setHours(0, 0, 0, 0),
      sessions: 0,
    };
  });

  sessions.forEach((s) => {
    const dayStart = new Date(s.updatedAt).setHours(0, 0, 0, 0);
    const bucket = days.find((d) => d.ts === dayStart);
    if (bucket) bucket.sessions++;
  });

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={days} margin={{ left: -20, right: 8, top: 8 }}>
        <defs>
          <linearGradient id="sg" x1="0" x2="0" y1="0" y2="1">
            <stop offset="5%"  stopColor="oklch(0.66 0.22 280)" stopOpacity={0.6} />
            <stop offset="95%" stopColor="oklch(0.66 0.22 280)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeOpacity={0.08} />
        <XAxis dataKey="day" stroke="oklch(0.68 0.02 260)" fontSize={10} interval={3} />
        <YAxis stroke="oklch(0.68 0.02 260)" fontSize={11} allowDecimals={false} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Area type="monotone" dataKey="sessions" stroke="oklch(0.74 0.22 290)" fill="url(#sg)" strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ── Token usage ───────────────────────────────────────────────────────────

interface TokensBarChartProps {
  totalTokens: number;
  usedTokens: number;
}

export function TokensBarChart({ totalTokens, usedTokens }: TokensBarChartProps) {
  const FREE_LIMIT = 100_000;
  const remaining = Math.max(0, FREE_LIMIT - usedTokens);
  const data = [
    { label: "Used",      tokens: usedTokens },
    { label: "Remaining", tokens: remaining },
  ];

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ left: -10, right: 8, top: 8 }}>
        <CartesianGrid strokeOpacity={0.08} />
        <XAxis dataKey="label" stroke="oklch(0.68 0.02 260)" fontSize={11} />
        <YAxis stroke="oklch(0.68 0.02 260)" fontSize={11} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(v: number) => [v.toLocaleString(), "tokens"]}
        />
        <Bar dataKey="tokens" radius={[6, 6, 0, 0]}>
          <Cell fill="oklch(0.74 0.22 290)" />
          <Cell fill="oklch(0.58 0.10 260)" />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Top topics ────────────────────────────────────────────────────────────

interface TopicsPieChartProps {
  sessions: ResearchSession[];
}

export function TopicsPieChart({ sessions }: TopicsPieChartProps) {
  // Extract topic from session.topic or first 3 words of query
  const topicCounts: Record<string, number> = {};
  sessions.forEach((s) => {
    const topic = (s.topic ?? s.query.split(" ").slice(0, 3).join(" ")).slice(0, 30);
    topicCounts[topic] = (topicCounts[topic] ?? 0) + 1;
  });

  const data = Object.entries(topicCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([name, value]) => ({ name, value }));

  if (!data.length) {
    return (
      <div className="flex h-[220px] items-center justify-center text-sm text-muted-foreground italic">
        No session data yet.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie data={data} dataKey="value" innerRadius={50} outerRadius={80} paddingAngle={3}>
          {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Pie>
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(v: number, name: string) => [v, name]}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: "oklch(0.68 0.02 260)" }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
