import { Activity, Layers, ShieldCheck, Zap, Network, FileText } from "lucide-react";
import { GlassCard } from "@/components/common/GlassCard";

const FEATURES = [
  { icon: Network, title: "Multi-agent swarm", desc: "Specialized agents debate, verify, and refine — not a single LLM guessing." },
  { icon: ShieldCheck, title: "Verified citations", desc: "Every claim is grounded with source verification badges and confidence scores." },
  { icon: Activity, title: "Live transparency", desc: "Watch the agents think in real time — searching, debating, and writing." },
  { icon: Zap, title: "Fast or deep", desc: "Choose Fast, Balanced, or Deep (Groq) for the right performance and cost tradeoff." },
  { icon: Layers, title: "Smart memory", desc: "Sessions, collections, and a knowledge graph that connects your research." },
  { icon: FileText, title: "Export anywhere", desc: "Beautifully formatted PDF, DOCX, and Markdown reports in one click." },
];

export function FeatureGrid() {
  return (
    <section className="border-t border-border bg-background/60 py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4">
        <div className="text-center">
          <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight">An operating system for research</h2>
          <p className="mt-3 text-muted-foreground max-w-2xl mx-auto">
            Aether combines a swarm of agents, a transparent reasoning interface,
            and a workspace built for serious knowledge work.
          </p>
        </div>
        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <GlassCard key={f.title} className="p-6" glow>
              <div className="grid h-10 w-10 place-items-center rounded-lg bg-primary/15 border border-primary/30">
                <f.icon className="h-5 w-5 text-primary-glow" />
              </div>
              <h3 className="mt-4 font-medium">{f.title}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{f.desc}</p>
            </GlassCard>
          ))}
        </div>
      </div>
    </section>
  );
}
