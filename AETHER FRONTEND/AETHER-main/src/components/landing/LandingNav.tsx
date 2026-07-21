import { Link } from "@tanstack/react-router";
import { Logo } from "@/components/common/Logo";

export function LandingNav() {
  return (
    <nav className="sticky top-0 z-30 border-b border-border bg-background/70 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 h-14">
        <Link to="/"><Logo /></Link>
        <div className="hidden md:flex items-center gap-6 text-sm text-muted-foreground">
          <a href="#demo" className="hover:text-foreground transition-colors">Demo</a>
          <Link to="/dashboard" className="hover:text-foreground transition-colors">Workspace</Link>
          <Link to="/analytics" className="hover:text-foreground transition-colors">Analytics</Link>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/login" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Sign in</Link>
          <Link
            to="/signup"
            className="rounded-md bg-gradient-to-r from-primary to-primary-glow px-3 py-1.5 text-sm text-primary-foreground shadow-glow"
          >
            Get started
          </Link>
        </div>
      </div>
    </nav>
  );
}
