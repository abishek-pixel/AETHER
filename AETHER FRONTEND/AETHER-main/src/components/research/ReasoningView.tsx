import { GlassCard } from "@/components/common/GlassCard";
import { Brain } from "lucide-react";

export function ReasoningView({ thoughts }: { thoughts: string[] }) {
  if (!thoughts.length) return <div className="text-xs text-muted-foreground italic">No reasoning steps yet.</div>;
  return (
    <div className="space-y-2">
      {thoughts.map((t, i) => (
        <GlassCard key={i} className="p-3">
          <div className="flex gap-2">
            <Brain className="mt-0.5 h-3.5 w-3.5 text-primary-glow shrink-0" />
            <div className="text-xs text-muted-foreground">{t}</div>
          </div>
        </GlassCard>
      ))}
    </div>
  );
}
