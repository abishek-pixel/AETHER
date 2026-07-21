import { motion } from "framer-motion";

export function ConfidenceMeter({ value, label = "Overall confidence" }: { value: number; label?: string }) {
  const pct = Math.round(value * 100);
  const tone = pct >= 80 ? "var(--confidence-high)" : pct >= 60 ? "var(--confidence-med)" : "var(--confidence-low)";
  return (
    <div>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium" style={{ color: tone }}>{pct}%</span>
      </div>
      <div className="mt-1.5 h-2 rounded-full bg-muted overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{ background: `linear-gradient(90deg, ${tone}, var(--primary-glow))` }}
        />
      </div>
    </div>
  );
}
