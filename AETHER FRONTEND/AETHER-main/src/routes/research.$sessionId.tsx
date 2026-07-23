/**
 * Research page — threaded conversation view.
 *
 * Renders each ResearchBlock independently with its own tabs.
 * Follow-up prompts APPEND new blocks — previous blocks are never removed.
 * Sticky follow-up input always visible at the bottom.
 */
import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState, useCallback } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { useResearchStore } from "@/store/research";
import { useAuthStore } from "@/store/auth";
import { useResearchStream } from "@/hooks/useResearchStream";
import { AgentGraph } from "@/components/agents/AgentGraph";
import { ResearchBlockCard } from "@/components/research/ResearchBlockCard";
import { ExportMenu } from "@/components/research/ExportMenu";
import { GlassCard } from "@/components/common/GlassCard";
import { Button } from "@/components/ui/button";
import {
  AlertCircle, Loader2, Send, LogIn, RotateCw,
  MessageSquarePlus, Sparkles, Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useRateLimit } from "@/hooks/useRateLimit";

export const Route = createFileRoute("/research/$sessionId")({
  head: () => ({
    meta: [
      { title: "Research — Aether" },
      { name: "description", content: "Multi-agent research workspace." },
    ],
  }),
  component: ResearchPage,
});

function ResearchPage() {
  const { sessionId } = Route.useParams();
  const navigate = useNavigate();

  // Store
  const current = useResearchStore((s) => s.current);
  const loadSession = useResearchStore((s) => s.loadSession);
  const loadSessionFromDB = useResearchStore((s) => s.loadSessionFromDB);
  const resetCurrent = useResearchStore((s) => s.resetCurrent);
  const storeError = useResearchStore((s) => s.error);
  const resetError = useResearchStore((s) => s.resetError);
  const startFollowUpStream = useResearchStore((s) => s.startFollowUpStream);
  const followUpBackendId = useResearchStore((s) => s.followUpBackendId);

  // Auth
  const isAuthInitialized = useAuthStore((s) => s.isInitialized);
  const user = useAuthStore((s) => s.user);

  // Local state
  const [notFound, setNotFound] = useState(false);
  const [isLoadingFromDB, setIsLoadingFromDB] = useState(false);
  const [followUpQuery, setFollowUpQuery] = useState("");
  const [isFollowingUp, setIsFollowingUp] = useState(false);
  const [inputFocused, setInputFocused] = useState(false);

  // Rate-limit state (live countdown from backend)
  const rateLimit = useRateLimit();

  // Refresh rate-limit whenever a follow-up completes
  useEffect(() => {
    if (!user || followUpBackendId !== null) return;
    // followUpBackendId just became null → a follow-up finished → re-fetch
    rateLimit.triggerRefetch();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [followUpBackendId]);

  // Refs for auto-scroll
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const followUpAbortRef = useRef<(() => void) | null>(null);

  // ── Load session ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isAuthInitialized) return;

    // Optimistic: show the in-memory summary immediately while the full fetch runs
    const inMemory = loadSession(sessionId);

    // If the current session is still actively streaming (status idle/running) AND
    // its ID matches the URL param, don't hit the DB yet — the ID in the URL is
    // still the local crypto.randomUUID(). useResearchStream will promote to the
    // backend DB UUID and navigate, causing this effect to re-run with the real ID.
    const cur = useResearchStore.getState().current;
    const isActivelyStreaming =
      cur?.id === sessionId &&
      (cur.status === "idle" || cur.status === "running");
    if (isActivelyStreaming) {
      setIsLoadingFromDB(false);
      return;
    }

    let cancelled = false;
    setIsLoadingFromDB(true);
    setNotFound(false);

    async function fetchFull(): Promise<void> {
      // Try up to 3 times (handles the case where the session was just created
      // and the DB write is still in flight).
      for (let i = 0; i < 3; i++) {
        if (cancelled) return;
        try {
          const result = await loadSessionFromDB(sessionId);
          if (result) {
            if (!cancelled) setIsLoadingFromDB(false);
            return;
          }
        } catch (err: unknown) {
          // Intentional cancellation (component unmounted or timeout) — stop silently
          if (err instanceof DOMException && err.name === "AbortError") {
            return;
          }
          // 404 from server — session may not exist yet (race) or may never exist (anon)
          // Don't surface as a research failure; fall through to retry / inMemory fallback
        }
        if (i < 2) await new Promise((r) => setTimeout(r, 1500 * (i + 1)));
      }
      if (!cancelled) {
        setIsLoadingFromDB(false);
        // Only show notFound if we have no in-memory session either
        if (!inMemory) setNotFound(true);
      }
    }

    fetchFull();
    return () => { cancelled = true; };
    // Re-run whenever sessionId or auth state changes. Do NOT add `current` to
    // deps — that would cause an infinite re-fetch loop.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, isAuthInitialized]);

  // ── Start SSE for new (idle) sessions ────────────────────────────────────
  useResearchStream(current);

  // ── Auto-scroll to bottom when new block is added ────────────────────────
  const prevBlockCount = useRef(0);
  useEffect(() => {
    const blocks = current?.blocks ?? [];
    if (blocks.length > prevBlockCount.current) {
      prevBlockCount.current = blocks.length;
      // Scroll to newest block after render
      setTimeout(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    }
  }, [current?.blocks?.length]);

  // ── Follow-up submit ─────────────────────────────────────────────────────
  const handleFollowUp = useCallback(async () => {
    if (!followUpQuery.trim() || !current || isFollowingUp) return;
    const query = followUpQuery.trim();
    setFollowUpQuery("");
    setIsFollowingUp(true);
    try {
      const ctrl = await startFollowUpStream(
        current.id, query, current.depth, current.model,
      );
      followUpAbortRef.current = ctrl.abort;
    } catch (err) {
      console.error("Follow-up failed:", err);
    } finally {
      setIsFollowingUp(false);
    }
  }, [followUpQuery, current, isFollowingUp, startFollowUpStream]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleFollowUp();
    }
  };

  // ── Guards ───────────────────────────────────────────────────────────────
  const isInitializing = !isAuthInitialized || (isLoadingFromDB && !current);

  if (isInitializing) {
    return (
      <AppShell title="Loading…">
        <div className="flex items-center gap-3 p-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading session…
        </div>
      </AppShell>
    );
  }

  if (notFound) {
    return (
      <AppShell title="Not found">
        <div className="p-6 space-y-3">
          <p className="text-sm text-muted-foreground">
            Session not found or you don't have access to it.
          </p>
          <Button variant="outline" size="sm" onClick={() => navigate({ to: "/dashboard" })}>
            Back to Dashboard
          </Button>
        </div>
      </AppShell>
    );
  }

  if (!current) {
    return (
      <AppShell title="Loading…">
        <div className="flex items-center gap-3 p-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading session…
        </div>
      </AppShell>
    );
  }

  const streaming = current.status === "running" || !!followUpBackendId;
  // AbortErrors are intentional cancellations (timeout, navigation) — not research failures
  const isAbortError = storeError != null && (
    storeError.includes("AbortError") ||
    storeError.includes("signal is aborted") ||
    storeError.includes("aborted without reason")
  );
  const hasError = (current.status === "error" || !!storeError) && !isAbortError;
  const blocks = current.blocks ?? [];

  // Build export content from all blocks
  const allReportContent = blocks
    .map((b, i) => `# Research #${i + 1}: ${b.query}\n\n${b.report}`)
    .join("\n\n---\n\n");

  return (
    <AppShell title="Research workspace">
      {/* ── Main scrollable area + sticky footer ── */}
      <div className="flex flex-col min-h-[calc(100vh-56px)]">
        <div className="flex-1 mx-auto w-full max-w-[1400px] p-4 lg:p-6 pb-40">

          {/* Error banner */}
          {hasError && (
            <div className="mb-4 flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
              <div className="flex-1 min-w-0">
                <span className="font-medium text-destructive">Research failed — </span>
                <span className="text-muted-foreground break-words">
                  {storeError ?? "An unknown error occurred."}
                </span>
                {storeError?.includes("429") && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Groq daily token limit reached.{" "}
                    <a href="https://console.groq.com/settings/billing" target="_blank"
                      rel="noopener noreferrer" className="underline text-primary-glow">
                      Upgrade at console.groq.com
                    </a>
                  </p>
                )}
              </div>
              <button onClick={() => { resetError(); resetCurrent(); }}
                className="shrink-0 text-xs text-muted-foreground underline hover:text-foreground">
                Retry
              </button>
            </div>
          )}

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
            {/* ── Left: Thread ── */}
            <div className="space-y-4 min-w-0">

              {/* Session header */}
              <GlassCard className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-xs uppercase tracking-wider text-muted-foreground">
                      Research Session
                    </div>
                    <h1 className="mt-0.5 text-base font-semibold leading-snug line-clamp-2">
                      {current.query}
                    </h1>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {blocks.length} research block{blocks.length !== 1 ? "s" : ""}
                      {streaming && (
                        <span className="ml-2 inline-flex items-center gap-1 text-primary-glow">
                          <Loader2 className="h-3 w-3 animate-spin" /> Live
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Button variant="outline" size="sm"
                      onClick={() => { resetError(); resetCurrent(); }}>
                      <RotateCw className="h-3.5 w-3.5 mr-1" /> Re-run
                    </Button>
                    <ExportMenu
                      filename={`aether-${current.id.slice(0, 6)}`}
                      content={allReportContent || `# ${current.query}\n\n(No report yet)`}
                    />
                  </div>
                </div>
              </GlassCard>

              {/* Agent swarm — only show when active */}
              {streaming && (
                <GlassCard className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-sm font-medium">Agent swarm</div>
                    <div className="text-xs text-primary-glow flex items-center gap-1">
                      <Loader2 className="h-3 w-3 animate-spin" /> Live
                    </div>
                  </div>
                  <AgentGraph agents={current.agents} />
                </GlassCard>
              )}

              {/* ── Research blocks — each is independent ── */}
              {blocks.length === 0 ? (
                <div className="flex items-center gap-3 rounded-xl border border-border/40 p-6 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  Starting research…
                </div>
              ) : (
                blocks.map((block, i) => (
                  <ResearchBlockCard
                    key={block.id}
                    block={block}
                    isLatest={i === blocks.length - 1}
                  />
                ))
              )}

              {/* Scroll anchor for auto-scroll to newest block */}
              <div ref={bottomRef} />
            </div>

            {/* ── Right panel (only when not streaming) ── */}
            {!streaming && blocks.length > 0 && (
              <aside className="space-y-4 hidden lg:block">
                <GlassCard className="p-4 space-y-2">
                  <div className="text-sm font-medium">Session summary</div>
                  <div className="text-xs text-muted-foreground">
                    <div className="flex justify-between py-1 border-b border-border/30">
                      <span>Blocks</span>
                      <span className="font-medium text-foreground">{blocks.length}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-border/30">
                      <span>Total findings</span>
                      <span className="font-medium text-foreground">
                        {blocks.reduce((a, b) => a + b.findings.length, 0)}
                      </span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-border/30">
                      <span>Total citations</span>
                      <span className="font-medium text-foreground">
                        {blocks.reduce((a, b) => a + b.citations.length, 0)}
                      </span>
                    </div>
                    <div className="flex justify-between py-1">
                      <span>Avg confidence</span>
                      <span className="font-medium text-foreground">
                        {blocks.length > 0
                          ? Math.round(
                              (blocks.reduce((a, b) => a + b.confidence, 0) / blocks.length) * 100,
                            ) + "%"
                          : "—"}
                      </span>
                    </div>
                  </div>
                </GlassCard>

                <GlassCard className="p-4">
                  <div className="text-sm font-medium mb-2">Research thread</div>
                  <div className="space-y-1">
                    {blocks.map((b) => (
                      <button
                        key={b.id}
                        onClick={() =>
                          document
                            .getElementById(`block-${b.id}`)
                            ?.scrollIntoView({ behavior: "smooth" })
                        }
                        className="w-full text-left rounded px-2 py-1.5 text-xs text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground transition-colors flex items-center gap-2"
                      >
                        <span className="shrink-0 h-4 w-4 rounded-full border border-primary/40 bg-primary/10 text-[9px] font-bold text-primary-glow flex items-center justify-center">
                          {b.blockIndex}
                        </span>
                        <span className="line-clamp-1">{b.query}</span>
                      </button>
                    ))}
                  </div>
                </GlassCard>
              </aside>
            )}
          </div>
        </div>

        {/* ── STICKY FOLLOW-UP INPUT ── */}
        <div className="sticky bottom-0 z-40 border-t border-border/60 bg-background/80 backdrop-blur-md">
          <div className="mx-auto max-w-[1400px] px-4 py-3 lg:px-6">

            {!user ? (
              /* Guest — sign in prompt */
              <div className="flex items-center justify-between gap-4 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <LogIn className="h-4 w-4 text-primary-glow shrink-0" />
                  Sign in to continue this research conversation
                </div>
                <Button asChild size="sm" variant="outline">
                  <Link to="/login">Sign in</Link>
                </Button>
              </div>
            ) : streaming ? (
              /* Research running */
              <div className="flex items-center gap-3 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                <span className="text-muted-foreground">
                  {followUpBackendId ? "Processing follow-up research…" : "Research in progress…"}
                </span>
              </div>
            ) : rateLimit.isLimited ? (
              /* Rate limited — live countdown from backend */
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2 text-sm">
                    <Clock className="h-4 w-4 text-amber-400 shrink-0" />
                    <span className="text-amber-300">{rateLimit.message}</span>
                  </div>
                  <span className="text-xs text-muted-foreground shrink-0">
                    {rateLimit.countdown}
                  </span>
                </div>
              </div>
            ) : (
              /* Ready for follow-up */
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <MessageSquarePlus className="h-4 w-4 text-primary-glow" />
                  <span className="text-sm font-medium text-foreground">Continue Research</span>
                  <span className="text-xs text-muted-foreground">
                    · Ask follow-up questions while preserving context
                  </span>
                </div>
                <div className={cn(
                  "flex items-end gap-2 rounded-xl border bg-card/60 px-4 py-3 transition-all duration-200",
                  inputFocused
                    ? "border-primary/60 shadow-[0_0_16px_rgba(139,92,246,0.2)]"
                    : "border-border hover:border-primary/30",
                )}>
                  <textarea
                    ref={inputRef}
                    value={followUpQuery}
                    onChange={(e) => setFollowUpQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onFocus={() => setInputFocused(true)}
                    onBlur={() => setInputFocused(false)}
                    placeholder="Ask a follow-up question… (Enter to send, Shift+Enter for new line)"
                    rows={1}
                    className={cn(
                      "flex-1 resize-none bg-transparent text-sm text-foreground",
                      "placeholder:text-muted-foreground/70 placeholder:text-sm",
                      "outline-none min-h-[36px] max-h-[120px]",
                      "leading-6 py-0.5",
                    )}
                    style={{ height: "auto" }}
                    onInput={(e) => {
                      const el = e.currentTarget;
                      el.style.height = "auto";
                      el.style.height = Math.min(el.scrollHeight, 120) + "px";
                    }}
                    disabled={isFollowingUp || rateLimit.isLimited}
                  />
                  <Button
                    onClick={handleFollowUp}
                    disabled={!followUpQuery.trim() || isFollowingUp || rateLimit.isLimited}
                    size="sm"
                    className={cn(
                      "shrink-0 h-9 w-9 rounded-lg p-0",
                      "bg-gradient-to-r from-primary to-primary-glow",
                      "shadow-[0_0_12px_rgba(139,92,246,0.3)]",
                      "disabled:opacity-40 disabled:shadow-none",
                    )}
                  >
                    {isFollowingUp
                      ? <Loader2 className="h-4 w-4 animate-spin" />
                      : <Send className="h-4 w-4" />}
                  </Button>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground px-1">
                  <Sparkles className="h-3 w-3 text-primary-glow" />
                  Each follow-up creates a new research block — previous research is preserved
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
