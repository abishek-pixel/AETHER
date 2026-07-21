import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Command } from "lucide-react";
import { useUIStore } from "@/store/ui";

export function Topbar({ title }: { title?: string }) {
  const toggle = useUIStore((s) => s.toggleCommand);
  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-background/60 backdrop-blur px-4 md:px-6">
      <div className="text-sm text-muted-foreground">
        {title ?? <span><span className="text-foreground font-medium">Aether</span> · AI Research Workspace</span>}
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={toggle} className="gap-2 text-muted-foreground">
          <Command className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Search</span>
          <kbd className="hidden sm:inline rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono">⌘K</kbd>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link to="/login">Sign in</Link>
        </Button>
        <Button asChild size="sm" className="bg-gradient-to-r from-primary to-primary-glow text-primary-foreground shadow-glow">
          <Link to="/signup">Get started</Link>
        </Button>
      </div>
    </header>
  );
}
