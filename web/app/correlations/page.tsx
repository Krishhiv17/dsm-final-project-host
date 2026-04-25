"use client";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { PlotlyChart } from "@/components/plot";
import { InsightBox } from "@/components/insight-box";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { getScatter, getHeatmap, getScatter3D } from "@/lib/api";

const ALL_VARS = [
  { value: "pm25",                 label: "PM2.5"  },
  { value: "pm10",                 label: "PM10"   },
  { value: "no2",                  label: "NO₂"    },
  { value: "so2",                  label: "SO₂"    },
  { value: "urban_percentage",     label: "Urban %" },
  { value: "literacy_rate",        label: "Literacy %" },
  { value: "population",           label: "Population" },
  { value: "respiratory_cases",    label: "Respiratory cases"    },
  { value: "cardiovascular_cases", label: "Cardiovascular cases" },
  { value: "diarrhoea_cases",      label: "Diarrhoea cases"      },
];
const X_VARS = ALL_VARS.filter(v => !["respiratory_cases","cardiovascular_cases","diarrhoea_cases"].includes(v.value));
const Y_VARS = ALL_VARS.filter(v => ["respiratory_cases","cardiovascular_cases","diarrhoea_cases"].includes(v.value));

const STATE_COLORS = [
  "#38bdf8", "#34d399", "#fbbf24", "#f87171", "#a78bfa",
  "#f472b6", "#22d3ee", "#facc15", "#fb923c", "#4ade80",
  "#60a5fa", "#c084fc", "#fb7185", "#2dd4bf", "#a3e635",
];

