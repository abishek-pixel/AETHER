import * as React from "react";
import { cn } from "@/lib/utils";

export const GlassCard = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { glow?: boolean }
>(({ className, glow, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "glass rounded-xl shadow-card transition-all",
      glow && "hover:shadow-glow",
      className,
    )}
    {...props}
  />
));
GlassCard.displayName = "GlassCard";
