import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export function Logo({ className, withText = true }: { className?: string; withText?: boolean }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="relative grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-primary to-primary-glow shadow-glow">
        <Sparkles className="h-4 w-4 text-primary-foreground" />
      </div>
      {withText && (
        <span className="text-lg font-semibold tracking-tight text-gradient">Aether</span>
      )}
    </div>
  );
}
