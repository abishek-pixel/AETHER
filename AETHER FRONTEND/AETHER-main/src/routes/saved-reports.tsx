import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/common/GlassCard";
import { useResearchStore } from "@/store/research";
import { useAuthStore } from "@/store/auth";
import { Button } from "@/components/ui/button";
import { formatSessionDate } from "@/lib/utils";
import { FolderOpen, FileText, Clock, Sparkles, Loader2, LogIn, BookOpen } from "lucide-react";

export const Route = createFileRoute("/saved-reports")({
  head: () => ({ meta: [{ title: "Saved Reports — Aether" }] }),
  component: SavedReportsPage,
});

function SavedReportsPage() {
  const user = useAuthStore((s) => s.user);
  const sessions = useResearchStore((s) => s.sessions);
  const isFetching = useResearchStore((s) => s.isFetchingHistory);
  const loadSessionsFromDB = useResearchStore((s) => s.loadSessionsFromDB);

  useEffect(() => {
    if (user) loadSessionsFromDB();
  }, [user]);

  // Only show sessions that have a report — and only for authenticated users.
  const saved = user ? sessions.filter((s) => s.status === "done" && s.report) : [];

  return (
    <AppShell title="Saved Reports">
      <div className="mx-auto max-w-6xl p-6">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold flex items-center gap-2">
              <FolderOpen className="h-6 w-6 text-primary" /> Saved Reports
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              All your completed research, ready to revisit and export.
            </p>
          </div>
          <Button asChild size="sm">
            <Link to="/dashboard"><Sparkles className="mr-2 h-4 w-4" /> New research</Link>
          </Button>
        </header>

        {/* Not logged in */}
        {!user && (
          <GlassCard className="p-10 text-center">
            <LogIn className="mx-auto h-10 w-10 text-muted-foreground/60" />
            <h2 className="mt-4 text-lg font-medium">Sign in to view your reports</h2>
            <Button asChild className="mt-4"><Link to="/login">Sign in</Link></Button>
          </GlassCard>
        )}

        {/* Loading skeleton */}
        {isFetching && user && saved.length === 0 && (
          <div className="grid gap-4 md:grid-cols-2">
            {[1, 2, 3, 4].map((i) => (
              <GlassCard key={i} className="p-5 h-[140px] animate-pulse bg-muted/20" />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!isFetching && user && saved.length === 0 && (
          <GlassCard className="p-10 text-center">
            <FileText className="mx-auto h-10 w-10 text-muted-foreground/60" />
            <h2 className="mt-4 text-lg font-medium">No saved reports yet</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Run a research session and it will appear here once complete.
            </p>
            <Button asChild className="mt-4"><Link to="/dashboard">Start research</Link></Button>
          </GlassCard>
        )}

        {/* Report cards */}
        {saved.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2">
            {saved.map((s) => (
              <Link
                key={s.id}
                to="/research/$sessionId"
                params={{ sessionId: s.id }}
                className="block group"
              >
                <GlassCard className="p-5 h-full hover:border-primary/40 transition-colors">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-1.5">
                      <BookOpen className="h-3.5 w-3.5 text-primary" />
                      <span className="text-[10px] uppercase tracking-wider text-primary-glow font-medium">
                        {s.depth} research
                      </span>
                    </div>
                    <span className="text-[10px] text-muted-foreground">
                      {Math.round(s.confidence * 100)}% confidence
                    </span>
                  </div>
                  <h3 className="mt-3 text-sm font-medium line-clamp-2 group-hover:text-primary transition-colors">
                    {s.query}
                  </h3>
                  <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatSessionDate(s.updatedAt)}
                    </span>
                    <span>{s.citations.length} citations</span>
                    <span>{s.findings.length} findings</span>
                  </div>
                </GlassCard>
              </Link>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
