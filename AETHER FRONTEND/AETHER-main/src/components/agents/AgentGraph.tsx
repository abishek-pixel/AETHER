import { motion } from "framer-motion";
import type { Agent } from "@/types";
import { AGENT_META, DEFAULT_AGENTS } from "@/lib/agents";
import { cn } from "@/lib/utils";

interface AgentGraphProps {
  agents?: Agent[];
  compact?: boolean;
}

export function AgentGraph({ agents = DEFAULT_AGENTS, compact }: AgentGraphProps) {
  // Layout: hub-and-spoke with supervisor at top, writer at bottom
  const W = 600, H = compact ? 280 : 360;
  const cx = W / 2;
  const positions: Record<string, { x: number; y: number }> = {
    supervisor:  { x: cx,        y: 40 },
    researcher:  { x: cx - 200,  y: H / 2 },
    critic:      { x: cx - 80,   y: H - 60 },
    verifier:    { x: cx + 80,   y: H - 60 },
    "fact-checker": { x: cx + 200, y: H / 2 },
    writer:      { x: cx,        y: H - 20 },
  };

  const edges: [string, string][] = [
    ["supervisor", "researcher"],
    ["supervisor", "fact-checker"],
    ["researcher", "critic"],
    ["fact-checker", "verifier"],
    ["critic", "verifier"],
    ["critic", "writer"],
    ["verifier", "writer"],
  ];

  const isActive = (id: string) => {
    const a = agents.find((x) => x.id === id);
    return a && (a.status !== "idle" && a.status !== "done");
  };
  const isDone = (id: string) => agents.find((x) => x.id === id)?.status === "done";

  return (
    <div className="relative w-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
        <defs>
          <linearGradient id="edgeGrad" x1="0" x2="1">
            <stop offset="0%" stopColor="oklch(0.66 0.22 280)" stopOpacity="0.7" />
            <stop offset="100%" stopColor="oklch(0.78 0.16 200)" stopOpacity="0.7" />
          </linearGradient>
          <filter id="glow"><feGaussianBlur stdDeviation="3" /></filter>
        </defs>

        {edges.map(([a, b], i) => {
          const A = positions[a], B = positions[b];
          const active = isActive(a) || isActive(b);
          return (
            <g key={i}>
              <line x1={A.x} y1={A.y} x2={B.x} y2={B.y}
                stroke="url(#edgeGrad)"
                strokeOpacity={active ? 0.9 : 0.18}
                strokeWidth={active ? 2 : 1}
                strokeDasharray={active ? "0" : "4 6"}
              />
              {active && (
                <motion.g
                  initial={{ x: A.x, y: A.y, opacity: 0 }}
                  animate={{
                    x: [A.x, B.x],
                    y: [A.y, B.y],
                    opacity: [0, 1, 0],
                  }}
                  transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
                >
                  <circle r={3} fill="oklch(0.78 0.16 200)" filter="url(#glow)" />
                </motion.g>
              )}
            </g>
          );
        })}

        {Object.entries(positions).map(([id, p]) => {
          const agent = agents.find((a) => a.id === id);
          const meta = AGENT_META[id as keyof typeof AGENT_META];
          if (!meta) return null;
          const active = isActive(id);
          const done = isDone(id);
          return (
            <g key={id} transform={`translate(${p.x}, ${p.y})`}>
              {active && (
                <motion.circle
                  r={28}
                  fill="none"
                  stroke={meta.color}
                  strokeWidth="1.5"
                  strokeOpacity="0.5"
                  style={{ transformBox: "fill-box", transformOrigin: "center" }}
                  animate={{ scale: [0.8, 1.2, 0.8], opacity: [0.6, 0, 0.6] }}
                  transition={{ duration: 2, repeat: Infinity }}
                />
              )}
              <circle r="20" fill="oklch(0.20 0.025 265)" stroke={done ? "oklch(0.74 0.18 155)" : meta.color} strokeWidth="2" />
              <foreignObject x="-10" y="-10" width="20" height="20">
                <div className="flex h-full w-full items-center justify-center text-foreground">
                  <meta.icon className="h-4 w-4" style={{ color: meta.color as string }} />
                </div>
              </foreignObject>
              <text y="38" textAnchor="middle" className="fill-foreground" fontSize="11" fontWeight="500">
                {meta.name}
              </text>
              {agent?.message && active && (
                <text y="52" textAnchor="middle" className="fill-muted-foreground" fontSize="9">
                  {agent.message.slice(0, 28)}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Status legend */}
      <div className="mt-3 flex flex-wrap gap-2 justify-center">
        {agents.map((a) => (
          <div key={a.id} className={cn(
            "flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px]",
            a.status === "done" && "border-confidence-high/30 text-confidence-high",
            a.status !== "done" && a.status !== "idle" && "border-primary/40 text-foreground bg-primary/10",
            a.status === "idle" && "border-border text-muted-foreground",
          )}>
            <span className={cn(
              "h-1.5 w-1.5 rounded-full",
              a.status === "done" && "bg-confidence-high",
              a.status !== "done" && a.status !== "idle" && "bg-primary animate-pulse",
              a.status === "idle" && "bg-muted-foreground/40",
            )} />
            {AGENT_META[a.role].name} · {a.status}
          </div>
        ))}
      </div>
    </div>
  );
}
