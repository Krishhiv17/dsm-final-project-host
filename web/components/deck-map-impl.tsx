"use client";
import { useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import { ScatterplotLayer, LineLayer, ArcLayer } from "@deck.gl/layers";
import MapLibre from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";

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

interface PredictedEdge {
  district_a: number;
  district_b: number;
  combined_score?: number;
  jaccard?: number;
  adamic_adar?: number;
  name_a?: string;
  name_b?: string;
}

interface Props {
  nodes: NodeFeature[];
  edges?: EdgeFeature[];
  predictedEdges?: PredictedEdge[];
  colorBy?: "community" | "pm25_mean" | "resp_rate_mean";
  height?: number;
  showBaseEdges?: boolean;
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

// Free CARTO dark basemap — shows country/state outlines (incl. India)
const BASE_MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

function pollutionColor(v: number): [number, number, number] {
  const t = Math.min(Math.max((v - 20) / 100, 0), 1);
  return [Math.round(40 + t * 215), Math.round(220 - t * 180), Math.round(120 - t * 100)];
}

// Score → blue/cyan → yellow → red gradient (visible on dark map at all scores)
function scoreColor(score: number, min: number, max: number): [number, number, number] {
  const t = max > min ? (score - min) / (max - min) : 0.5;
  // cyan (low) → yellow (mid) → red (high)
  if (t < 0.5) {
    const k = t * 2;
    return [Math.round(56 + k * 195), Math.round(189 + k * 2), Math.round(248 - k * 212)];
  }
  const k = (t - 0.5) * 2;
  return [Math.round(251 - k * 3), Math.round(191 - k * 78), Math.round(36 - k * 0)];
}

export default function DeckMapImpl({
  nodes,
  edges = [],
  predictedEdges = [],
  colorBy = "community",
  height = 600,
  showBaseEdges = true,
}: Props) {
  const [hovered, setHovered] = useState<NodeFeature | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<PredictedEdge | null>(null);

  const initialView = useMemo(() => ({
    longitude: 80,
    latitude: 22,
    zoom: 4.0,
    pitch: 30,
    bearing: 0,
  }), []);

  const layers = useMemo(() => {
    const nodeMap = new Map(nodes.map(n => [n.district_id, n]));
    const out: any[] = [];

    if (showBaseEdges && edges.length > 0) {
      out.push(new LineLayer({
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
      }));
    }

    if (predictedEdges.length > 0) {
      const valid = predictedEdges.filter(
        e => nodeMap.has(e.district_a) && nodeMap.has(e.district_b)
      );
      const scores = valid.map(e => e.combined_score ?? e.adamic_adar ?? 0);
      const sMin = Math.min(...scores);
      const sMax = Math.max(...scores);

      out.push(new ArcLayer({
        id: "predicted",
        data: valid,
        getSourcePosition: (e: PredictedEdge) => {
          const n = nodeMap.get(e.district_a)!;
          return [n.lon, n.lat];
        },
        getTargetPosition: (e: PredictedEdge) => {
          const n = nodeMap.get(e.district_b)!;
          return [n.lon, n.lat];
        },
        getSourceColor: (e: PredictedEdge) => {
          const s = e.combined_score ?? e.adamic_adar ?? 0;
          const t = sMax > sMin ? (s - sMin) / (sMax - sMin) : 0.5;
          const opacity = Math.round(120 + t * 120);
          return [...scoreColor(s, sMin, sMax), opacity] as any;
        },
        getTargetColor: (e: PredictedEdge) => {
          const s = e.combined_score ?? e.adamic_adar ?? 0;
          const t = sMax > sMin ? (s - sMin) / (sMax - sMin) : 0.5;
          const opacity = Math.round(120 + t * 120);
          return [...scoreColor(s, sMin, sMax), opacity] as any;
        },
        getWidth: (e: PredictedEdge) => {
          const s = e.combined_score ?? e.adamic_adar ?? 0;
          const t = sMax > sMin ? (s - sMin) / (sMax - sMin) : 0.5;
          return 1.5 + t * 4;
        },
        getHeight: 0.5,
        greatCircle: false,
        pickable: true,
        onHover: (info: any) => setHoveredEdge(info.object || null),
      }));
    }

    out.push(new ScatterplotLayer({
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
    }));

    return out;
  }, [nodes, edges, predictedEdges, colorBy, showBaseEdges]);

  return (
    <div
      className="relative rounded-xl overflow-hidden border border-border/60"
      style={{ height }}
    >
      <DeckGL
        initialViewState={initialView}
        controller={true}
        layers={layers}
        style={{ width: "100%", height: "100%" }}
      >
        <MapLibre reuseMaps mapStyle={BASE_MAP_STYLE} attributionControl={false} />
      </DeckGL>

      {hovered && (
        <div className="absolute top-3 left-3 bg-card/95 backdrop-blur-sm border border-border rounded-lg px-3 py-2 shadow-2xl pointer-events-none z-10">
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

      {hoveredEdge && (
        <div className="absolute top-3 right-3 bg-card/95 backdrop-blur-sm border border-border rounded-lg px-3 py-2 shadow-2xl pointer-events-none z-10">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">Predicted link</div>
          <div className="font-semibold text-sm">
            {hoveredEdge.name_a ?? hoveredEdge.district_a} ↔ {hoveredEdge.name_b ?? hoveredEdge.district_b}
          </div>
          {hoveredEdge.combined_score !== undefined && (
            <div className="text-xs mt-1">Score: <span className="font-mono text-amber-300">{hoveredEdge.combined_score.toFixed(3)}</span></div>
          )}
        </div>
      )}

      <div className="absolute bottom-3 right-3 text-[10px] text-muted-foreground/80 z-10">
        deck.gl · CARTO
      </div>
    </div>
  );
}
