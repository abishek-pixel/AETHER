/**
 * SearchBar — main research input.
 *
 * BUG 5 + BUG 6 compliant:
 *  - Authenticated free-tier users: live countdown from server reset_at.
 *  - Countdown survives refresh and logout/login.
 *  - Input disabled while limited.
 *  - Guest users: 1 free session-storage prompt.
 */
import { useState } from "react";
import { Search, Loader2, Lock, Clock } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useNavigate, Link } from "@tanstack/react-router";
import { useResearchStore } from "@/store/research";
import { useAuthStore } from "@/store/auth";
import type { ResearchDepth, ModelTier } from "@/types";
import { DepthSlider } from "./DepthSlider";
import { ModelSelector } from "./ModelSelector";
import { useRateLimit } from "@/hooks/useRateLimit";

// ── Guest free prompt tracking (sessionStorage) ────────────────────────────
const GUEST_PROMPT_KEY = "aether.guest_prompts_used";
const GUEST_FREE_PROMPTS = 1;

function getGuestPromptsUsed(): number {
  try { return parseInt(sessionStorage.getItem(GUEST_PROMPT_KEY) ?? "0", 10); } catch { return 0; }
}
function incrementGuestPrompts(): void {
  try { sessionStorage.setItem(GUEST_PROMPT_KEY, String(getGuestPromptsUsed() + 1)); } catch { /* ignore */ }
}

// ── Component ──────────────────────────────────────────────────────────────

export function SearchBar({ initialQuery = "" }: { initialQuery?: string }) {
  const [q, setQ] = useState(initialQuery);
  const [depth, setDepth] = useState<ResearchDepth>("balanced");
  const [model, setModel] = useState<ModelTier>("groq-compound");
  const [busy, setBusy] = useState(false);

  const createSession = useResearchStore((s) => s.createSession);
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const isInitialized = useAuthStore((s) => s.isInitialized);

  // Live rate-limit state from backend
  const rateLimit = useRateLimit();

  // Guest exhaustion check
  const guestExhausted = isInitialized && !user && getGuestPromptsUsed() >= GUEST_FREE_PROMPTS;

  const isDisabled = busy || guestExhausted || (!!user && rateLimit.isLimited);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!q.trim() || isDisabled) return;

    // Guest limit check
    if (!user) {
      if (getGuestPromptsUsed() >= GUEST_FREE_PROMPTS) {
        navigate({ to: "/login" });
        return;
      }
      incrementGuestPrompts();
    }

    setBusy(true);
    const session = createSession(q.trim(), depth, model);
    navigate({ to: "/research/$sessionId", params: { sessionId: session.id } });
    // Trigger rate-limit refresh after prompt submission
    setTimeout(() => rateLimit.triggerRefetch(), 3000);
    setBusy(false);
  };

  return (
    <form onSubmit={handleSubmit} className="glass rounded-2xl p-3 shadow-elevated">
      <div className="flex items-center gap-2">
        <Search className="ml-2 h-4 w-4 text-muted-foreground shrink-0" />
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={
            guestExhausted
              ? "Sign in to continue researching…"
              : user && rateLimit.isLimited
              ? `Research limit reached — resets in ${rateLimit.countdown}`
              : "Ask Aether to research anything…"
          }
          className="border-0 bg-transparent focus-visible:ring-0 text-base h-11"
          disabled={isDisabled}
        />

        {guestExhausted ? (
          <Button asChild size="sm"
            className="bg-gradient-to-r from-primary to-primary-glow text-primary-foreground shadow-glow shrink-0">
            <Link to="/login">
              <Lock className="h-4 w-4 mr-1" /> Sign in
            </Link>
          </Button>
        ) : user && rateLimit.isLimited ? (
          <Button disabled size="sm" className="shrink-0 opacity-60 cursor-not-allowed">
            <Clock className="h-4 w-4 mr-1" />
            {rateLimit.countdown}
          </Button>
        ) : (
          <Button
            type="submit"
            disabled={isDisabled || !q.trim() || rateLimit.isLoading}
            className="bg-gradient-to-r from-primary to-primary-glow text-primary-foreground shadow-glow shrink-0"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Research"}
          </Button>
        )}
      </div>

      {/* Live rate-limit banner — spec message format */}
      {isInitialized && user && rateLimit.isLimited && (
        <div className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2">
          <div className="flex items-start gap-2 text-xs text-amber-300">
            <Clock className="h-3.5 w-3.5 mt-0.5 shrink-0 text-amber-400" />
            <span>{rateLimit.message}</span>
          </div>
        </div>
      )}

      {/* Remaining prompts hint (not limited yet) */}
      {isInitialized && user && !rateLimit.isLimited && !rateLimit.isLoading
        && rateLimit.remaining <= rateLimit.promptsAllowed && rateLimit.remaining > 0 && (
        <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground px-2">
          <span className={rateLimit.remaining === 1 ? "text-amber-400" : ""}>
            {rateLimit.remaining === 1
              ? "⚠ Last free research in this window"
              : `${rateLimit.remaining} of ${rateLimit.promptsAllowed} free researches remaining`}
          </span>
        </div>
      )}

      {/* Guest free prompt banner */}
      {isInitialized && !user && !guestExhausted && (
        <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground px-2">
          <span>
            1 free research available —{" "}
            <Link to="/login" className="text-primary-glow underline">sign in</Link> for more
          </span>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-border pt-3">
        <DepthSlider value={depth} onChange={setDepth} disabled={isDisabled} />
        <ModelSelector value={model} onChange={setModel} disabled={isDisabled} />
      </div>
    </form>
  );
}
