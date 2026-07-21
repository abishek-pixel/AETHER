/**
 * Aether API Client — production-ready, auth-aware, no mock fallbacks for
 * authenticated routes.
 */
import type {
  ResearchRequest,
  ResearchResponse,
  SessionStatus,
  SessionListResponse,
  FeedbackRequest,
  FeedbackResponse,
  ExportRequest,
  HealthResponse,
  StreamHandlers,
  StartStreamOptions,
  AnyStreamEvent,
} from "@/types/api";
import { runMockResearch } from "./mockStream";

// ── Configuration ──────────────────────────────────────────────────────────

export const API_BASE_URL: string = (() => {
  // 1. Runtime injection (e.g. Cloudflare Workers / SSR)
  if (typeof window !== "undefined" && (window as any).__ENV__?.VITE_API_BASE_URL) {
    return (window as any).__ENV__.VITE_API_BASE_URL as string;
  }
  // 2. Vite build-time env var (set VITE_API_BASE_URL on Vercel)
  if (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_API_BASE_URL) {
    return (import.meta as any).env.VITE_API_BASE_URL as string;
  }
  // 3. Runtime override stored by the Settings page
  if (typeof window !== "undefined") {
    const stored = localStorage.getItem("aether.apiBaseUrl");
    if (stored && stored !== "http://localhost:8000") return stored;
  }
  // 4. Local development default — never used in a Vercel/Render deployment
  //    because VITE_API_BASE_URL will always be set there.
  return "http://localhost:8000";
})();

const TIMEOUT = 30_000;

// ── Model translation ──────────────────────────────────────────────────────

const MODEL_MAP: Record<string, string> = {
  // Legacy tiers kept for backward compat
  "groq-fast":       "llama-3.1-8b-instant",
  "groq-balanced":   "llama-3.3-70b-versatile",
  "groq-deep":       "llama-3.3-70b-versatile",
  // New models (Issue 5)
  "groq-compound":   "groq/compound",          // GPT OSS 120B class
  "groq-qwen":       "qwen/qwen3.6-27b",       // Qwen 3.6 27B
};
export function resolveModelId(model: string): string {
  return MODEL_MAP[model] ?? model;
}

// ── Error class ────────────────────────────────────────────────────────────

export class APIError extends Error {
  constructor(public status: number, public detail: any, message = "API Error") {
    super(message);
    this.name = "APIError";
  }
}

// ── Auth header helper ─────────────────────────────────────────────────────
// Read directly from localStorage — avoids circular imports and works
// at any point in the module lifecycle including before React mounts.
const TOKEN_KEY = "aether.access_token";

function authHeaders(): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Read the raw access token (used for EventSource query param). */
export function getAccessToken(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
}

// ── Core fetch with timeout ────────────────────────────────────────────────

