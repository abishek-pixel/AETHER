import { useEffect, useRef, useCallback, useState } from "react";
import { startResearch, startResearchStream, getResearchStatus } from "@/lib/api";
import type {
  ResearchRequest,
  ResearchResponse,
  SessionStatus,
  ResearchDepth,
  AnyStreamEvent,
} from "@/types/api";

export interface UseResearchOptions {
  autoStart?: boolean;
  onStatusChange?: (status: SessionStatus) => void;
  onError?: (error: Error) => void;
  pollInterval?: number; // ms between status checks
}

export interface UseResearchReturn {
  sessionId: string | null;
  status: SessionStatus | null;
  result: ResearchResponse | null;
  events: AnyStreamEvent[];
  isLoading: boolean;
  error: Error | null;
  start: (query: string, depth: ResearchDepth, model: string) => Promise<string>;
  abort: () => void;
  retry: () => Promise<void>;
}

/**
 * React hook for managing research sessions
 * Handles starting research, streaming updates, and status polling
 */
export function useResearch(options: UseResearchOptions = {}): UseResearchReturn {
  const {
    autoStart = false,
    onStatusChange,
    onError,
    pollInterval = 2000,
  } = options;

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [result, setResult] = useState<ResearchResponse | null>(null);
  const [events, setEvents] = useState<AnyStreamEvent[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const streamControllerRef = useRef<{ abort: () => void } | null>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const lastRequestRef = useRef<ResearchRequest | null>(null);

  // Cleanup function
  const cleanup = useCallback(() => {
    if (streamControllerRef.current) {
      streamControllerRef.current.abort();
      streamControllerRef.current = null;
    }
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  // Start research
  const start = useCallback(
    async (query: string, depth: ResearchDepth, model: string): Promise<string> => {
      try {
        cleanup();
        setIsLoading(true);
        setError(null);
        setEvents([]);
        setResult(null);

        const request: ResearchRequest = { query, depth, model };
        lastRequestRef.current = request;

        // Start research
        const response = await startResearch(request);
        setSessionId(response.session_id);

        // Start streaming events
        const streamHandler = startResearchStream(
          { sessionId: response.session_id, query, depth, model },
          {
            onEvent: (event) => {
              setEvents((prev) => [...prev, event]);

              // Extract status updates
              if (event.type === "done") {
                setStatus({
                  session_id: response.session_id,
                  status: "completed",
                  query,
                  depth,
                  model,
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                  progress: 100,
                  agents_status: {},
                  current_agent: null,
                });
                setResult(response);
              }
            },
            onError: (err) => {
              setError(err);
              onError?.(err);
            },
            onClose: () => {
              // Stream closed
            },
          }
        );

        streamControllerRef.current = streamHandler;

        // Start polling for status updates
        if (response.session_id) {
          pollIntervalRef.current = setInterval(async () => {
            try {
              const sessionStatus = await getResearchStatus(response.session_id);
              setStatus(sessionStatus);
              onStatusChange?.(sessionStatus);
            } catch (err) {
              console.error("Status poll error:", err);
            }
          }, pollInterval);
        }

        return response.session_id;
      } catch (err) {
        const apiError = err instanceof Error ? err : new Error(String(err));
        setError(apiError);
        onError?.(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [cleanup, pollInterval, onStatusChange, onError]
  );

  // Retry function
  const retry = useCallback(async () => {
    if (lastRequestRef.current) {
      const { query, depth, model } = lastRequestRef.current;
      await start(query, depth, model);
    }
  }, [start]);

  // Cleanup on unmount
  useEffect(() => {
    return cleanup;
  }, [cleanup]);

  return {
    sessionId,
    status,
    result,
    events,
    isLoading,
    error,
    start,
    abort: cleanup,
    retry,
  };
}
