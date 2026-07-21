/**
 * Aether API Types
 * Type-safe definitions for all API requests, responses, and events
 */

// ==================== ENUMS & CONSTANTS ====================

export type ResearchDepth = "fast" | "balanced" | "deep";
export type ExportFormat = "markdown" | "pdf" | "docx";
export type SessionLifecycleStatus =
  | "initialized"
  | "in_progress"
  | "running"
  | "completed"
  | "complete"
  | "done"
  | "failed"
  | "error";
export type AgentName = "researcher" | "critic" | "fact_checker" | "verifier" | "writer" | "supervisor";
export type StreamEventType =
  | "session_start"
  | "decomposition"
  | "finding"
  | "citation"
  | "report"
  | "report_chunk"
  | "tokens"
  | "agent_update"
  | "timeline"
  | "done"
  | "error";

// ==================== REQUEST TYPES ====================

export interface ResearchRequest {
  query: string;
  depth: ResearchDepth;
  model: string;
  max_iterations?: number;
  verify_results?: boolean;
  include_citations?: boolean;
}

export interface FeedbackRequest {
  rating: number; // 1-5
  comment?: string;
  helpful_findings?: number[];
  improvement_suggestions?: string[];
}

export interface ExportRequest {
  format: ExportFormat;
  include_citations?: boolean;
  include_reasoning?: boolean;
}

// ==================== RESPONSE TYPES ====================

export interface CostMetrics {
  total_cost: number;
  breakdown: Record<string, number>;
  within_budget: boolean;
}

export interface ResearchResponse {
  status: SessionLifecycleStatus;
  session_id: string;
  decomposition?: Record<string, any>;
  research_summary?: string;
  key_findings: string[];
  citations: string[];
  confidence_score: number;
  cost_metrics?: CostMetrics;
  errors: string[];
  execution_time: number;
  total_tokens?: Record<string, number>;
}

export interface SessionStatus {
  session_id: string;
  status: SessionLifecycleStatus;
  query: string;
  depth: ResearchDepth;
  model: string;
  created_at: string;
  updated_at: string;
  progress: number; // 0-100
  agents_status: Record<string, AgentStatus>;
  current_agent: AgentName | null;
}

export interface AgentStatus {
  name: AgentName;
  status: "idle" | "running" | "completed" | "failed";
  progress: number;
  message?: string;
}

export interface SessionSummary {
  session_id: string;
  query: string;
  status: SessionLifecycleStatus;
  depth: ResearchDepth;
  model: string;
  created_at: string;
  updated_at: string;
  confidence: number;
  execution_time: number;
  total_tokens: number;
  topic?: string;
}

export interface SessionListResponse {
  sessions: SessionSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface FeedbackResponse {
  status: string;
  message: string;
  feedback_id: string;
}

export interface AnalyticsResponse {
  total_sessions: number;
  total_time_saved: number;
  average_confidence: number;
  total_tokens_used: Record<string, number>;
  total_cost: number;
  sessions_last_7_days: number;
  top_topics: string[];
  depth_distribution: Record<string, number>;
  model_distribution: Record<string, number>;
  avg_execution_time: number;
}

export interface MemoryGraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata: Record<string, any>;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, any>;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
  weight?: number;
}

export interface HealthResponse {
  status: "healthy" | "unhealthy";
  version: string;
  timestamp: string;
  uptime: number;
  memory_system: "available" | "unavailable";
  neo4j: "healthy" | "unavailable";
  qdrant: "healthy" | "unavailable";
}

// ==================== STREAMING TYPES ====================

export interface StreamEvent {
  type: StreamEventType;
  timestamp: string;
  session_id?: string;
  agent?: AgentName;
  status?: string;
  progress?: number;
  message?: string;
  data?: Record<string, any>;
}

export interface StreamEventDecomposition extends StreamEvent {
  type: "decomposition";
  data: {
    sub_queries: string[];
    research_plan: string;
  };
}

export interface StreamEventFinding extends StreamEvent {
  type: "finding";
  data: {
    text: string;
    index: number;
    source?: string;
    confidence?: number;
  };
}

export interface StreamEventCitation extends StreamEvent {
  type: "citation";
  data: {
    text: string;
    index: number;
    url?: string;
  };
}

export interface StreamEventReport extends StreamEvent {
  type: "report";
  data: {
    summary: string;
    recommendations?: string[];
  };
}

export interface StreamEventAgentUpdate extends StreamEvent {
  type: "agent_update";
  data: {
    agent_name: AgentName;
    status: string;
    progress: number;
    current_task?: string;
  };
}

export interface StreamEventDone extends StreamEvent {
  type: "done";
  data: {
    session_id: string;
    status: SessionLifecycleStatus;
    execution_time: number;
  };
}

export interface StreamEventError extends StreamEvent {
  type: "error";
  data: {
    error_code: string;
    message: string;
  };
}

export type AnyStreamEvent =
  | StreamEvent
  | StreamEventDecomposition
  | StreamEventFinding
  | StreamEventCitation
  | StreamEventReport
  | StreamEventAgentUpdate
  | StreamEventDone
  | StreamEventError;

// ==================== ERROR TYPES ====================

export class APIError extends Error {
  constructor(
    public status: number,
    public detail: any,
    message: string = "API Error"
  ) {
    super(message);
    this.name = "APIError";
  }
}

// ==================== HANDLER TYPES ====================

export interface StreamHandlers {
  onEvent: (event: AnyStreamEvent) => void;
  onError?: (err: Error) => void;
  onClose?: () => void;
}

export interface StartStreamOptions {
  sessionId?: string;
  query: string;
  depth: ResearchDepth;
  model: string;
  forceMock?: boolean;
}

// ==================== INTERNAL TYPES ====================

export interface ResearchSession {
  session_id: string;
  query: string;
  status: SessionLifecycleStatus;
  created_at: Date;
  updated_at: Date;
  events: AnyStreamEvent[];
  result?: ResearchResponse;
}
