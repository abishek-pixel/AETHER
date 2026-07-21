import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/common/GlassCard";
import { useAuthStore } from "@/store/auth";
import { useResearchStore } from "@/store/research";
import { getUserUsage } from "@/lib/api";
import { SessionsAreaChart, TokensBarChart, TopicsPieChart } from "@/components/visualization/AnalyticsCharts";
import { Activity, Clock, Coins, Sparkles, Zap, Loader2 } from "lucide-react";

export const Route = createFileRoute("/analytics")({
  head: () => ({ meta: [{ title: "Analytics — Aether" }] }),
  component: AnalyticsPage,
});

interface UsageData {
  total_tokens: number;
  total_cost: number;
  total_sessions: number;
  total_requests: number;
  credits_remaining: number;
  current_plan: string;
}

function AnalyticsPage() {
  const user = useAuthStore((s) => s.user);
  const sessions = useResearchStore((s) => s.sessions);
  const loadSessionsFromDB = useResearchStore((s) => s.loadSessionsFromDB);
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!user) return;
    loadSessionsFromDB();
    setIsLoading(true);
    getUserUsage()
      .then(setUsage)
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, [user]);

  const completedSessions = sessions.filter((s) => s.status === "done");
  const avgConf = completedSessions.length
    ? Math.round((completedSessions.reduce((a, s) => a + s.confidence, 0) / completedSessions.length) * 100)
    : 0;
  const timeSavedHrs = Math.round(completedSessions.length * 1.8);

  const stats = [
    {
      label: "Total sessions",
      value: isLoading ? "—" : String(usage?.total_sessions ?? completedSessions.length),
      icon: Activity,
    },
    {
      label: "Tokens used",
      value: isLoading ? "—" : (usage?.total_tokens ?? 0).toLocaleString(),
      icon: Coins,
    },
    {
      label: "Tokens remaining",
      value: isLoading ? "—" : (usage?.credits_remaining ?? 0).toLocaleString(),
      icon: Zap,
    },
    {
      label: "Avg confidence",
      value: `${avgConf}%`,
      icon: Sparkles,
    },
    {
      label: "Est. time saved",
      value: `${timeSavedHrs}h`,
      icon: Clock,
    },
    {
      label: "API cost",
      value: isLoading ? "—" : `$${(usage?.total_cost ?? 0).toFixed(4)}`,
      icon: Coins,
    },
  ];

  return (
    <AppShell title="Analytics">
      <div className="mx-auto max-w-6xl p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
            <p className="text-sm text-muted-foreground">
              {user ? `Usage data for ${user.email}` : "Sign in to view your analytics."}
            </p>
          </div>
          {isLoading && <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />}
        </div>

        {/* Plan badge */}
        {usage && (
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs text-primary-glow">
            <Zap className="h-3 w-3" />
            {usage.current_plan.charAt(0).toUpperCase() + usage.current_plan.slice(1)} plan
            · {usage.credits_remaining.toLocaleString()} credits remaining
          </div>
        )}

        {/* Stat grid */}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {stats.map((s) => (
            <GlassCard key={s.label} className="p-4">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <s.icon className="h-3.5 w-3.5" /> {s.label}
              </div>
              <div className="mt-2 text-2xl font-semibold text-gradient">{s.value}</div>
            </GlassCard>
          ))}
        </div>

        {/* Charts */}
        <div className="grid gap-4 lg:grid-cols-2">
          <GlassCard className="p-4">
            <div className="mb-2 text-sm font-medium">Sessions over time</div>
            <SessionsAreaChart sessions={completedSessions} />
          </GlassCard>
          <GlassCard className="p-4">
            <div className="mb-2 text-sm font-medium">Token usage</div>
            <TokensBarChart totalTokens={usage?.total_tokens ?? 0} usedTokens={usage?.total_tokens ?? 0} />
          </GlassCard>
          <GlassCard className="p-4 lg:col-span-2">
            <div className="mb-2 text-sm font-medium">Top topics</div>
            <TopicsPieChart sessions={completedSessions} />
          </GlassCard>
        </div>
      </div>
    </AppShell>
  );
}
