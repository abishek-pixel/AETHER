/**
 * ResearchBlockCard — renders a single research block (prompt + results).
 * Each block has its own independent tabs for Report / Findings / Citations / Timeline.
 * Never shares state with other blocks.
 */
import { useRef } from "react";
import type { ResearchBlock, Citation } from "@/types";
import { GlassCard } from "@/components/common/GlassCard";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ReportView } from "@/components/research/ReportView";
import { FindingCard } from "@/components/research/FindingCard";
import { CitationsPanel } from "@/components/research/CitationsPanel";
import { Timeline } from "@/components/research/Timeline";
import { ConfidenceMeter } from "@/components/research/ConfidenceMeter";
import { Loader2, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface Props {
  block: ResearchBlock;
  isLatest?: boolean;
}

export function ResearchBlockCard({ block, isLatest = false }: Props) {
  const streaming = block.status === "streaming";
  const hasError = block.status === "error";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={cn(
        "rounded-2xl border p-5 space-y-4",
        "bg-background/40 backdrop-blur-sm",
        isLatest
          ? "border-primary/40 shadow-[0_0_20px_rgba(139,92,246,0.15)]"
          : "border-border/60",
      )}
    >
      {/* Block header */}
      <div className="flex items-start gap-3">
        <div className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold",
          "border border-primary/40 bg-primary/10 text-primary-glow",
        )}>
          {block.blockIndex}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">
            Research #{block.blockIndex}
          </div>
          <p className="text-sm font-medium leading-snug text-foreground flex items-center gap-2">
            <MessageSquare className="h-3.5 w-3.5 text-primary-glow shrink-0" />
            {block.query}
          </p>
        </div>
        {streaming && (
          <div className="flex items-center gap-1.5 text-xs text-primary-glow shrink-0">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Running…
          </div>
        )}
        {!streaming && block.confidence > 0 && (
          <div className="shrink-0 w-28">
            <ConfidenceMeter value={block.confidence} label="Confidence" />
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="border-t border-border/40" />

      {/* Error state */}
      {hasError && (
        <div className="text-sm text-destructive bg-destructive/10 border border-destructive/30 rounded-lg p-3">
          This research block encountered an error.
        </div>
      )}

      {/* Tabs — each block has completely independent tab state */}
      {!hasError && (
        <Tabs defaultValue="report" className="w-full">
          <TabsList className="h-8">
            <TabsTrigger value="report" className="text-xs">Report</TabsTrigger>
            <TabsTrigger value="findings" className="text-xs">
              Findings ({block.findings.length})
            </TabsTrigger>
            <TabsTrigger value="citations" className="text-xs">
              Citations ({block.citations.length})
            </TabsTrigger>
            <TabsTrigger value="timeline" className="text-xs">
              Timeline ({block.timeline.length})
            </TabsTrigger>
          </TabsList>

          {/* Report */}
          <TabsContent value="report" className="mt-3">
            <div className="rounded-xl border border-border/40 bg-background/20 p-4 min-h-[120px]">
              {!block.report && streaming && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  Generating report…
                </div>
              )}
              {!block.report && !streaming && (
                <p className="text-sm text-muted-foreground italic">No report generated.</p>
              )}
              <ReportView text={block.report} streaming={streaming} />
            </div>
          </TabsContent>

          {/* Findings */}
          <TabsContent value="findings" className="mt-3">
            {block.findings.length === 0 ? (
              <p className="text-sm text-muted-foreground italic">
                {streaming ? "Findings streaming in…" : "No findings for this research."}
              </p>
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                {block.findings.map((f) => (
                  <FindingCard key={f.id} finding={f} citations={block.citations} />
                ))}
              </div>
            )}
          </TabsContent>

          {/* Citations */}
          <TabsContent value="citations" className="mt-3">
            {block.citations.length === 0 ? (
              <p className="text-sm text-muted-foreground italic">
                {streaming ? "Citations streaming in…" : "No citations for this research."}
              </p>
            ) : (
              <CitationsPanel citations={block.citations} />
            )}
          </TabsContent>

          {/* Timeline */}
          <TabsContent value="timeline" className="mt-3">
            <div className="rounded-xl border border-border/40 bg-background/20 p-4">
              {block.timeline.length === 0 ? (
                <p className="text-sm text-muted-foreground italic">
                  {streaming ? "Timeline building…" : "No timeline events for this research."}
                </p>
              ) : (
                <Timeline events={block.timeline} />
              )}
            </div>
          </TabsContent>
        </Tabs>
      )}
    </motion.div>
  );
}
