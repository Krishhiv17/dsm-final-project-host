import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  value: string | number;
  delta?: string;
  icon?: ReactNode;
  tone?: "default" | "warning" | "critical" | "success" | "info";
  className?: string;
}

const TONES = {
  default:  "from-slate-700/40 to-slate-800/40 border-slate-700/50",
  warning:  "from-amber-500/20 to-orange-500/10 border-amber-500/30",
  critical: "from-rose-500/20 to-red-600/10 border-rose-500/30",
  success:  "from-emerald-500/20 to-teal-500/10 border-emerald-500/30",
  info:     "from-sky-500/20 to-cyan-500/10 border-sky-500/30",
};

export function KPICard({ label, value, delta, icon, tone = "default", className }: Props) {
  return (
    <div className={cn(
      "relative overflow-hidden rounded-xl border bg-gradient-to-br p-5 backdrop-blur-sm animate-fade-in",
      TONES[tone],
      className
    )}>
      <div className="flex items-start justify-between mb-3">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        {icon && <div className="opacity-70">{icon}</div>}
      </div>
      <div className="text-3xl font-bold tracking-tight">{value}</div>
      {delta && (
        <div className="mt-2 text-xs text-muted-foreground">{delta}</div>
      )}
    </div>
  );
}
