/**
 * Research store — threaded conversation architecture.
 *
 * Each ResearchSession contains an ordered `blocks` array.
 * Each follow-up creates a NEW ResearchBlock appended to blocks[].
 * Previous blocks are NEVER overwritten or removed.
 */
import { create } from "zustand";
import type {
  Agent, AgentRole, Citation, Finding, ResearchDepth,
  ResearchBlock, ResearchSession, StreamEvent, TimelineEvent, ModelTier,
} from "@/types";
import { DEFAULT_AGENTS } from "@/lib/agents";
import { listSessions, getSession, startFollowUp, startResearchStream } from "@/lib/api";

// ── Helpers ────────────────────────────────────────────────────────────────

function newBlock(blockIndex: number, query: string): ResearchBlock {
  return {
    id: crypto.randomUUID(),
    blockIndex,
    query,
    report: "",
    findings: [],
    citations: [],
    timeline: [],
    confidence: 0,
    status: "streaming",
    createdAt: Date.now(),
  };
}

function buildReportMarkdown(report: any): string {
  if (!report) return "";
  const parts: string[] = [];
  if (report.title) parts.push(`# ${report.title}\n`);
  if (report.summary) parts.push(`## Executive Summary\n\n${report.summary}\n`);
  if (report.main_content) parts.push(`\n${report.main_content}`);
  if (!parts.length && report.key_findings?.length) {
    parts.push("## Key Findings\n\n" + report.key_findings.map((f: string) => `- ${f}`).join("\n"));
  }
  return parts.join("\n");
}

/** Convert a backend session dict to a local ResearchSession with blocks. */
function dbSessionToLocal(s: any): ResearchSession {
  const report = s.report;
  const reportMd = buildReportMarkdown(report);
  const findings: Finding[] = (report?.key_findings ?? []).map((text: string, i: number) => ({
    id: `f_${i}`,
    agentRole: "researcher" as AgentRole,
    title: text.slice(0, 80),
    summary: text,
    citationIds: [],
    confidence: report?.confidence_score ?? 0,
    relevance: 1,
    createdAt: new Date(s.created_at).getTime(),
  }));
  const citations: Citation[] = (report?.citations ?? []).map((text: string, i: number) => ({
    id: `c_${i}`,
    title: text.slice(0, 80),
    url: "",
    source: "Backend",
    snippet: text,
    verification: "verified" as const,
    confidence: report?.confidence_score ?? 0,
  }));
  const timeline: TimelineEvent[] = (report?.timeline_events ?? []).map((ev: any, i: number) => ({
    id: ev.id ?? `tl_${i}`,
    ts: ev.ts ?? new Date(s.created_at).getTime(),
    agentRole: (ev.agentRole ?? "supervisor") as AgentRole,
    type: (ev.type ?? "search") as TimelineEvent["type"],
    text: ev.text ?? "",
  }));

  // Build blocks from DB messages (each user/assistant pair = one block)
  const blocks: ResearchBlock[] = [];
  const messages: any[] = s.messages ?? [];
  const userMsgs = messages.filter((m: any) => m.role === "user");
  const asstMsgs = messages.filter((m: any) => m.role === "assistant");

  if (userMsgs.length > 0) {
    userMsgs.forEach((um: any, idx: number) => {
      const am = asstMsgs[idx];
      // Each block gets its own report's structured data from the session-level report
      // For the primary session report (idx=0), use structured data.
      // For follow-up blocks, parse findings/citations from the assistant message content
      // and fall back to session-level report data for the first block.
      const blockFindings: Finding[] = idx === 0 ? findings : [];
      const blockCitations: Citation[] = idx === 0 ? citations : [];
      const blockTimeline: TimelineEvent[] = idx === 0 ? timeline : [];
      const blockConfidence = report?.confidence_score ?? 0;

      // For follow-up blocks, extract citations from message content if available
      if (idx > 0 && am?.content) {
        // Use session-level confidence for all blocks (they ran the same pipeline quality)
        // Findings/citations will be populated when SSE streams them live;
        // after DB reload we restore what we can from the session report.
        // For now, assign session-level data to all blocks so the UI isn't empty.
        blockFindings.push(...findings.map((f, i) => ({ ...f, id: `f_${idx}_${i}` })));
        blockCitations.push(...citations.map((c, i) => ({ ...c, id: `c_${idx}_${i}` })));
        blockTimeline.push(...timeline.map((t, i) => ({ ...t, id: `t_${idx}_${i}` })));
      }

      blocks.push({
        id: um.id ?? crypto.randomUUID(),
        blockIndex: idx + 1,
        query: um.content,
        report: am?.content ?? reportMd,
        findings: blockFindings,
        citations: blockCitations,
        timeline: blockTimeline,
        confidence: blockConfidence,
        status: "done",
        createdAt: new Date(um.timestamp ?? s.created_at).getTime(),
      });
    });
  } else if (reportMd) {
    // No messages stored yet but report exists — create single block from report
    blocks.push({
      id: crypto.randomUUID(),
      blockIndex: 1,
      query: s.query,
      report: reportMd,
      findings,
      citations,
      timeline,
      confidence: report?.confidence_score ?? 0,
      status: "done",
      createdAt: new Date(s.created_at).getTime(),
    });
  }

  return {
    id: s.id,
    query: s.query,
    depth: (s.depth as ResearchDepth) ?? "balanced",
    model: (s.model as ModelTier) ?? "groq-compound",
    status: "done",
    createdAt: new Date(s.created_at).getTime(),
    updatedAt: new Date(s.updated_at).getTime(),
    confidence: report?.confidence_score ?? 0,
    tokensUsed: 0,
    agents: DEFAULT_AGENTS.map((a) => ({ ...a, status: "done", progress: 100 })),
    // Legacy flat fields (for backward compat with other components)
    findings,
    citations,
    timeline,
    report: reportMd,
    reasoning: report?.key_findings?.slice(0, 5) ?? [],
    topic: s.title ?? s.query.split(" ").slice(0, 4).join(" "),
    blocks,
  };
}

