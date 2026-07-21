import type { Agent, AgentRole } from "@/types";
import { Brain, Search, Scale, ShieldCheck, BadgeCheck, PenLine } from "lucide-react";

export const AGENT_META: Record<AgentRole, {
  name: string;
  description: string;
  color: string;
  icon: typeof Brain;
}> = {
  supervisor: { name: "Supervisor", description: "Plans and decomposes the query", color: "var(--agent-supervisor)", icon: Brain },
  researcher: { name: "Researcher", description: "Searches sources and gathers evidence", color: "var(--agent-researcher)", icon: Search },
  critic: { name: "Critic", description: "Challenges assumptions and findings", color: "var(--agent-critic)", icon: Scale },
  verifier: { name: "Verifier", description: "Cross-references claims", color: "var(--agent-verifier)", icon: ShieldCheck },
  "fact-checker": { name: "Fact Checker", description: "Validates with primary sources", color: "var(--agent-verifier)", icon: BadgeCheck },
  writer: { name: "Writer", description: "Synthesizes the final report", color: "var(--agent-writer)", icon: PenLine },
};

export const DEFAULT_AGENTS: Agent[] = (
  ["supervisor", "researcher", "critic", "verifier", "fact-checker", "writer"] as AgentRole[]
).map((role) => ({
  id: role,
  role,
  name: AGENT_META[role].name,
  status: "idle",
  progress: 0,
}));
