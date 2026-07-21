import type { TimelineEvent } from "@/types";
import { AGENT_META } from "@/lib/agents";
import { motion, AnimatePresence } from "framer-motion";

export function Timeline({ events }: { events: TimelineEvent[] }) {
  if (!events.length) {
    return (
      <div className="text-xs text-muted-foreground italic">Timeline will appear as agents work…</div>
    );
  }
  return (
    <ol className="relative space-y-3 border-l border-border pl-4">
      <AnimatePresence initial={false}>
        {events.map((e) => {
          const meta = AGENT_META[e.agentRole];
          return (
            <motion.li
              key={e.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              className="relative"
            >
              <span
                className="absolute -left-[21px] top-1.5 grid h-3.5 w-3.5 place-items-center rounded-full border"
                style={{ borderColor: meta.color as string, background: "var(--background)" }}
              >
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: meta.color as string }} />
              </span>
              <div className="text-xs">
                <span className="font-medium" style={{ color: meta.color as string }}>{meta.name}</span>
                <span className="text-muted-foreground"> · {new Date(e.ts).toLocaleTimeString()}</span>
              </div>
              <div className="text-sm">{e.text}</div>
            </motion.li>
          );
        })}
      </AnimatePresence>
    </ol>
  );
}