// ── Store interface ────────────────────────────────────────────────────────

interface ResearchStore {
  sessions: ResearchSession[];
  current: ResearchSession | null;
  isLoading: boolean;
  isFetchingHistory: boolean;
  error: string | null;
  /** id of the in-progress follow-up SSE backend session */
  followUpBackendId: string | null;

  // Session management
  createSession: (query: string, depth: ResearchDepth, model: ModelTier) => ResearchSession;
  loadSession: (id: string) => ResearchSession | null;
  loadSessionFromDB: (id: string) => Promise<ResearchSession | null>;
  loadSessionsFromDB: () => Promise<void>;
  setCurrent: (s: ResearchSession | null) => void;
  addOrUpdateSession: (s: ResearchSession) => void;
  promoteSessionId: (localId: string, dbId: string) => void;

  // Follow-up: APPENDS a new block to current.blocks
  startFollowUpStream: (
    dbSessionId: string,
    query: string,
    depth: ResearchDepth,
    model: ModelTier,
  ) => Promise<{ abort: () => void }>;

  // Event handling (for initial research)
  applyEvent: (e: StreamEvent) => void;
  setStatus: (status: ResearchSession["status"]) => void;
  setError: (error: string | null) => void;

  resetCurrent: () => void;
  resetError: () => void;
}

// ── Store implementation ───────────────────────────────────────────────────

