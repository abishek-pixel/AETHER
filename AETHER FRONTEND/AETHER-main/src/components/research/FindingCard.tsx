import type { Finding, Citation } from "@/types";
import { GlassCard } from "@/components/common/GlassCard";
import { AGENT_META } from "@/lib/agents";
import { ExternalLink, ShieldCheck, AlertTriangle, ShieldQuestion } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

const verifyMeta = {
  verified: { icon: ShieldCheck, label: "Verified", className: "text-confidence-high border-confidence-high/30 bg-confidence-high/10" },
  partial: { icon: ShieldQuestion, label: "Partial", className: "text-confidence-med border-confidence-med/30 bg-confidence-med/10" },
  conflicting: { icon: AlertTriangle, label: "Conflicting", className: "text-confidence-low border-confidence-low/30 bg-confidence-low/10" },
  unverified: { icon: ShieldQuestion, label: "Unverified", className: "text-muted-foreground border-border bg-muted/20" },
};

export function FindingCard({ finding, citations }: { finding: Finding; citations: Citation[] }) {
  const refs = citations.filter((c) => finding.citationIds.includes(c.id));
  const meta = AGENT_META[finding.agentRole];
  const confPct = Math.round(finding.confidence * 100);
  const relPct = Math.round(finding.relevance * 100);
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <GlassCard className="p-4" glow>
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 text-xs">
            <span
              className="rounded px-1.5 py-0.5 border"
              style={{ borderColor: `${meta.color}55`, color: meta.color as string, background: `color-mix(in oklab, ${meta.color} 12%, transparent)` }}
            >
              {meta.name}
            </span>
            <span className="text-muted-foreground">Relevance {relPct}%</span>
          </div>
          <ConfidenceBadge value={confPct} />
        </div>
        <h4 className="font-medium text-sm">{finding.title}</h4>
        <p className="mt-1 text-sm text-muted-foreground">{finding.summary}</p>
        {refs.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {refs.map((c) => {
              const v = verifyMeta[c.verification];
              return (
                <a
                  key={c.id}
                  href={c.url} target="_blank" rel="noreferrer"
                  className="flex items-center gap-2 rounded-md border border-border bg-background/40 px-2 py-1.5 text-xs hover:border-primary/40 transition-colors"
                >
                  <span className={cn("flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px]", v.className)}>
                    <v.icon className="h-3 w-3" /> {v.label}
                  </span>
                  <span className="text-foreground">{c.source}</span>
                  <span className="text-muted-foreground line-clamp-1 flex-1">{c.title}</span>
                  <ExternalLink className="h-3 w-3 text-muted-foreground" />
                </a>
              );
            })}
          </div>
        )}
      </GlassCard>
    </motion.div>
  );
}

function ConfidenceBadge({ value }: { value: number }) {
  const tone = value >= 80 ? "high" : value >= 60 ? "med" : "low";
  const map = {
    high: "text-confidence-high border-confidence-high/30 bg-confidence-high/10",
    med: "text-confidence-med border-confidence-med/30 bg-confidence-med/10",
    low: "text-confidence-low border-confidence-low/30 bg-confidence-low/10",
  } as const;
  return (
    <span className={cn("rounded border px-1.5 py-0.5 text-[10px]", map[tone])}>
      {value}% confidence
    </span>
  );
}
