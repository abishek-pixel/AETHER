/**
 * useRateLimit — shared hook for free-tier rate-limit state.
 *
 * Features per spec (BUG 5 + BUG 6):
 *  - Derives authoritative reset_at from backend (not localStorage).
 *  - Live countdown that ticks every second.
 *  - Persists reset_at in sessionStorage so refresh does NOT reset the timer.
 *  - Automatically re-fetches when the countdown reaches zero → unlocks.
 *  - Reacts to user login/logout.
 *  - `triggerRefetch()` call allows pages to refresh state after a prompt is used.
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { useAuthStore } from "@/store/auth";
import { getRateLimit } from "@/lib/api";

// We store the authoritative reset_at in sessionStorage so it survives
// page refreshes without relying on backend for every render.
const STORAGE_KEY = "aether.rate_limit_reset_at";

function loadStoredResetAt(): string | null {
  try { return sessionStorage.getItem(STORAGE_KEY); } catch { return null; }
}
function saveResetAt(ts: string | null): void {
  try {
    if (ts) sessionStorage.setItem(STORAGE_KEY, ts);
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch { /* ignore */ }
}

function secondsUntil(isoTs: string | null): number {
  if (!isoTs) return 0;
  const diff = (new Date(isoTs).getTime() - Date.now()) / 1000;
  return Math.max(0, Math.ceil(diff));
}

function formatCountdown(seconds: number): string {
  if (seconds <= 0) return "soon";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return m > 0 ? `${h}h ${m}m` : `${h}h`;
  if (m > 0) return s > 0 ? `${m}m ${s}s` : `${m}m`;
  return `${s}s`;
}

export interface RateLimitState {
  /** true while the initial fetch hasn't returned yet */
  isLoading: boolean;
  /** true when limit is active */
  isLimited: boolean;
  /** prompts used in current window */
  promptsUsed: number;
  /** max prompts allowed */
  promptsAllowed: number;
  /** prompts remaining */
  remaining: number;
  /** ISO UTC string of when the window resets */
  resetAt: string | null;
  /** live countdown string e.g. "4h 12m" */
  countdown: string;
  /** raw seconds until reset */
  secondsRemaining: number;
  /** human-readable message matching spec format */
  message: string;
  /** call after submitting a prompt to refresh the state */
  triggerRefetch: () => void;
}

export function useRateLimit(): RateLimitState {
  const user = useAuthStore((s) => s.user);
  const isInitialized = useAuthStore((s) => s.isInitialized);

  const [isLoading, setIsLoading] = useState(true);
  const [isLimited, setIsLimited] = useState(false);
  const [promptsUsed, setPromptsUsed] = useState(0);
  const [promptsAllowed, setPromptsAllowed] = useState(2);
  const [remaining, setRemaining] = useState(2);
  const [resetAt, setResetAt] = useState<string | null>(null);
  const [secondsRemaining, setSecondsRemaining] = useState(0);
  const [refetchTick, setRefetchTick] = useState(0);

  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Fetch from backend ──────────────────────────────────────────────────
  const fetchLimit = useCallback(async () => {
    if (!user) {
      setIsLoading(false);
      setIsLimited(false);
      setResetAt(null);
      saveResetAt(null);
      return;
    }
    try {
      const info = await getRateLimit();
      setPromptsUsed(info.prompts_used);
      setPromptsAllowed(info.prompts_allowed === -1 ? 999 : info.prompts_allowed);
      setRemaining(info.remaining === -1 ? 999 : info.remaining);
      setIsLimited(info.is_limited);

      if (info.is_limited && info.reset_at) {
        setResetAt(info.reset_at);
        saveResetAt(info.reset_at);
        setSecondsRemaining(secondsUntil(info.reset_at));
      } else {
        setResetAt(null);
        saveResetAt(null);
        setSecondsRemaining(0);
      }
    } catch {
      // On error: try to use stored reset_at so the UI doesn't break
      const stored = loadStoredResetAt();
      if (stored && secondsUntil(stored) > 0) {
        setIsLimited(true);
        setResetAt(stored);
        setSecondsRemaining(secondsUntil(stored));
      }
    } finally {
      setIsLoading(false);
    }
  }, [user]);

  // ── Fetch on mount, user change, and manual trigger ─────────────────────
  useEffect(() => {
    if (!isInitialized) return;

    // On mount, seed timer from storage immediately while fetch is in-flight
    const stored = loadStoredResetAt();
    if (stored) {
      const secs = secondsUntil(stored);
      if (secs > 0) {
        setIsLimited(true);
        setResetAt(stored);
        setSecondsRemaining(secs);
        setIsLoading(false); // show banner immediately
      } else {
        // Stored reset_at is in the past — clear it
        saveResetAt(null);
      }
    }

    fetchLimit();
  }, [isInitialized, user, refetchTick, fetchLimit]);

  // ── Live countdown ticker ────────────────────────────────────────────────
  useEffect(() => {
    if (tickRef.current) clearInterval(tickRef.current);
    if (!isLimited || !resetAt) return;

    tickRef.current = setInterval(() => {
      const secs = secondsUntil(resetAt);
      setSecondsRemaining(secs);
      if (secs <= 0) {
        // Time is up — auto-unlock
        setIsLimited(false);
        setResetAt(null);
        saveResetAt(null);
        setRemaining(promptsAllowed);
        clearInterval(tickRef.current!);
        // Re-fetch to confirm from server
        setRefetchTick((n) => n + 1);
      }
    }, 1000);

    return () => { if (tickRef.current) clearInterval(tickRef.current); };
  }, [isLimited, resetAt, promptsAllowed]);

  const triggerRefetch = useCallback(() => {
    setRefetchTick((n) => n + 1);
  }, []);

  const countdown = formatCountdown(secondsRemaining);

  const message = isLimited
    ? `You've reached the free-tier research limit of ${promptsAllowed} prompts. You can continue researching in ${countdown}.`
    : remaining === 1
    ? `1 research prompt remaining in this 6-hour window.`
    : remaining <= promptsAllowed
    ? `${remaining} research prompts remaining in this 6-hour window.`
    : "";

  return {
    isLoading,
    isLimited,
    promptsUsed,
    promptsAllowed,
    remaining,
    resetAt,
    countdown,
    secondsRemaining,
    message,
    triggerRefetch,
  };
}