export default function CorrelationsPage() {
  const [x, setX] = useState("pm25");
  const [y, setY] = useState("respiratory_cases");
  const [scatter, setScatter] = useState<any>(null);
  const [heatmap, setHeatmap] = useState<any>(null);

  // 3D state (independent axes)
  const [x3, setX3] = useState("pm25");
  const [y3, setY3] = useState("pm10");
  const [z3, setZ3] = useState("respiratory_cases");
  const [scatter3, setScatter3] = useState<any>(null);

  useEffect(() => { getScatter(x, y).then(setScatter).catch(console.error); }, [x, y]);
  useEffect(() => { getHeatmap().then(setHeatmap).catch(console.error); }, []);
  useEffect(() => { getScatter3D(x3, y3, z3).then(setScatter3).catch(console.error); }, [x3, y3, z3]);

  const r = scatter?.stats?.pearson_r ?? 0;
  const tone = Math.abs(r) > 0.4 ? "critical" : Math.abs(r) > 0.2 ? "warning" : "info";
  const labelOf = (v: string) => ALL_VARS.find(a => a.value === v)?.label || v;

  // Group 3D points by state for coloured traces
  const groupedByState = (() => {
    if (!scatter3?.data) return [];
    const m: Record<string, any[]> = {};
    for (const d of scatter3.data) (m[d.state] ||= []).push(d);
    return Object.entries(m).sort();
  })();

  return (
    <div className="space-y-8">
      <PageHeader badge="Correlations" title="What predicts what?"
        subtitle="The single most important question of this project: do pollutants actually correlate with disease at the district level? Explore in 2D, 3D, or via the full correlation matrix." />

      <Tabs defaultValue="2d">
        <TabsList className="mb-4">
          <TabsTrigger value="2d">2D Scatter</TabsTrigger>
          <TabsTrigger value="3d">3D Scatter</TabsTrigger>
          <TabsTrigger value="matrix">Correlation Matrix</TabsTrigger>
        </TabsList>

        <TabsContent value="2d" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Pick variables</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">X axis</label>
                  <Select value={x} onValueChange={setX}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {X_VARS.map(v => <SelectItem key={v.value} value={v.value}>{v.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">Y axis</label>
                  <Select value={y} onValueChange={setY}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {Y_VARS.map(v => <SelectItem key={v.value} value={v.value}>{v.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <CardTitle>Scatter plot</CardTitle>
                  <CardDescription>Each point is one district-month observation.</CardDescription>
                </div>
                {scatter && (
                  <div className="flex gap-2">
                    <Badge variant={tone}>r = {scatter.stats.pearson_r}</Badge>
                    <Badge variant="outline">p ≈ {scatter.stats.p_value < 1e-4 ? "0" : scatter.stats.p_value.toExponential(2)}</Badge>
                    <Badge variant="secondary">n = {scatter.stats.n}</Badge>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {scatter && scatter.data.length > 0 && (
                <PlotlyChart
                  height={500}
                  data={[{
                    type: "scatter", mode: "markers",
                    x: scatter.data.map((d: any) => d.x),
                    y: scatter.data.map((d: any) => d.y),
                    text: scatter.data.map((d: any) => d.state),
                    marker: { size: 4, color: "#38bdf8", opacity: 0.45,
                      line: { color: "rgba(56,189,248,0.4)", width: 0.5 } },
                    hovertemplate: "%{text}<br>x=%{x:.1f}<br>y=%{y:.0f}<extra></extra>",
                  }]}
                  layout={{
                    xaxis: { title: { text: labelOf(x) } },
                    yaxis: { title: { text: labelOf(y) } },
                  }}
                />
              )}
            </CardContent>
          </Card>

          <InsightBox variant={tone === "critical" ? "critical" : "info"} title="What this means">
            {Math.abs(r) > 0.3 ? (
              <>A correlation of <b>r = {r.toFixed(3)}</b> at <b>n = {scatter?.stats.n}</b> is highly statistically significant (p ≈ 0). This is not noise — it is a real, reproducible association between {labelOf(x)} and {labelOf(y)} across Indian districts.</>
            ) : (
              <>Correlation here is modest (r = {r.toFixed(3)}). The signal is weaker — try PM2.5 vs respiratory cases for the strongest pollution-health link in this dataset.</>
            )}
          </InsightBox>
        </TabsContent>

        <TabsContent value="3d" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Pick three axes</CardTitle>
              <CardDescription>Drag to rotate · scroll to zoom · double-click to reset.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <AxisSelect label="X axis" value={x3} onChange={setX3} options={ALL_VARS} />
                <AxisSelect label="Y axis" value={y3} onChange={setY3} options={ALL_VARS} />
                <AxisSelect label="Z axis" value={z3} onChange={setZ3} options={ALL_VARS} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <CardTitle>3D Scatter — {labelOf(x3)} × {labelOf(y3)} × {labelOf(z3)}</CardTitle>
                  <CardDescription>Coloured by state. Each point is a district-month.</CardDescription>
                </div>
                {scatter3 && <Badge variant="secondary">n = {scatter3.stats?.n}</Badge>}
              </div>
            </CardHeader>
            <CardContent>
              {scatter3 && scatter3.data.length > 0 ? (
                <PlotlyChart
                  height={620}
                  data={groupedByState.map(([state, rows], i) => ({
                    type: "scatter3d", mode: "markers", name: state,
                    x: rows.map((d: any) => d.x),
                    y: rows.map((d: any) => d.y),
                    z: rows.map((d: any) => d.z),
                    text: rows.map(() => state),
                    marker: {
                      size: 3,
                      color: STATE_COLORS[i % STATE_COLORS.length],
                      opacity: 0.75,
                      line: { color: "rgba(255,255,255,0.15)", width: 0.5 },
                    },
                    hovertemplate: "<b>%{text}</b><br>" +
                      labelOf(x3) + ": %{x:.2f}<br>" +
                      labelOf(y3) + ": %{y:.2f}<br>" +
                      labelOf(z3) + ": %{z:.2f}<extra></extra>",
                  }))}
                  layout={{
                    scene: {
                      xaxis: { title: { text: labelOf(x3) }, gridcolor: "rgba(148,163,184,0.15)",
                        backgroundcolor: "rgba(15,23,42,0.5)", showbackground: true },
                      yaxis: { title: { text: labelOf(y3) }, gridcolor: "rgba(148,163,184,0.15)",
                        backgroundcolor: "rgba(15,23,42,0.5)", showbackground: true },
                      zaxis: { title: { text: labelOf(z3) }, gridcolor: "rgba(148,163,184,0.15)",
                        backgroundcolor: "rgba(15,23,42,0.5)", showbackground: true },
                      camera: { eye: { x: 1.4, y: 1.4, z: 0.9 } },
                    },
                    margin: { l: 0, r: 0, t: 0, b: 0 },
                    legend: { font: { size: 10 } },
                  }}
                />
              ) : (
                <div className="text-sm text-muted-foreground py-12 text-center">Loading…</div>
              )}
            </CardContent>
          </Card>

          <InsightBox variant="info" title="Reading a 3D cloud">
            Look for clustering by colour (state) and direction. If states form parallel sheets, geographic factors matter beyond the variables on screen. If the cloud aligns along a single direction, the three variables are essentially measuring one underlying construct.
          </InsightBox>
        </TabsContent>

        <TabsContent value="matrix">
          <Card>
            <CardHeader>
              <CardTitle>Full Correlation Matrix</CardTitle>
              <CardDescription>All pollutants × health × demographics — every pairwise Pearson r.</CardDescription>
            </CardHeader>
            <CardContent>
              {heatmap && (
                <PlotlyChart
                  height={620}
                  data={[{
                    type: "heatmap",
                    z: heatmap.matrix, x: heatmap.vars, y: heatmap.vars,
                    colorscale: [[0, "#1e3a8a"], [0.5, "#0f172a"], [1, "#dc2626"]],
                    zmid: 0, zmin: -1, zmax: 1,
                    hovertemplate: "%{x} ↔ %{y}<br>r = %{z:.2f}<extra></extra>",
                    text: heatmap.matrix.map((row: number[]) => row.map(v => v.toFixed(2))),
                    texttemplate: "%{text}", textfont: { size: 11 },
                  }]}
                  layout={{
                    margin: { l: 180, r: 30, t: 20, b: 140 },
                    xaxis: { tickangle: -40 },
                  }}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function AxisSelect({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div>
      <label className="text-xs text-muted-foreground mb-1.5 block">{label}</label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger><SelectValue /></SelectTrigger>
        <SelectContent>
          {options.map(o => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  );
}