async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT);
  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
        ...((options.headers as Record<string, string>) ?? {}),
      },
    });
  } finally {
    clearTimeout(timer);
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new APIError(res.status, detail, detail?.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Health ─────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<HealthResponse> {
  const res = await apiFetch(`${API_BASE_URL}/health`);
  return handleResponse(res);
}

export async function isBackendAvailable(): Promise<boolean> {
  try {
    const h = await checkHealth();
    return h.status === "healthy";
  } catch {
    return false;
  }
}

// ── Research ───────────────────────────────────────────────────────────────

export async function startResearch(request: ResearchRequest): Promise<ResearchResponse> {
  const res = await apiFetch(`${API_BASE_URL}/api/v1/research`, {
    method: "POST",
    body: JSON.stringify({
      query: request.query,
      depth: request.depth,
      model: resolveModelId(request.model),
      max_iterations: request.max_iterations ?? 2,
      verify_results: request.verify_results !== false,
      include_citations: request.include_citations !== false,
    }),
  });
  return handleResponse(res);
}

export async function getResearchStatus(sessionId: string): Promise<SessionStatus> {
  const res = await apiFetch(`${API_BASE_URL}/api/v1/research/${sessionId}/status`);
  return handleResponse(res);
}

export function startResearchStream(
  opts: StartStreamOptions,
  handlers: StreamHandlers,
): { abort: () => void; mode: "sse" | "mock" } {
  const controller = new AbortController();

  if (!opts.forceMock && opts.sessionId) {
    const rawToken = getAccessToken();
    const url = new URL(
      `/api/v1/research/${encodeURIComponent(opts.sessionId)}/stream`,
      API_BASE_URL,
    );
    if (rawToken) url.searchParams.set("token", rawToken);

    const es = new EventSource(url.toString());
    let connected = false;

    es.onopen = () => { connected = true; };

    es.onmessage = (msg) => {
      connected = true;
      try {
        const event = JSON.parse(msg.data) as AnyStreamEvent;
        handlers.onEvent(event);
        if (event.type === "done" || event.type === "error") {
          es.close();
          handlers.onClose?.();
        }
      } catch (e) {
        handlers.onError?.(e as Error);
      }
    };

    es.addEventListener("done", () => { es.close(); handlers.onClose?.(); });

    es.onerror = () => {
      es.close();
      if (!connected) {
        // Only fall back to mock if backend is unreachable entirely
        doMock();
      } else {
        handlers.onClose?.();
      }
    };

    controller.signal.addEventListener("abort", () => es.close());
    return { abort: () => controller.abort(), mode: "sse" };
  }

  doMock();
  return { abort: () => controller.abort(), mode: "mock" };

  function doMock() {
    if (opts.forceMock) {
      runMockResearch(
        { query: opts.query, depth: opts.depth, signal: controller.signal },
        handlers.onEvent,
      )
        .catch((err) => { if (err.message !== "aborted") handlers.onError?.(err); })
        .finally(() => handlers.onClose?.());
    }
  }
}

export async function exportResearch(sessionId: string, req: ExportRequest): Promise<Blob> {
  const res = await apiFetch(`${API_BASE_URL}/api/v1/research/${sessionId}/export`, {
    method: "POST",
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new APIError(res.status, {}, "Export failed");
  return res.blob();
}

// ── Sessions (authenticated) ───────────────────────────────────────────────

export async function listSessions(limit = 50, offset = 0, q?: string): Promise<SessionListResponse> {
  const url = new URL(`${API_BASE_URL}/api/v1/sessions`);
  url.searchParams.set("limit", String(limit));
  url.searchParams.set("offset", String(offset));
  if (q) url.searchParams.set("q", q);
  const res = await apiFetch(url.toString());
  return handleResponse(res);
}

export async function getSession(sessionId: string): Promise<any> {
  const res = await apiFetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}`);
  return handleResponse(res);
}

export async function startFollowUp(
  dbSessionId: string,
  query: string,
  depth = "balanced",
  model = "groq-compound",
): Promise<ResearchResponse> {
  const res = await apiFetch(`${API_BASE_URL}/api/v1/sessions/${dbSessionId}/followup`, {
    method: "POST",
    body: JSON.stringify({ query, depth, model: resolveModelId(model), max_iterations: 2 }),
  });
  return handleResponse(res);
}

export async function renameSession(sessionId: string, title: string): Promise<any> {
  const res = await apiFetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}/rename`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
  return handleResponse(res);
}

export async function deleteSession(sessionId: string): Promise<void> {
  await apiFetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}`, { method: "DELETE" });
}

export async function saveFeedback(sessionId: string, feedback: FeedbackRequest): Promise<FeedbackResponse> {
  const res = await apiFetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}/feedback`, {
    method: "POST",
    body: JSON.stringify(feedback),
  });
  return handleResponse(res);
}

// ── Users / Usage ──────────────────────────────────────────────────────────

export async function getUserUsage(): Promise<{
  total_tokens: number;
  total_cost: number;
  total_sessions: number;
  total_requests: number;
  credits_remaining: number;
  current_plan: string;
}> {
  const res = await apiFetch(`${API_BASE_URL}/api/v1/users/me/usage`);
  return handleResponse(res);
}

export async function getSubscription(): Promise<{
  current_plan: string;
  credits_remaining: number;
  renewal_date: string | null;
}> {
  const res = await apiFetch(`${API_BASE_URL}/api/v1/users/me/subscription`);
  return handleResponse(res);
}

// ── Rate-limit ─────────────────────────────────────────────────────────────

export async function getRateLimit(): Promise<{
  prompts_used: number;
  prompts_allowed: number;
  remaining: number;
  reset_at: string | null;
  retry_after_seconds: number;
  hours_remaining: number;
  is_limited: boolean;
}> {
  const res = await apiFetch(`${API_BASE_URL}/api/v1/users/me/rate-limit`);
  return handleResponse(res);
}

// ── Analytics ──────────────────────────────────────────────────────────────

export async function getAnalytics(): Promise<any> {
  const res = await apiFetch(`${API_BASE_URL}/api/v1/analytics`);
  return handleResponse(res);
}

// ── Helpers ────────────────────────────────────────────────────────────────

export function downloadFile(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}

export async function downloadResearchReport(sessionId: string, filename = `research_${sessionId}.md`): Promise<void> {
  const blob = await exportResearch(sessionId, { format: "markdown", include_citations: true, include_reasoning: true });
  downloadFile(blob, filename);
}
