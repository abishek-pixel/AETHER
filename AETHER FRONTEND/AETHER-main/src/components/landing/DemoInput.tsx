import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ArrowRight, Sparkles } from "lucide-react";
import { useResearchStore } from "@/store/research";
import { motion, AnimatePresence } from "framer-motion";
import { GlassCard } from "@/components/common/GlassCard";

const EXAMPLES = [
  { label: "Simple", q: "What is retrieval-augmented generation?" },
  { label: "Deep", q: "Explain the economic impact of AI agents on knowledge work in 2025" },
  { label: "Comparison", q: "Compare Llama 3, Claude 3.5, and GPT-4o for code generation" },
];

export function DemoInput() {
  const [q, setQ] = useState("");
  const [running, setRunning] = useState(false);
  const navigate = useNavigate();
  const createSession = useResearchStore((s) => s.createSession);

  const start = (query: string) => {
    if (!query.trim()) return;
    setRunning(true);
    const session = createSession(query.trim(), "balanced", "groq-balanced");
    setTimeout(() => navigate({ to: "/research/$sessionId", params: { sessionId: session.id } }), 350);
  };

  return (
    <div className="mx-auto max-w-3xl">
      <GlassCard className="p-2 sm:p-3 shadow-elevated" glow>
        <form
          onSubmit={(e) => { e.preventDefault(); start(q); }}
          className="flex flex-col sm:flex-row items-stretch gap-2"
        >
          <div className="flex flex-1 items-center gap-2 rounded-lg bg-background/40 px-3">
            <Sparkles className="h-4 w-4 text-primary-glow shrink-0" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Ask anything — Aether's swarm will research it for you…"
              className="border-0 bg-transparent focus-visible:ring-0 text-base h-12"
            />
          </div>
          <Button type="submit" disabled={running} size="lg" className="bg-gradient-to-r from-primary to-primary-glow text-primary-foreground shadow-glow">
            {running ? "Starting…" : <>Research <ArrowRight className="ml-2 h-4 w-4" /></>}
          </Button>
        </form>
      </GlassCard>

      <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
        <span className="text-xs text-muted-foreground">Try:</span>
        {EXAMPLES.map((e) => (
          <button
            key={e.label}
            onClick={() => { setQ(e.q); start(e.q); }}
            className="rounded-full border border-border bg-card/60 px-3 py-1 text-xs text-muted-foreground hover:text-foreground hover:border-primary/40 transition-colors"
          >
            <span className="text-primary-glow font-medium mr-1">{e.label}</span> · {e.q.slice(0, 48)}…
          </button>
        ))}
      </div>

      <AnimatePresence>
        {running && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-3 text-center text-xs text-muted-foreground"
          >
            Spinning up the agent swarm…
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
