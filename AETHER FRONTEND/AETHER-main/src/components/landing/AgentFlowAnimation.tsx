import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { AGENT_META } from "@/lib/agents";
import type { AgentRole } from "@/types";
import { cn } from "@/lib/utils";

const FLOW: AgentRole[] = ["supervisor", "researcher", "critic", "verifier", "writer"];

export function AgentFlowAnimation() {
  const [active, setActive] = useState(0);
  const reduce = useReducedMotion();

  useEffect(() => {
    if (reduce) return;
    const t = setInterval(() => setActive((i) => (i + 1) % FLOW.length), 1400);
    return () => clearInterval(t);
  }, [reduce]);

  return (
    <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-4">
      {FLOW.map((role, i) => {
        const meta = AGENT_META[role];
        const isOn = i === active;
        return (
          <div key={role} className="flex items-center gap-2 sm:gap-4">
            <motion.div
              animate={isOn ? { scale: 1.05 } : { scale: 1 }}
              className={cn(
                "relative flex flex-col items-center gap-1.5 rounded-2xl border px-3 py-3 sm:px-4 sm:py-4 transition-all glass min-w-[88px]",
                isOn ? "border-primary/60 shadow-glow" : "border-border",
              )}
            >
              {isOn && (
                <motion.div
                  layoutId="agent-glow"
                  className="absolute inset-0 rounded-2xl"
                  style={{ background: `radial-gradient(circle, ${meta.color} 0%, transparent 70%)`, opacity: 0.18 }}
                />
              )}
              <div
                className="grid h-9 w-9 place-items-center rounded-full"
                style={{ background: `color-mix(in oklab, ${meta.color} 25%, transparent)`, border: `1px solid ${meta.color}` }}
              >
                <meta.icon className="h-4 w-4" style={{ color: meta.color as string }} />
              </div>
              <div className="text-xs font-medium">{meta.name}</div>
              <div className={cn("text-[10px]", isOn ? "text-primary-glow" : "text-muted-foreground")}>
                {isOn ? "Working…" : "Idle"}
              </div>
            </motion.div>
            {i < FLOW.length - 1 && (
              <div className="relative h-px w-6 sm:w-12 bg-border overflow-hidden">
                <motion.div
                  className="absolute inset-y-0 w-1/2 bg-gradient-to-r from-transparent via-primary to-transparent"
                  animate={{ x: ["-100%", "200%"] }}
                  transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
