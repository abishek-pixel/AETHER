import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

export function CTASection() {
  return (
    <section className="relative overflow-hidden border-t border-border py-20 sm:py-28">
      <div className="absolute inset-0 bg-hero opacity-60" />
      <div className="relative mx-auto max-w-3xl px-4 text-center">
        <h2 className="text-3xl sm:text-5xl font-semibold tracking-tight">
          Stop searching. Start <span className="text-gradient">knowing</span>.
        </h2>
        <p className="mt-4 text-muted-foreground">
          Aether's agent swarm runs the entire research workflow for you — and shows its work.
        </p>
        <div className="mt-8 flex justify-center gap-3">
          <Button asChild size="lg" className="bg-gradient-to-r from-primary to-primary-glow text-primary-foreground shadow-glow">
            <Link to="/dashboard">Open the workspace <ArrowRight className="ml-2 h-4 w-4" /></Link>
          </Button>
          <Button asChild size="lg" variant="outline" className="glass">
            <Link to="/signup">Create an account</Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
