import { createFileRoute } from "@tanstack/react-router";
import { LandingNav } from "@/components/landing/LandingNav";
import { Hero } from "@/components/landing/Hero";
import { FeatureGrid } from "@/components/landing/FeatureGrid";
import { CTASection } from "@/components/landing/CTASection";
import { Logo } from "@/components/common/Logo";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Aether — Research Smarter with Multi-Agent AI" },
      { name: "description", content: "Aether is a premium AI research workspace powered by an autonomous multi-agent swarm. Get verified, transparent answers in seconds." },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <LandingNav />
      <main>
        <Hero />
        <FeatureGrid />
        <CTASection />
      </main>
      <footer className="border-t border-border py-8">
        <div className="mx-auto flex max-w-6xl flex-col sm:flex-row items-center justify-between gap-4 px-4">
          <Logo />
          <div className="text-xs text-muted-foreground">© {new Date().getFullYear()} Aether Research, Inc.</div>
        </div>
      </footer>
    </div>
  );
}
