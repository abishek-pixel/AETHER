import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { SearchBar } from "@/components/research/SearchBar";
import { useResearchStore } from "@/store/research";
import { useAuthStore } from "@/store/auth";
import { GlassCard } from "@/components/common/GlassCard";
import { ConfidenceMeter } from "@/components/research/ConfidenceMeter";
import { Button } from "@/components/ui/button";
import { formatSessionDate } from "@/lib/utils";
import { ArrowRight, Clock, Zap, Layers, Scale, Loader2, LogIn } from "lucide-react";
import { motion } from "framer-motion";

export const Route = createFileRoute("/dashboard")({
  head: () => ({ meta: [{ title: "Dashboard — Aether" }] }),
  component: DashboardPage,
});

function DashboardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const isInitialized = useAuthStore((s) => s.isInitialized);
  const sessions = useResearchStore((s) => s.sessions);
  const isFetching = useResearchStore((s) => s.isFetchingHistory);
  const loadSessionsFromDB = useResearchStore((s) => s.loadSessionsFromDB);

  // Reload sessions whenever the dashboard mounts (after research completes etc.)
  useEffect(() => {
    if (user) loadSessionsFromDB();
  }, [user]);

  // Only show completed sessions on the dashboard — and only for authenticated users.
  // Guests must see an empty state, never a previous user's or previous guest's sessions.
  const completedSessions = user
    ? sessions.filter((s) => s.status === "done")
    : [];

  return (
    <AppShell title="Dashboard">
      <div className="mx-auto max-w-6xl p-6 space-y-8">
        {/* Search bar */}
        <section>
          <div className="mb-4">
            <h1 className="text-2xl font-semibold tracking-tight">Start a new research session</h1>
            <p className="text-sm text-muted-foreground">Aether's swarm will plan, search, debate and write — live.</p>
          </div>
          <SearchBar />
        </section>

        {/* Recent sessions */}
        <section>
          <div className="mb-3 flex items-end justify-between">
            <h2 className="text-lg font-medium flex items-center gap-2">
              Recent sessions
              {isFetching && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
            </h2>
            <Link to="/analytics" className="text-xs text-primary-glow hover:underline">View analytics →</Link>
          </div>

          {/* Not logged in */}
          {isInitialized && !user && (
            <GlassCard className="p-8 text-center">
              <p className="text-sm text-muted-foreground mb-4">Sign in to see your research history.</p>
              <Button asChild size="sm">
                <Link to="/login"><LogIn className="mr-2 h-4 w-4" />Sign in</Link>
              </Button>
            </GlassCard>
          )}

          {/* Loading */}
          {isFetching && completedSessions.length === 0 && (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3].map((i) => (
                <GlassCard key={i} className="p-4 h-[120px] animate-pulse bg-muted/20" />
              ))}
            </div>
          )}

          {/* Empty state */}
          {!isFetching && user && completedSessions.length === 0 && (
            <GlassCard className="p-8 text-center">
              <p className="text-sm text-muted-foreground">No research sessions yet. Start your first one above!</p>
            </GlassCard>
          )}

          {/* Session cards */}
          {completedSessions.length > 0 && (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {completedSessions.map((s, i) => (
                <motion.div
                  key={s.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                >
                  <Link to="/research/$sessionId" params={{ sessionId: s.id }}>
                    <GlassCard className="p-4 h-full hover:border-primary/40 transition-colors" glow>
                      <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                        <DepthBadge depth={s.depth} />
                        <span>· {formatSessionDate(s.updatedAt)}</span>
                      </div>
                      <div className="mt-2 line-clamp-2 text-sm font-medium">{s.query}</div>
                      {s.confidence > 0 && (
                        <div className="mt-3">
                          <ConfidenceMeter value={s.confidence} label="Confidence" />
                        </div>
                      )}
                      <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {s.tokensUsed > 0 ? `${s.tokensUsed.toLocaleString()} tok` : s.model}
                        </span>
                        <ArrowRight className="h-3.5 w-3.5" />
                      </div>
                    </GlassCard>
                  </Link>
                </motion.div>
              ))}
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}

function DepthBadge({ depth }: { depth: string }) {
  const map: Record<string, { label: string; Icon: any }> = {
    fast:     { label: "Fast",     Icon: Zap },
    balanced: { label: "Balanced", Icon: Scale },
    deep:     { label: "Deep",     Icon: Layers },
  };
  const m = map[depth] ?? { label: depth, Icon: Scale };
  return (
    <span className="inline-flex items-center gap-1 rounded border border-primary/30 bg-primary/10 px-1.5 py-0.5 text-primary-glow">
      <m.Icon className="h-2.5 w-2.5" /> {m.label}
    </span>
  );
}
