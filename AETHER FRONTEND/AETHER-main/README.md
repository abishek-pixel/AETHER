# Aether — Frontend

a multi-agent system where different specialized agents (Researcher, Critic, Verifier, Writer, Fact-Checker) collaborate to solve complex research problems with minimal hallucination. Include self-reflection loops, debate mechanisms, and tool-use (web search, code execution, paper analysis).

## Run

```bash
bun install
bun run dev
```

By default the app talks to a FastAPI backend at `http://localhost:8000`.
Set a different backend with:

```bash
VITE_API_BASE_URL=https://your-backend.example.com bun run dev
```

You can also change it at runtime in **Settings → Backend**.

## Backend contract

The frontend expects a FastAPI backend with these endpoints:

| Method | Path | Notes |
| ------ | ---- | ----- |
| `GET`  | `/research/stream?query=…&depth=…&model=…` | **SSE stream** of `StreamEvent` JSON messages |
| `GET`  | `/sessions` | List sessions (optional, currently uses local store) |
| `POST` | `/sessions` | Create session (optional) |
| `GET`  | `/sessions/:id` | Fetch one session (optional) |

### `StreamEvent` shape (TypeScript / Pydantic mirror)

See `src/types/index.ts`. Each SSE message is JSON-encoded:

```jsonc
{ "type": "agent_update", "agent": { "id": "researcher", "role": "researcher", "name": "Researcher", "status": "searching", "progress": 40 } }
{ "type": "decompose", "subqueries": ["...", "..."] }
{ "type": "timeline",  "event": { "id": "...", "ts": 1736..., "agentRole": "researcher", "type": "search", "text": "..." } }
{ "type": "finding",   "finding": { "id": "...", "agentRole": "researcher", "title": "...", "summary": "...", "citationIds": ["..."], "confidence": 0.82, "relevance": 0.91, "createdAt": 1736... } }
{ "type": "citation",  "citation": { "id": "...", "title": "...", "url": "...", "source": "Nature", "snippet": "...", "verification": "verified", "confidence": 0.9 } }
{ "type": "report_chunk", "text": "..." }
{ "type": "reasoning", "text": "..." }
{ "type": "tokens", "total": 8420 }
{ "type": "done", "confidence": 0.89 }
{ "type": "error", "message": "..." }
```

### Demo / fallback mode

If the backend is unreachable the UI **automatically falls back to a built-in
mock streamer** that emits the same event sequence on a timer — so every
button, animation and route works end-to-end with no backend running.

## Project structure (mapped to your spec)

| Requested | Actual (TanStack Start) |
| --------- | ----------------------- |
| `app/page.tsx` | `src/routes/index.tsx` |
| `app/(auth)/login` | `src/routes/login.tsx`, `src/routes/signup.tsx` |
| `app/dashboard` | `src/routes/dashboard.tsx` |
| `app/research/[sessionId]` | `src/routes/research.$sessionId.tsx` |
| `app/layout.tsx` | `src/routes/__root.tsx` |
| `lib/api.ts` | `src/lib/api.ts` (SSE + mock) |
| `lib/utils.ts` | `src/lib/utils.ts` |
| `types/index.ts` | `src/types/index.ts` |
| `components/ui/*` | `src/components/ui/*` |
| `components/{layout,research,agents,visualization,common}` | same paths under `src/components/` |
| `hooks/*` | `src/hooks/*` |

## Routes

- `/` — Landing (hero, animated agent flow, demo input, examples, CTAs)
- `/login`, `/signup` — Auth (UI only in this demo)
- `/dashboard` — Sidebar + new-research bar + recent session cards
- `/research/$sessionId` — Live agent graph, timeline, findings, report, citations, confidence, reasoning, export
- `/analytics` — Recharts dashboard
- `/settings` — Backend URL + default model

`Cmd/Ctrl + K` opens the command palette anywhere.

## Tech

- TanStack Start v1 (React 19, Vite 7) — file-based routing under `src/routes/`
- Tailwind v4 (semantic tokens in `src/styles.css`, dark-first)
- shadcn/ui components
- Framer Motion (agent animations, page transitions)
- Zustand (`src/store/research.ts`, `src/store/ui.ts`)
- TanStack Query (provider wired in `__root.tsx`)
- Axios available; the streaming layer uses native `EventSource`
- Recharts (analytics)
