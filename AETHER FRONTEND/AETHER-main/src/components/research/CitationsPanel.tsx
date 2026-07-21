/**
 * CitationsPanel — renders citation links that ALWAYS open in a new tab.
 * Never uses <Link> (which triggers SPA navigation) and never uses href="#".
 */
import type { Citation } from "@/types";
import { ExternalLink, ShieldCheck, ShieldQuestion, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

const VERIFICATION_META = {
  verified:   { icon: ShieldCheck,    color: "text-confidence-high" },
  partial:    { icon: ShieldQuestion, color: "text-confidence-med" },
  conflicting:{ icon: AlertTriangle,  color: "text-confidence-low" },
  unverified: { icon: ShieldQuestion, color: "text-muted-foreground" },
} as const;

export function CitationsPanel({ citations }: { citations: Citation[] }) {
  if (!citations.length) {
    return <div className="text-xs text-muted-foreground italic">Citations will stream in here.</div>;
  }

  return (
    <ul className="space-y-2">
      {citations.map((c) => {
        const m = VERIFICATION_META[c.verification] ?? VERIFICATION_META.unverified;
        const hasUrl = !!c.url && c.url.startsWith("http");

        const inner = (
          <div className="rounded-lg border border-border bg-background/40 p-2.5 hover:border-primary/40 transition-colors group cursor-pointer">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 text-xs">
                <m.icon className={cn("h-3.5 w-3.5 shrink-0", m.color)} />
                <span className="font-medium text-foreground">{c.source || "Source"}</span>
              </div>
              {hasUrl && <ExternalLink className="h-3 w-3 shrink-0 text-muted-foreground group-hover:text-foreground" />}
            </div>
            <div className="mt-1 text-sm line-clamp-2">{c.title}</div>
            {c.snippet && (
              <div className="mt-1 text-xs text-muted-foreground line-clamp-2">{c.snippet}</div>
            )}
          </div>
        );

        if (hasUrl) {
          return (
            <li key={c.id}>
              {/* IMPORTANT: target="_blank" + rel="noopener noreferrer" prevents
                  the click from triggering React Router navigation or page reload */}
              <a
                href={c.url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
              >
                {inner}
              </a>
            </li>
          );
        }

        return <li key={c.id}>{inner}</li>;
      })}
    </ul>
  );
}
