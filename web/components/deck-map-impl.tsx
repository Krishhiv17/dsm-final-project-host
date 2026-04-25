"use client";
import { useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import { ScatterplotLayer, LineLayer } from "@deck.gl/layers";

interface NodeFeature {
  district_id: number;
  district_name: string;
  state: string;
  lat: number;
  lon: number;
  community?: number;
  pm25_mean?: number;
  resp_rate_mean?: number;
  betweenness_centrality?: number;
}

interface EdgeFeature {
  source_id: number;
  target_id: number;
  weight?: number;
}

interface Props {
  nodes: NodeFeature[];
  edges?: EdgeFeature[];
  colorBy?: "community" | "pm25_mean" | "resp_rate_mean";
  height?: number;
}

const COMMUNITY_COLORS: Record<number, [number, number, number]> = {
  0: [56, 189, 248],
  1: [52, 211, 153],
  2: [251, 191, 36],
  3: [248, 113, 113],
  4: [167, 139, 250],
  5: [244, 114, 182],
  6: [34, 211, 238],
};

function pollutionColor(v: number): [number, number, number] {
  const t = Math.min(Math.max((v - 20) / 100, 0), 1);
  return [Math.round(40 + t * 215), Math.round(220 - t * 180), Math.round(120 - t * 100)];
}

export default function DeckMapImpl({ nodes, edges = [], colorBy = "community", height = 600 }: Props) {
  const [hovered, setHovered] = useState<NodeFeature | null>(null);

  const initialView = useMemo(() => ({
    longitude: 80,
    latitude: 22,
    zoom: 4.0,
    pitch: 35,
    bearing: 0,
  }), []);

  const layers = useMemo(() => {
    const nodeMap = new Map(nodes.map(n => [n.district_id, n]));

    const lineLayer = new LineLayer({
      id: "edges",
      data: edges.filter(e => nodeMap.has(e.source_id) && nodeMap.has(e.target_id)),
      getSourcePosition: (e: EdgeFeature) => {
        const n = nodeMap.get(e.source_id)!;
        return [n.lon, n.lat];
      },
      getTargetPosition: (e: EdgeFeature) => {
        const n = nodeMap.get(e.target_id)!;
        return [n.lon, n.lat];
      },
      getColor: [148, 163, 184, 60],
      getWidth: 1,
      pickable: false,
    });

    const nodeLayer = new ScatterplotLayer({
      id: "nodes",
      data: nodes,
      getPosition: (d: NodeFeature) => [d.lon, d.lat],
      getRadius: (d: NodeFeature) => 8000 + (d.betweenness_centrality || 0) * 80000,
      radiusMinPixels: 4,
      radiusMaxPixels: 30,
      getFillColor: (d: NodeFeature) => {
        if (colorBy === "community") {
          const c = d.community ?? 0;
          return [...(COMMUNITY_COLORS[c] || [148, 163, 184]), 220] as any;
        }
        if (colorBy === "pm25_mean") {
          return [...pollutionColor(d.pm25_mean || 50), 220] as any;
        }
        return [...pollutionColor((d.resp_rate_mean || 50) * 0.5), 220] as any;
      },
      getLineColor: [255, 255, 255, 200],
      lineWidthMinPixels: 0.5,
      stroked: true,
      pickable: true,
      onHover: (info: any) => setHovered(info.object || null),
    });

    return [lineLayer, nodeLayer];
  }, [nodes, edges, colorBy]);

  return (
    <div className="relative rounded-xl overflow-hidden border border-border/60 bg-gradient-to-br from-slate-950 to-slate-900" style={{ height }}>
      <DeckGL
        initialViewState={initialView}
        controller={true}
        layers={layers}
        style={{ width: "100%", height: "100%" }}
      />
      {hovered && (
        <div className="absolute top-3 left-3 bg-card/95 backdrop-blur-sm border border-border rounded-lg px-3 py-2 shadow-2xl pointer-events-none">
          <div className="font-semibold text-sm">{hovered.district_name}</div>
          <div className="text-xs text-muted-foreground">{hovered.state}</div>
          {hovered.pm25_mean !== undefined && (
            <div className="text-xs mt-1">PM2.5: <span className="font-mono text-rose-300">{hovered.pm25_mean?.toFixed(1)}</span></div>
          )}
          {hovered.community !== undefined && (
            <div className="text-xs">Zone {hovered.community}</div>
          )}
        </div>
      )}
      <div className="absolute bottom-3 right-3 text-[10px] text-muted-foreground/80">
        deck.gl
      </div>
    </div>
  );
}
