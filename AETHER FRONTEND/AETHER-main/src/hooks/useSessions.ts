import { useEffect, useState, useCallback } from "react";
import { listSessions, getSession, saveFeedback } from "@/lib/api";
import type { SessionSummary, FeedbackRequest, FeedbackResponse } from "@/types/api";

export interface UseSessionsOptions {
  limit?: number;
  offset?: number;
  autoFetch?: boolean;
  refetchInterval?: number; // ms between auto-refetches
}

export interface UseSessionsReturn {
  sessions: SessionSummary[];
  total: number;
  limit: number;
  offset: number;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  getSessionDetail: (id: string) => Promise<SessionSummary | null>;
  submitFeedback: (
    sessionId: string,
    feedback: FeedbackRequest
  ) => Promise<FeedbackResponse | null>;
  nextPage: () => Promise<void>;
  previousPage: () => Promise<void>;
}

/**
 * React hook for managing research sessions
 * Handles fetching, pagination, and operations on sessions
 */
export function useSessions(
  options: UseSessionsOptions = {}
): UseSessionsReturn {
  const { limit = 50, offset: initialOffset = 0, autoFetch = true, refetchInterval = 0 } =
    options;

  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(initialOffset);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchSessions = useCallback(async (pageOffset = offset) => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await listSessions(limit, pageOffset);
      setSessions(response.sessions);
      setTotal(response.total);
      setOffset(pageOffset);
    } catch (err) {
      const apiError = err instanceof Error ? err : new Error(String(err));
      console.error("Failed to fetch sessions:", apiError);
      setError(apiError);
    } finally {
      setIsLoading(false);
    }
  }, [limit, offset]);

  // Auto-fetch on mount and auto-refetch interval
  useEffect(() => {
    if (autoFetch) {
      fetchSessions(initialOffset);
    }
  }, [autoFetch, initialOffset, fetchSessions]);

  // Setup auto-refetch interval
  useEffect(() => {
    if (!refetchInterval || refetchInterval <= 0) return;

    const interval = setInterval(() => {
      fetchSessions(offset);
    }, refetchInterval);

    return () => clearInterval(interval);
  }, [refetchInterval, offset, fetchSessions]);

  const getSessionDetail = useCallback(
    async (id: string): Promise<SessionSummary | null> => {
      try {
        const session = await getSession(id);
        return session;
      } catch (err) {
        console.error(`Failed to fetch session ${id}:`, err);
        return null;
      }
    },
    []
  );

  const submitFeedback = useCallback(
    async (
      sessionId: string,
      feedback: FeedbackRequest
    ): Promise<FeedbackResponse | null> => {
      try {
        const response = await saveFeedback(sessionId, feedback);
        return response;
      } catch (err) {
        console.error("Failed to submit feedback:", err);
        return null;
      }
    },
    []
  );

  const nextPage = useCallback(async () => {
    const newOffset = offset + limit;
    if (newOffset < total) {
      await fetchSessions(newOffset);
    }
  }, [offset, limit, total, fetchSessions]);

  const previousPage = useCallback(async () => {
    const newOffset = Math.max(0, offset - limit);
    await fetchSessions(newOffset);
  }, [offset, limit, fetchSessions]);

  return {
    sessions,
    total,
    limit,
    offset,
    isLoading,
    error,
    refetch: () => fetchSessions(offset),
    getSessionDetail,
    submitFeedback,
    nextPage,
    previousPage,
  };
}
