import { useEffect, useRef, useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useResearchStore } from "@/store/research";
import { startResearch, startResearchStream } from "@/lib/api";
import type { ResearchSession, StreamEvent } from "@/types";
import type { AnyStreamEvent } from "@/types/api";

function toStoreEvent(event: AnyStreamEvent): StreamEvent {
  return event as unknown as StreamEvent;
}

/**
 * Hook that manages the research stream lifecycle.
 *
 * Flow:
 *  1. Session is created with status="idle" (local UUID) by SearchBar.
 *  2. This hook detects status="idle", sets it to "running".
 *  3. Calls POST /api/v1/research → backend creates a DB session with its own UUID.
 *  4. Opens SSE stream.
 *  5. On "done" event: promotes the local UUID to the DB UUID in the store,
 *     then navigates the URL from /research/{localUUID} to /research/{dbUUID}
 *     so the address bar is persistent and survives page refresh.
 */
export function useResearchStream(session: ResearchSession | null, autoStart = true) {
  const applyEvent = useResearchStore((s) => s.applyEvent);
  const promoteSessionId = useResearchStore((s) => s.promoteSessionId);
  const setStatus = useResearchStore((s) => s.setStatus);
  const navigate = useNavigate();
  const abortControllerRef = useRef<{ abort: () => void } | null>(null);
  const ranForRef = useRef<string | null>(null);

  const cleanup = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!session || !autoStart) return;

    const hasNoStreamedOutput =
      session.agents.every((a) => a.status === "idle") &&
      session.findings.length === 0 &&
      session.citations.length === 0 &&
      session.report.length === 0;

    const isStaleRunningSession =
      session.status === "running" &&
      hasNoStreamedOutput &&
      Date.now() - session.updatedAt > 3000;

    if (session.status !== "idle" && !isStaleRunningSession) return;
    if (ranForRef.current === session.id) return;

    ranForRef.current = session.id;
    const localId = session.id;   // capture before async work
    setStatus("running");

    const isCurrentSession = () =>
      useResearchStore.getState().current?.id === localId ||
      // also match after promotion (db id may differ)
      useResearchStore.getState().current !== null;

    startResearch({
      query: session.query,
      depth: session.depth,
      model: session.model,
    })
      .then((response) => {
        if (!isCurrentSession()) return;

        const streamController = startResearchStream(
          {
            sessionId: response.session_id,
            query: session.query,
            depth: session.depth,
            model: session.model,
            forceMock: false,
          },
          {
            onEvent: (event) => {
              const ev = event as any;

              if (ev.type === "error") {
                applyEvent(toStoreEvent(event));
                console.error("Backend research error:", ev.message);
                return;
              }

              applyEvent(toStoreEvent(event));

              // ── Key fix: on "done", replace local UUID with DB UUID in URL ──
              if (ev.type === "done" && ev.db_session_id && ev.db_session_id !== localId) {
                const dbId: string = ev.db_session_id;
                // Promote the ID in the store first
                promoteSessionId(localId, dbId);
                // Navigate after store update is flushed to React
                // Use requestAnimationFrame so the current render (with the
                // promoted session content) paints BEFORE the route changes,
                // preventing the 1-frame blank screen.
                requestAnimationFrame(() => {
                  navigate({
                    to: "/research/$sessionId",
                    params: { sessionId: dbId },
                    replace: true,
                  });
                });
              }
            },
            onError: (error) => {
              console.error("SSE connection error:", error);
            },
            onClose: () => {
              abortControllerRef.current = null;
              ranForRef.current = null;
            },
          },
        );

        abortControllerRef.current = streamController;
      })
      .catch((err) => {
        if (!isCurrentSession()) return;
        // Intentional AbortError (request cancelled because component unmounted
        // or 30-second timeout fired) — treat as a transient cancellation,
        // not a research failure.
        if (err instanceof DOMException && err.name === "AbortError") {
          console.warn("Research request aborted (likely timeout or navigation):", err.message);
          ranForRef.current = null;
          return;
        }
        const isNetworkError = err?.name === "TypeError" || err?.message?.includes("fetch");
        if (!isNetworkError) {
          setStatus("error");
          useResearchStore.getState().setError(
            err?.message ?? "Research failed. Please try again.",
          );
          return;
        }
        // Backend completely unreachable — fall back to mock for dev experience
        console.warn("Backend unreachable, falling back to mock stream:", err);
        const streamController = startResearchStream(
          {
            query: session.query,
            depth: session.depth,
            model: session.model,
            forceMock: true,
          },
          {
            onEvent: (event) => applyEvent(toStoreEvent(event)),
            onError: (error) => {
              console.error("Mock stream error:", error);
              setStatus("error");
            },
            onClose: () => {
              abortControllerRef.current = null;
              ranForRef.current = null;
            },
          },
        );
        abortControllerRef.current = streamController;
      });

    return () => {
      const cur = useResearchStore.getState().current;
      if (cur?.id === localId && cur.status === "idle") {
        ranForRef.current = null;
      }
      cleanup();
    };
  }, [session?.id, session?.status, autoStart, setStatus, applyEvent, promoteSessionId, navigate, cleanup]);

  return {
    abort: cleanup,
    isRunning: session?.status === "running",
  };
}
