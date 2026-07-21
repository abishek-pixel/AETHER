export type AgentRole =
  | "supervisor"
  | "researcher"
  | "critic"
  | "verifier"
  | "fact-checker"
  | "writer";

export type AgentStatus = "idle" | "thinking" | "searching" | "debating" | "verifying" | "writing" | "done" | "error";

export interface Agent {
  id: string;
  role: AgentRole;
  name: string;
  status: AgentStatus;
  message?: string;
  progress: number; // 0-100
}

export type VerificationStatus = "verified" | "partial" | "conflicting" | "unverified";

export interface Citation {
  id: string;
  title: string;
  url: string;
  source: string;
  snippet: string;
  verification: VerificationStatus;
  confidence: number; // 0-1
}

export interface Finding {
  id: string;
  agentRole: AgentRole;
  title: string;
  summary: string;
  citationIds: string[];
  confidence: number; // 0-1
  relevance: number; // 0-1
  createdAt: number;
}

export interface TimelineEvent {
  id: string;
  ts: number;
  agentRole: AgentRole;
  type: "decompose" | "search" | "debate" | "verify" | "write" | "done";
  text: string;
}

export type ResearchDepth = "fast" | "balanced" | "deep";
export type ModelTier = "groq-fast" | "groq-balanced" | "groq-deep" | "groq-compound" | "groq-qwen";

/** A single research exchange: one prompt → one full AI response. */
export interface ResearchBlock {
  id: string;                 // unique per block (uuid)
  blockIndex: number;         // 1-based display number
  query: string;              // the user prompt for this block
  report: string;             // full markdown report
  findings: Finding[];
  citations: Citation[];
  timeline: TimelineEvent[];
  confidence: number;
  status: "streaming" | "done" | "error";
  createdAt: number;
}

export interface ResearchSession {
  id: string;
  query: string;              // first / primary query
  depth: ResearchDepth;
  model: ModelTier;
  status: "idle" | "running" | "done" | "error";
  createdAt: number;
  updatedAt: number;
  confidence: number;
  tokensUsed: number;
  agents: Agent[];
  /** Legacy flat fields — kept for the first block and backward compat */
  findings: Finding[];
  citations: Citation[];
  timeline: TimelineEvent[];
  report: string;
  reasoning: string[];
  topic?: string;
  /** Multi-block conversation thread */
  blocks: ResearchBlock[];
}

// Backend session types matching API responses
export interface SessionSummary {
  session_id: string;
  query: string;
  status: string;
  depth: string;
  model: string;
  created_at: string | Date;
  updated_at: string | Date;
  confidence: number;
  execution_time: number;
  total_tokens: number;
}

export interface SessionDetail extends SessionSummary {
  decomposition?: Record<string, any>;
  research_summary?: string;
  key_findings: string[];
  citations: string[];
  cost_metrics?: {
    total_cost: number;
    breakdown: Record<string, any>;
    within_budget: boolean;
  };
  errors: string[];
}

export type StreamEvent =
  | { type: "decompose"; subqueries: string[] }
  | { type: "agent_update"; agent: Agent }
  | { type: "timeline"; event: TimelineEvent }
  | { type: "finding"; finding: Finding }
  | { type: "citation"; citation: Citation }
  | { type: "report_chunk"; text: string }
  | { type: "reasoning"; text: string }
  | { type: "tokens"; total: number }
  | { type: "done"; confidence: number }
  | { type: "error"; message: string }
  | { type: "session_start"; session_id: string }
  | { type: "decomposition"; data: Record<string, any> }
  | { type: "report"; data: Record<string, any> }
  | { type: "status"; message: string; agent?: string };
