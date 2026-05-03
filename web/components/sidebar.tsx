"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Map, LineChart, GitGraph, Activity, Layers,
  Microscope, Wind, Sparkles, Network, FlaskConical, BookOpen, Bot, AlertTriangle
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/",            icon: LayoutDashboard, label: "Overview"          },
  { href: "/states",      icon: Map,             label: "State Comparison"  },
  { href: "/timeseries",  icon: LineChart,       label: "Time-Series"       },
  { href: "/correlations",icon: GitGraph,        label: "Correlations"      },
  { href: "/clusters",    icon: Layers,          label: "District Clusters" },
  { href: "/seasonality", icon: Activity,        label: "Seasonality"       },
  { href: "/predict",     icon: Sparkles,        label: "Health Predictor"  },
  { href: "/graph",       icon: Network,         label: "Disease Graph"     },
  { href: "/causal",      icon: FlaskConical,    label: "Causal Inference"  },
  { href: "/advanced",    icon: Microscope,      label: "Advanced Analytics"},
  { href: "/sensitivity", icon: AlertTriangle,   label: "Pollution Sensitivity"},
  { href: "/blog",        icon: BookOpen,        label: "The Story"         },
  { href: "/chat",        icon: Bot,             label: "AI Assistant"      },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="hidden lg:flex flex-col w-64 h-screen sticky top-0 border-r border-border/60 bg-card/30 backdrop-blur-md">
      <div className="p-6 border-b border-border/60">
        <Link href="/" className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-sky-500 to-emerald-500 flex items-center justify-center">
            <Wind className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="font-bold text-sm leading-tight gradient-text">AirHealth</div>
            <div className="text-xs text-muted-foreground">India · 2018–2023</div>
          </div>
        </Link>
      </div>
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto scroll-area">
        {NAV.map((item) => {
          const Icon = item.icon;
          const active = path === item.href;
          return (
            <Link key={item.href} href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all",
                active
                  ? "bg-primary/10 text-primary border border-primary/20"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )}>
              <Icon className="w-4 h-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t border-border/60 text-xs text-muted-foreground">
        <div className="font-medium text-foreground/70 mb-1">DSM Final Project</div>
        <div>150 districts · 15 states</div>
        <div>10,800 monthly records</div>
      </div>
    </aside>
  );
}
