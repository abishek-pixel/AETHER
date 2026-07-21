## Aether — AI Research Workspace

A premium dark-themed multi-agent research platform with live agent visualization, simulated streaming, and a full workspace UI.

### Stack mapping (important)

This Lovable template is **TanStack Start + React 19 + Vite** — Next.js App Router is not supported here. I'll map your structure 1:1:

- `app/page.tsx` → `src/routes/index.tsx` (Landing)
- `app/(auth)/login` → `src/routes/login.tsx`, `src/routes/signup.tsx`
- `app/dashboard` → `src/routes/dashboard.tsx`
- `app/research/[sessionId]` → `src/routes/research.$sessionId.tsx`
- `lib/`, `components/`, `hooks/`, `types/` → same names under `src/`

All requested libraries are supported: Tailwind v4, shadcn/ui, Framer Motion, Zustand, TanStack Query, Axios, Recharts.

### Routes & navigation

```text
/                       Landing (hero, agent flow viz, demo input, CTAs)
/login, /signup         Auth screens (UI only, no backend wired)
/dashboard              Sidebar + sessions list + analytics summary
/research/$sessionId    Live workspace (agent graph, timeline, report)
/analytics              Recharts dashboard
/settings               Preferences, model selector, API base URL
```

Every CTA, sidebar item, and button routes correctly via TanStack `<Link>`.

### Pages — what you get

**Landing (`/`)**
- Gradient hero, headline "Research Smarter with Multi-Agent AI"
- Animated agent pipeline (Supervisor → Researcher → Critic → Verifier → Writer) with Framer Motion glow/pulse
- Interactive demo input that simulates a research run inline
- Example query chips (Simple / Deep / Comparison)
- CTAs: "Start Free Research" → `/dashboard`, "Watch 90s Demo" → modal

**Dashboard (`/dashboard`)**
- Left sidebar: New Research, Sessions, Saved Reports, Team Workspace, Analytics, Settings
- Recent sessions grid with status, depth, confidence
- Quick-start search bar → creates session and routes to `/research/$id`

**Research Workspace (`/research/$sessionId`)** — the centerpiece
- Premium search bar + depth slider (Fast / Balanced / Deep) + model selector
- **Multi-agent live graph**: SVG nodes with glowing rings, status labels ("Searching…", "Debating…", "Verifying…"), animated edges that light up during debate cycles
- Research timeline (chronological agent steps, typing animation)
- Findings cards: source, confidence badge, relevance, expandable citation preview
- Right panel: citations list, confidence meter, token usage, export buttons (PDF/DOCX/MD)
- Reasoning View toggle (agent inner thoughts)
- Final formatted report with skeleton → streamed reveal

**Analytics (`/analytics`)**
- Recharts: sessions over time (area), token usage (bar), top topics (pie), time saved (stat cards)

**Settings (`/settings`)**
- Theme (dark default), model preference, API base URL field, export defaults

### Real-time streaming

`lib/api.ts` exposes:
- Axios instance with `VITE_API_BASE_URL` (defaults `http://localhost:8000`)
- `streamResearch(query, opts, handlers)` using **native `EventSource`** for SSE with typed event handlers (`onDecompose`, `onAgentUpdate`, `onFinding`, `onCitation`, `onReportChunk`, `onDone`, `onError`)
- A **mock streamer** fallback that emits the same event sequence on a timer so the UI is fully demo-able without the backend

### State & data

- **Zustand**: `useResearchStore` (current session, agents, findings, citations, report buffer, status), `useUIStore` (sidebar, command palette, reasoning view)
- **TanStack Query**: sessions list, analytics, saved reports
- **Types** (`src/types/index.ts`): `AgentRole`, `AgentStatus`, `Agent`, `Finding`, `Citation`, `ResearchSession`, `ResearchDepth`, `ModelTier`, SSE event union — mirrors typical FastAPI Pydantic shape

### Premium UX

- **Cmd+K command palette** (shadcn `command`) — navigate, start research, switch model
- Glassmorphism cards (`bg-card/60 backdrop-blur` + soft border + glow shadow)
- Framer Motion page transitions, agent pulse, finding card stagger
- Skeleton loaders + typing animation for streamed report
- Toast notifications via Sonner

### Design system (`src/styles.css`)

Dark-first palette with one accent + glow:
- `--background` near-black with subtle blue tint
- `--primary` electric indigo with `--primary-glow` for halos
- `--accent` cyan for "verified" badges; `--destructive` for conflicts
- Custom tokens: `--gradient-hero`, `--gradient-agent`, `--shadow-glow`, `--shadow-elevated`
- Inter font, generous radii, semantic confidence colors (`--confidence-high/med/low`)
- Button variants: `hero` (gradient + glow), `glass`, `ghost-glow`

### File plan (high-level)

```text
src/
  routes/
    __root.tsx               (providers: QueryClient, Sonner, CommandPalette)
    index.tsx                (Landing)
    login.tsx, signup.tsx
    dashboard.tsx
    research.$sessionId.tsx
    analytics.tsx
    settings.tsx
  components/
    layout/{AppShell,Sidebar,Topbar}.tsx
    landing/{Hero,AgentFlowAnimation,DemoInput,ExampleQueries,CTASection}.tsx
    research/{SearchBar,DepthSlider,ModelSelector,Timeline,FindingCard,
              CitationsPanel,ConfidenceMeter,ReportView,ReasoningView,ExportMenu}.tsx
    agents/{AgentGraph,AgentNode,AgentEdge,StatusBadge}.tsx
    visualization/{MemoryGraph,AnalyticsCharts}.tsx
    common/{CommandPalette,GlassCard,GradientText,Logo}.tsx
  lib/{api.ts, sse.ts, mockStream.ts, utils.ts}
  hooks/{useResearchStream.ts, useCommandPalette.ts, useHotkeys.ts}
  store/{research.ts, ui.ts}
  types/index.ts
  styles.css
README.md
```

### Backend connectivity

- `VITE_API_BASE_URL` env var (documented in README), default `http://localhost:8000`
- SSE endpoint assumed: `GET /research/stream?query=...&depth=...&model=...`
- Sessions REST: `GET/POST /sessions`, `GET /sessions/:id`, `GET /analytics`
- If backend is unreachable, UI auto-falls back to mock streamer (clearly labeled "Demo mode") so every button works end-to-end
- Typed error states + toasts + retry

### Scope note

This is a large build. I'll ship it in one pass focused on a polished, fully-navigable product: every route exists, every button routes or triggers an action, the agent visualization and simulated streaming work out of the box. Auth screens are UI-only (no real auth wired) unless you want me to enable Lovable Cloud for real accounts/persistence later.
