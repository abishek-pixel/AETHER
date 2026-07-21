import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/common/GlassCard";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useUIStore } from "@/store/ui";
import { useState } from "react";
import { ModelSelector } from "@/components/research/ModelSelector";
import type { ModelTier } from "@/types";
import { toast } from "sonner";

export const Route = createFileRoute("/settings")({
  head: () => ({ meta: [{ title: "Settings — Aether" }, { name: "description", content: "Configure your Aether workspace." }] }),
  component: SettingsPage,
});

function SettingsPage() {
  const apiBaseUrl = useUIStore((s) => s.apiBaseUrl);
  const setApiBaseUrl = useUIStore((s) => s.setApiBaseUrl);
  const [url, setUrl] = useState(apiBaseUrl);
  const [model, setModel] = useState<ModelTier>("groq-balanced");

  return (
    <AppShell title="Settings">
      <div className="mx-auto max-w-3xl p-6 space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>

        <GlassCard className="p-5 space-y-3">
          <div>
            <h2 className="text-sm font-medium">Backend</h2>
            <p className="text-xs text-muted-foreground">URL of your FastAPI backend. SSE stream is expected at <code className="text-foreground">/research/stream</code>.</p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="api">API base URL</Label>
            <Input id="api" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://localhost:8000" />
          </div>
          <Button onClick={() => { setApiBaseUrl(url); toast.success("Saved"); }} className="bg-gradient-to-r from-primary to-primary-glow text-primary-foreground">Save</Button>
        </GlassCard>

        <GlassCard className="p-5 space-y-3">
          <div>
            <h2 className="text-sm font-medium">Default model</h2>
            <p className="text-xs text-muted-foreground">Used for new research sessions.</p>
          </div>
          <ModelSelector value={model} onChange={setModel} />
        </GlassCard>

        <GlassCard className="p-5 space-y-2">
          <h2 className="text-sm font-medium">Theme</h2>
          <p className="text-xs text-muted-foreground">Aether is dark by default. A light theme is on the roadmap.</p>
        </GlassCard>
      </div>
    </AppShell>
  );
}
