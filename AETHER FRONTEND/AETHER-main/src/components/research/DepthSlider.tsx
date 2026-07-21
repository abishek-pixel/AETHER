import type { ResearchDepth } from "@/types";
import { cn } from "@/lib/utils";
import { Zap, Scale, Layers } from "lucide-react";

const OPTIONS: { value: ResearchDepth; label: string; icon: typeof Zap; hint: string }[] = [
  { value: "fast", label: "Fast", icon: Zap, hint: "~10s" },
  { value: "balanced", label: "Balanced", icon: Scale, hint: "~30s" },
  { value: "deep", label: "Deep", icon: Layers, hint: "~90s" },
];

export function DepthSlider({ value, onChange }: { value: ResearchDepth; onChange: (v: ResearchDepth) => void }) {
  return (
    <div className="flex items-center gap-1 rounded-lg border border-border bg-card/50 p-0.5">
      {OPTIONS.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            onClick={() => onChange(o.value)}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs transition-colors",
              active ? "bg-primary/15 text-foreground border border-primary/30" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <o.icon className="h-3.5 w-3.5" />
            {o.label}
            <span className="text-[10px] text-muted-foreground">{o.hint}</span>
          </button>
        );
      })}
    </div>
  );
}
