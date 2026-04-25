import { ReactNode } from "react";
import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  children: ReactNode;
  title?: string;
  variant?: "info" | "warning" | "critical";
  className?: string;
}

const VARIANTS = {
  info:     "border-sky-500/30 bg-sky-500/5",
  warning:  "border-amber-500/30 bg-amber-500/5",
  critical: "border-rose-500/30 bg-rose-500/5",
};

export function InsightBox({ children, title = "Insight", variant = "info", className }: Props) {
  return (
    <div className={cn("rounded-xl border-l-4 px-5 py-4 backdrop-blur-sm", VARIANTS[variant], className)}>
      <div className="flex items-center gap-2 mb-1.5">
        <Sparkles className="w-4 h-4 text-primary" />
        <span className="text-sm font-semibold">{title}</span>
      </div>
      <div className="text-sm text-foreground/80 leading-relaxed">{children}</div>
    </div>
  );
}
