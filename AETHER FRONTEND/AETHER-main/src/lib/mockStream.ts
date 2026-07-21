import type { StreamEvent, AgentRole } from "@/types";

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

const SAMPLE_SOURCES = [
  { source: "Nature", url: "https://nature.com/article/abc" },
  { source: "MIT Tech Review", url: "https://technologyreview.com/2024/x" },
  { source: "arXiv", url: "https://arxiv.org/abs/2403.01234" },
  { source: "Stanford HAI", url: "https://hai.stanford.edu/research" },
  { source: "The Economist", url: "https://economist.com/article" },
  { source: "Bloomberg", url: "https://bloomberg.com/news/article" },
  { source: "OpenAI Blog", url: "https://openai.com/research" },
  { source: "Google DeepMind", url: "https://deepmind.com/research" },
];

export interface RunOptions {
  query: string;
  depth: "fast" | "balanced" | "deep";
  signal?: AbortSignal;
}

export async function runMockResearch(
  opts: RunOptions,
  emit: (e: StreamEvent) => void,
): Promise<void> {
  const { query, depth, signal } = opts;
  const speed = depth === "fast" ? 0.5 : depth === "deep" ? 1.6 : 1;
  const step = (ms: number) => wait(ms * speed);
  const checkAbort = () => { if (signal?.aborted) throw new Error("aborted"); };

  // 1. Decompose
  emit({ type: "agent_update", agent: { id: "supervisor", role: "supervisor", name: "Supervisor", status: "thinking", progress: 20, message: "Decomposing query" } });
  emit({ type: "timeline", event: { id: crypto.randomUUID(), ts: Date.now(), agentRole: "supervisor", type: "decompose", text: `Breaking down: "${query}"` } });
  await step(800);
  checkAbort();

  const subqueries = [
    `Background and definitions related to "${query}"`,
    `Recent developments and key data points`,
    `Counterarguments and limitations`,
    `Expert opinions and authoritative sources`,
  ];
  emit({ type: "decompose", subqueries });
  emit({ type: "reasoning", text: `Plan: split into ${subqueries.length} sub-questions and assign to researcher.` });
  emit({ type: "agent_update", agent: { id: "supervisor", role: "supervisor", name: "Supervisor", status: "done", progress: 100 } });
  await step(400);

  // 2. Researcher searches
  emit({ type: "agent_update", agent: { id: "researcher", role: "researcher", name: "Researcher", status: "searching", progress: 10, message: "Querying sources" } });
  for (let i = 0; i < subqueries.length; i++) {
    checkAbort();
    await step(700);
    const src = SAMPLE_SOURCES[i % SAMPLE_SOURCES.length];
    const cid = crypto.randomUUID();
    emit({ type: "citation", citation: {
      id: cid,
      title: `${src.source}: insights on ${query.slice(0, 40)}`,
      url: src.url,
      source: src.source,
      snippet: `Authoritative analysis covering ${subqueries[i].toLowerCase()}. Includes peer-reviewed data and recent meta-analyses.`,
      verification: i === 2 ? "partial" : "verified",
      confidence: 0.7 + Math.random() * 0.25,
    }});
    emit({ type: "timeline", event: { id: crypto.randomUUID(), ts: Date.now(), agentRole: "researcher", type: "search", text: `Found source from ${src.source}` } });
    emit({ type: "finding", finding: {
      id: crypto.randomUUID(),
      agentRole: "researcher",
      title: subqueries[i],
      summary: `Key insight ${i + 1}: ${SAMPLE_SOURCES[i % SAMPLE_SOURCES.length].source} reports significant evidence aligned with the question. Multiple independent studies converge on a consistent direction with measurable effect sizes.`,
      citationIds: [cid],
      confidence: 0.72 + Math.random() * 0.2,
      relevance: 0.78 + Math.random() * 0.18,
      createdAt: Date.now(),
    }});
    emit({ type: "agent_update", agent: { id: "researcher", role: "researcher", name: "Researcher", status: "searching", progress: 10 + ((i + 1) / subqueries.length) * 80 } });
    emit({ type: "tokens", total: 1200 + i * 850 });
  }
  emit({ type: "agent_update", agent: { id: "researcher", role: "researcher", name: "Researcher", status: "done", progress: 100 } });
  await step(300);

  // 3. Debate (Critic <-> Verifier)
  const debateAgents: AgentRole[] = ["critic", "verifier", "fact-checker"];
  for (const role of debateAgents) {
    checkAbort();
    emit({ type: "agent_update", agent: { id: role, role, name: role, status: role === "critic" ? "debating" : "verifying", progress: 30, message: role === "critic" ? "Challenging claims" : "Cross-referencing" } });
    emit({ type: "timeline", event: { id: crypto.randomUUID(), ts: Date.now(), agentRole: role, type: role === "critic" ? "debate" : "verify", text: role === "critic" ? "Identified 1 weak claim — requesting evidence" : "Verified 3/4 claims against primary sources" } });
    emit({ type: "reasoning", text: role === "critic"
      ? "Claim #3 relies on a single source — flagging for re-verification."
      : `Verifier: cross-referenced ${role === "fact-checker" ? "primary" : "secondary"} sources, agreement high.` });
    await step(700);
    emit({ type: "agent_update", agent: { id: role, role, name: role, status: "done", progress: 100 } });
  }

  // 4. Writer
  emit({ type: "agent_update", agent: { id: "writer", role: "writer", name: "Writer", status: "writing", progress: 20, message: "Synthesizing report" } });
  emit({ type: "timeline", event: { id: crypto.randomUUID(), ts: Date.now(), agentRole: "writer", type: "write", text: "Composing final report" } });

  const reportParagraphs = [
    `## Executive Summary\n\nBased on a multi-agent investigation into **"${query}"**, our research swarm reviewed authoritative sources across academic, industry, and journalistic domains. The analysis converged on a high-confidence answer supported by ${subqueries.length} cross-verified findings.`,
    `\n\n## Key Findings\n\n1. The evidence base is broad and recent, with multiple independent sources reaching consistent conclusions.\n2. One area shows partial verification — flagged for follow-up.\n3. Counter-arguments were considered and addressed.`,
    `\n\n## Detailed Analysis\n\nThe Researcher agent gathered ${subqueries.length} primary findings. The Critic challenged claim #3, and the Verifier confirmed 3 of 4 claims with primary sources. Confidence is high overall.`,
    `\n\n## Recommendations\n\n- Cite the verified findings directly.\n- Treat the partially-verified claim as provisional.\n- Re-run a deep search if higher confidence is required on the flagged claim.`,
    `\n\n## Conclusion\n\nThe synthesized answer is well-supported. See citations panel for full source list.`,
  ];

  for (const para of reportParagraphs) {
    const words = para.split(" ");
    for (const w of words) {
      checkAbort();
      emit({ type: "report_chunk", text: w + " " });
      await wait(18);
    }
    emit({ type: "agent_update", agent: { id: "writer", role: "writer", name: "Writer", status: "writing", progress: Math.min(100, 20 + reportParagraphs.indexOf(para) * 18) } });
  }

  emit({ type: "agent_update", agent: { id: "writer", role: "writer", name: "Writer", status: "done", progress: 100 } });
  emit({ type: "tokens", total: 8420 });
  emit({ type: "done", confidence: 0.89 });
}
