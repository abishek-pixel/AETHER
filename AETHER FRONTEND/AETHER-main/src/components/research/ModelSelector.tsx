import type { ModelTier } from "@/types";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

interface ModelOption {
  value: ModelTier;
  label: string;
  description: string;
  provider: string;
  badge?: string;
}

const OPTIONS: ModelOption[] = [
  {
    value: "groq-compound",
    label: "Compound AI",
    description: "Groq's most capable model — best for complex research",
    provider: "Groq",
    badge: "Best",
  },
  {
    value: "groq-qwen",
    label: "Qwen 3.6 27B",
    description: "Alibaba Qwen — strong reasoning & multilingual",
    provider: "Groq",
    badge: "New",
  },
  {
    value: "groq-balanced",
    label: "Llama 3.3 70B",
    description: "Meta Llama — balanced speed & quality",
    provider: "Groq",
  },
  {
    value: "groq-fast",
    label: "Llama 3.1 8B",
    description: "Fastest option — ideal for quick lookups",
    provider: "Groq",
  },
];

export function ModelSelector({
  value,
  onChange,
  disabled,
}: {
  value: ModelTier;
  onChange: (v: ModelTier) => void;
  disabled?: boolean;
}) {
  return (
    <Select
      value={value}
      onValueChange={(v) => onChange(v as ModelTier)}
      disabled={disabled}
    >
      <SelectTrigger className="h-8 w-[240px] bg-card/50 text-xs">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {OPTIONS.map((o) => (
          <SelectItem key={o.value} value={o.value} className="text-xs">
            <div className="flex items-center gap-2">
              <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[10px] text-primary-glow">
                {o.provider}
              </span>
              <span className="flex-1">{o.label}</span>
              {o.badge && (
                <span className="rounded bg-primary/20 px-1.5 py-0.5 text-[10px] text-primary-glow font-medium">
                  {o.badge}
                </span>
              )}
            </div>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