export const useResearchStore = create<ResearchStore>((set, get) => ({
  sessions: [],
  current: null,
  isLoading: false,
  isFetchingHistory: false,
  error: null,
  followUpBackendId: null,

  // ── DB loaders ──────────────────────────────────────────────────────────

  loadSessionsFromDB: async () => {
    set({ isFetchingHistory: true });
    try {
      const data = await listSessions(50, 0);
      const incoming = (data.sessions ?? []).map(dbSessionToLocal);
      set((state) => {
        // Merge: do NOT overwrite a fully-loaded session (multiple blocks from
        // messages) with a list-endpoint summary (single block from report only).
        // A session is "fully loaded" if it has >1 block OR its messages were
        // fetched (detectable: blocks[0].id matches a UUID from the DB message).
        const merged = incoming.map((incomingSession) => {
          const existing = state.sessions.find((x) => x.id === incomingSession.id);
          if (existing && existing.blocks.length > 1) {
            // Keep the fully-loaded version, just update metadata
            return { ...existing, updatedAt: incomingSession.updatedAt };
          }
          return incomingSession;
        });
        // Add any sessions not yet in state
        const existingIds = new Set(state.sessions.map((s) => s.id));
        const newOnes = merged.filter((s) => !existingIds.has(s.id));
        const updated = state.sessions.map((s) => {
          const fresh = merged.find((m) => m.id === s.id);
          if (!fresh) return s;
          if (s.blocks.length > 1) return { ...s, updatedAt: fresh.updatedAt };
          return fresh;
        });
        return { sessions: [...newOnes, ...updated], isFetchingHistory: false };
      });
    } catch (err) {
      console.warn("Could not load session history:", err);
      set({ isFetchingHistory: false });
    }
  },

  loadSessionFromDB: async (id) => {
    try {
      const data = await getSession(id);
      const local = dbSessionToLocal(data);
      set((s) => {
        const existing = s.sessions.find((x) => x.id === id);
        const sessions = existing
          ? s.sessions.map((x) => (x.id === id ? local : x))
          : [local, ...s.sessions];
        return { sessions, current: local };
      });
      return local;
    } catch (err) {
      console.error("Failed to load session from DB:", err);
      return null;
    }
  },

  // ── Session creation ────────────────────────────────────────────────────

  createSession: (query, depth, model) => {
    // Create first block immediately (status=streaming until SSE done)
    const firstBlock = newBlock(1, query);
    const session: ResearchSession = {
      id: crypto.randomUUID(),
      query, depth, model,
      status: "idle",
      createdAt: Date.now(),
      updatedAt: Date.now(),
      confidence: 0,
      tokensUsed: 0,
      agents: DEFAULT_AGENTS.map((a) => ({ ...a })),
      findings: [], citations: [], timeline: [],
      report: "", reasoning: [],
      topic: query.split(" ").slice(0, 4).join(" "),
      blocks: [firstBlock],
    };
    set((s) => ({ sessions: [session, ...s.sessions], current: session }));
    return session;
  },

  addOrUpdateSession: (s) => {
    set((state) => {
      const exists = state.sessions.find((x) => x.id === s.id);
      const sessions = exists
        ? state.sessions.map((x) => (x.id === s.id ? s : x))
        : [s, ...state.sessions];
      return { sessions };
    });
  },

  // ── Follow-up: APPEND new block, never replace ─────────────────────────

  startFollowUpStream: async (dbSessionId, query, depth, model) => {
    const cur = get().current;
    if (!cur) return { abort: () => {} };

    // Create a new block for this follow-up and APPEND it
    const newFollowUpBlock = newBlock(cur.blocks.length + 1, query);

    set((s) => {
      if (!s.current) return {};
      return {
        current: {
          ...s.current,
          status: "running",
          blocks: [...s.current.blocks, newFollowUpBlock],
        },
        followUpBackendId: null, // will be set after response
      };
    });

    let response;
    try {
      response = await startFollowUp(dbSessionId, query, depth, model);
    } catch (err) {
      // Remove the pending block if API call failed
      set((s) => {
        if (!s.current) return {};
        return {
          current: {
            ...s.current,
            status: "done",
            blocks: s.current.blocks.filter((b) => b.id !== newFollowUpBlock.id),
          },
          error: String(err),
        };
      });
      return { abort: () => {} };
    }

    const backendSid = response.session_id;
    set({ followUpBackendId: backendSid });

    const ctrl = startResearchStream(
      { sessionId: backendSid, query, depth, model, forceMock: false },
      {
        onEvent: (event) => {
          const ev = event as any;

          // Helper: update only the new follow-up block (by id)
          const updateBlock = (updater: (b: ResearchBlock) => ResearchBlock) => {
            set((s) => {
              if (!s.current) return {};
              return {
                current: {
                  ...s.current,
                  updatedAt: Date.now(),
                  blocks: s.current.blocks.map((b) =>
                    b.id === newFollowUpBlock.id ? updater(b) : b,
                  ),
                },
              };
            });
          };

          if (ev.type === "report_chunk") {
            updateBlock((b) => ({ ...b, report: b.report + ev.text }));
          } else if (ev.type === "finding") {
            updateBlock((b) => ({ ...b, findings: [...b.findings, ev.finding] }));
          } else if (ev.type === "citation") {
            updateBlock((b) => ({ ...b, citations: [...b.citations, ev.citation] }));
          } else if (ev.type === "timeline") {
            updateBlock((b) => ({ ...b, timeline: [...b.timeline, ev.event] }));
          } else if (ev.type === "done") {
            updateBlock((b) => ({
              ...b,
              status: "done",
              confidence: ev.confidence ?? b.confidence,
            }));
            set((s) => s.current
              ? { current: { ...s.current, status: "done" }, followUpBackendId: null }
              : { followUpBackendId: null });
            // Reload full session from DB to sync — but MERGE so live-streamed data is preserved
            setTimeout(() => {
              // Capture current live-streamed blocks BEFORE the DB reload overwrites them
              const liveBlocks = get().current?.blocks ?? [];
              get().loadSessionFromDB(dbSessionId).then(() => {
                // After DB reload, restore live-streamed findings/citations/timeline/confidence
                // for any block that was empty in the DB (follow-up data isn't per-block in DB yet)
                set((s) => {
                  if (!s.current) return {};
                  const mergedBlocks = s.current.blocks.map((dbBlock) => {
                    const live = liveBlocks.find((lb) => lb.blockIndex === dbBlock.blockIndex);
                    if (!live) return dbBlock;
                    return {
                      ...dbBlock,
                      findings:   dbBlock.findings.length   > 0 ? dbBlock.findings   : live.findings,
                      citations:  dbBlock.citations.length  > 0 ? dbBlock.citations  : live.citations,
                      timeline:   dbBlock.timeline.length   > 0 ? dbBlock.timeline   : live.timeline,
                      confidence: dbBlock.confidence        > 0 ? dbBlock.confidence : live.confidence,
                      report:     dbBlock.report                 ? dbBlock.report     : live.report,
                    };
                  });
                  return { current: { ...s.current, blocks: mergedBlocks } };
                });
              }).catch(() => {});
            }, 2000);
          } else if (ev.type === "error") {
            updateBlock((b) => ({ ...b, status: "error" }));
            set({ error: ev.message ?? "Follow-up failed", followUpBackendId: null });
            set((s) => s.current ? { current: { ...s.current, status: "done" } } : {});
          }
        },
        onClose: () => set({ followUpBackendId: null }),
      },
    );

    return { abort: () => { ctrl.abort(); set({ followUpBackendId: null }); } };
  },

  // ── Promote local UUID → DB UUID ────────────────────────────────────────

  promoteSessionId: (localId, dbId) => {
    set((state) => {
      const sessions = state.sessions.map((s) =>
        s.id === localId ? { ...s, id: dbId } : s,
      );
      const current = state.current?.id === localId
        ? { ...state.current, id: dbId }
        : state.current;
      return { sessions, current };
    });
  },

  // ── Misc ────────────────────────────────────────────────────────────────

  loadSession: (id) => {
    const found = get().sessions.find((s) => s.id === id) ?? null;
    if (found) set({ current: found });
    return found;
  },

  setCurrent: (s) => set({ current: s }),

  setStatus: (status) =>
    set((s) => s.current ? { current: { ...s.current, status, updatedAt: Date.now() } } : {}),

  setError: (error) => set({ error }),

  resetCurrent: () =>
    set((s) =>
      s.current
        ? {
            current: {
              ...s.current,
              status: "idle",
              agents: DEFAULT_AGENTS.map((a) => ({ ...a })),
              findings: [], citations: [], timeline: [],
              report: "", reasoning: [], tokensUsed: 0, confidence: 0,
              blocks: [],
            },
            error: null,
          }
        : { error: null },
    ),

  resetError: () => set({ error: null }),

  // ── applyEvent: updates first block + legacy flat fields ────────────────

  applyEvent: (e) => {
    const cur = get().current;
    if (!cur) return;
    let next: ResearchSession = { ...cur, updatedAt: Date.now() };

    switch (e.type) {
      case "agent_update": {
        const agents = cur.agents.map((a) =>
          a.role === e.agent.role ? { ...a, ...e.agent } : a,
        );
        next = { ...next, agents };
        break;
      }
      case "timeline": {
        const tl = e.event as TimelineEvent;
        next = {
          ...next,
          timeline: [...cur.timeline, tl],
          // Also update block[0]
          blocks: cur.blocks.map((b, i) =>
            i === 0 ? { ...b, timeline: [...b.timeline, tl] } : b,
          ),
        };
        break;
      }
      case "finding": {
        const f = e.finding as Finding;
        next = {
          ...next,
          findings: [...cur.findings, f],
          blocks: cur.blocks.map((b, i) =>
            i === 0 ? { ...b, findings: [...b.findings, f] } : b,
          ),
        };
        break;
      }
      case "citation": {
        const c = e.citation as Citation;
        next = {
          ...next,
          citations: [...cur.citations, c],
          blocks: cur.blocks.map((b, i) =>
            i === 0 ? { ...b, citations: [...b.citations, c] } : b,
          ),
        };
        break;
      }
      case "report_chunk":
        next = {
          ...next,
          report: cur.report + e.text,
          blocks: cur.blocks.map((b, i) =>
            i === 0 ? { ...b, report: b.report + e.text } : b,
          ),
        };
        break;
      case "reasoning":
        next = { ...next, reasoning: [...cur.reasoning, e.text] };
        break;
      case "tokens":
        next = { ...next, tokensUsed: e.total };
        break;
      case "done": {
        const conf = (e as any).confidence ?? 0;
        next = {
          ...next,
          status: "done",
          confidence: conf,
          blocks: cur.blocks.map((b, i) =>
            i === 0 ? { ...b, status: "done", confidence: conf } : b,
          ),
        };
        const dbSid = (e as any).db_session_id as string | undefined;
        const targetId = dbSid ?? next.id;
        setTimeout(() => {
          // Capture live blocks before DB reload overwrites them
          const liveBlocks = get().current?.blocks ?? [];
          get().loadSessionFromDB(targetId).then(() => {
            // Merge: keep live-streamed timeline/findings/citations for block[0]
            set((s) => {
              if (!s.current) return {};
              const mergedBlocks = s.current.blocks.map((dbBlock) => {
                const live = liveBlocks.find((lb) => lb.blockIndex === dbBlock.blockIndex);
                if (!live) return dbBlock;
                return {
                  ...dbBlock,
                  findings:   dbBlock.findings.length   > 0 ? dbBlock.findings   : live.findings,
                  citations:  dbBlock.citations.length  > 0 ? dbBlock.citations  : live.citations,
                  timeline:   dbBlock.timeline.length   > 0 ? dbBlock.timeline   : live.timeline,
                  confidence: dbBlock.confidence        > 0 ? dbBlock.confidence : live.confidence,
                  report:     dbBlock.report                 ? dbBlock.report     : live.report,
                };
              });
              return { current: { ...s.current, blocks: mergedBlocks } };
            });
          }).catch(() => {});
          get().loadSessionsFromDB().catch(() => {});
        }, 2000);
        break;
      }
      case "error":
        next = {
          ...next,
          status: "error",
          blocks: cur.blocks.map((b, i) =>
            i === 0 ? { ...b, status: "error" } : b,
          ),
        };
        set({ error: (e as any).message ?? "Research failed" });
        break;
      case "status":
        if (e.agent) {
          const updatedAgents = cur.agents.map((a) =>
            a.role === (e.agent as AgentRole)
              ? { ...a, status: "thinking" as const, message: e.message }
              : a,
          );
          next = { ...next, agents: updatedAgents };
        }
        break;
      default:
        break;
    }

    const sessions = get().sessions.map((s) => (s.id === next.id ? next : s));
    set({ current: next, sessions });
  },
}));

export { DEFAULT_AGENTS };
export function makeIdleAgent(role: Agent["role"]): Agent {
  return { id: role, role, name: role, status: "idle", progress: 0 };
}
