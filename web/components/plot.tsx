"use client";
import dynamic from "next/dynamic";
import { useMemo } from "react";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface PlotProps {
  data: any[];
  layout?: any;
  config?: any;
  className?: string;
  height?: number;
}

const DARK_LAYOUT = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor:  "rgba(0,0,0,0)",
  font: { color: "#cbd5e1", family: "Inter, sans-serif", size: 12 },
  margin: { l: 50, r: 20, t: 30, b: 40 },
  xaxis: {
    gridcolor: "rgba(148,163,184,0.1)",
    zerolinecolor: "rgba(148,163,184,0.2)",
    tickcolor:  "rgba(148,163,184,0.4)",
    linecolor:  "rgba(148,163,184,0.2)",
  },
  yaxis: {
    gridcolor: "rgba(148,163,184,0.1)",
    zerolinecolor: "rgba(148,163,184,0.2)",
    tickcolor:  "rgba(148,163,184,0.4)",
    linecolor:  "rgba(148,163,184,0.2)",
  },
  legend: { bgcolor: "rgba(0,0,0,0)" },
  hoverlabel: { bgcolor: "#1e293b", bordercolor: "#334155", font: { color: "#e2e8f0" } },
  colorway: ["#38bdf8", "#34d399", "#fbbf24", "#f87171", "#a78bfa", "#f472b6", "#22d3ee", "#facc15"],
};

export function PlotlyChart({ data, layout = {}, config = {}, className, height = 400 }: PlotProps) {
  const mergedLayout = useMemo(() => ({
    ...DARK_LAYOUT,
    ...layout,
    xaxis: { ...DARK_LAYOUT.xaxis, ...(layout.xaxis || {}) },
    yaxis: { ...DARK_LAYOUT.yaxis, ...(layout.yaxis || {}) },
    autosize: true,
    height,
  }), [layout, height]);

  const mergedConfig = useMemo(() => ({
    displayModeBar: false,
    responsive: true,
    ...config,
  }), [config]);

  return (
    <div className={className}>
      <Plot
        data={data}
        layout={mergedLayout}
        config={mergedConfig}
        style={{ width: "100%", height: `${height}px` }}
        useResizeHandler
      />
    </div>
  );
}
