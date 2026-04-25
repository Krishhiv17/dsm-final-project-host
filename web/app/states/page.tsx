"use client";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { PlotlyChart } from "@/components/plot";
import { InsightBox } from "@/components/insight-box";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getStates } from "@/lib/api";
import { formatNumber } from "@/lib/utils";

export default function StatesPage() {
  const [states, setStates] = useState<any[]>([]);
  useEffect(() => { getStates().then(setStates).catch(console.error); }, []);

  return (
    <div className="space-y-8">
      <PageHeader badge="State Comparison" title="State-level Pollution & Health"
        subtitle="A side-by-side ranking of every state. The pattern is clear: northern states carry both the heaviest pollution and the heaviest disease burden." />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>PM2.5 by State</CardTitle>
            <CardDescription>Sorted high → low. Red dashed line = NAAQS annual standard (40 µg/m³).</CardDescription>
          </CardHeader>
          <CardContent>
            {states.length > 0 && (
              <PlotlyChart
                height={520}
                data={[{
                  type: "bar", orientation: "h",
                  x: [...states].reverse().map(s => s.avg_pm25),
                  y: [...states].reverse().map(s => s.state),
                  marker: {
                    color: [...states].reverse().map(s => s.avg_pm25),
                    colorscale: [[0, "#34d399"], [0.5, "#fbbf24"], [1, "#f87171"]],
                  },
                  hovertemplate: "<b>%{y}</b><br>PM2.5: %{x:.1f} µg/m³<extra></extra>",
                }]}
                layout={{
                  xaxis: { title: { text: "PM2.5 (µg/m³)" } },
                  margin: { l: 130, r: 30, t: 20, b: 50 },
                  shapes: [{ type: "line", x0: 40, x1: 40, y0: -0.5, y1: states.length - 0.5,
                    line: { color: "#f87171", dash: "dash", width: 2 } }],
                }}
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Pollution vs Respiratory Burden</CardTitle>
            <CardDescription>Each bubble is a state. Larger bubble = more districts. Up-and-right = double trouble.</CardDescription>
          </CardHeader>
          <CardContent>
            {states.length > 0 && (
              <PlotlyChart
                height={520}
                data={[{
                  type: "scatter", mode: "markers+text",
                  x: states.map(s => s.avg_pm25),
                  y: states.map(s => s.total_respiratory),
                  text: states.map(s => s.state),
                  textposition: "top center", textfont: { size: 10, color: "#cbd5e1" },
                  marker: {
                    size: states.map(s => Math.sqrt(s.num_districts) * 8 + 6),
                    color: states.map(s => s.avg_pm25),
                    colorscale: [[0, "#34d399"], [0.5, "#fbbf24"], [1, "#f87171"]],
                    showscale: true, colorbar: { title: { text: "PM2.5" } },
                    line: { color: "rgba(255,255,255,0.4)", width: 1 },
                  },
                  hovertemplate: "<b>%{text}</b><br>PM2.5: %{x:.1f}<br>Resp cases: %{y:,}<extra></extra>",
                }]}
                layout={{
                  xaxis: { title: { text: "Avg PM2.5 (µg/m³)" } },
                  yaxis: { title: { text: "Total respiratory cases" } },
                  margin: { l: 70, r: 30, t: 20, b: 50 },
                }}
              />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>State Table</CardTitle>
          <CardDescription>Full breakdown — pollutants, disease totals, district counts.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs uppercase text-muted-foreground border-b border-border/60">
                <tr>
                  <th className="text-left py-2 px-3">State</th>
                  <th className="text-right py-2 px-3">Districts</th>
                  <th className="text-right py-2 px-3">PM2.5</th>
                  <th className="text-right py-2 px-3">PM10</th>
                  <th className="text-right py-2 px-3">NO₂</th>
                  <th className="text-right py-2 px-3">SO₂</th>
                  <th className="text-right py-2 px-3">Respiratory</th>
                  <th className="text-right py-2 px-3">Cardio</th>
                  <th className="text-right py-2 px-3">Diarrhoea</th>
                </tr>
              </thead>
              <tbody>
                {states.map((s, i) => {
                  const tone =
                    s.avg_pm25 > 100 ? "critical" :
                    s.avg_pm25 > 60 ? "warning" :
                    s.avg_pm25 > 40 ? "info" : "success";
                  return (
                    <tr key={i} className="border-b border-border/30 hover:bg-accent/30 transition-colors">
                      <td className="py-2 px-3 font-medium">{s.state}</td>
                      <td className="py-2 px-3 text-right">{s.num_districts}</td>
                      <td className="py-2 px-3 text-right">
                        <Badge variant={tone}>{s.avg_pm25?.toFixed(1)}</Badge>
                      </td>
                      <td className="py-2 px-3 text-right text-muted-foreground">{s.avg_pm10?.toFixed(1)}</td>
                      <td className="py-2 px-3 text-right text-muted-foreground">{s.avg_no2?.toFixed(1)}</td>
                      <td className="py-2 px-3 text-right text-muted-foreground">{s.avg_so2?.toFixed(1)}</td>
                      <td className="py-2 px-3 text-right">{formatNumber(s.total_respiratory)}</td>
                      <td className="py-2 px-3 text-right">{formatNumber(s.total_cardiovascular)}</td>
                      <td className="py-2 px-3 text-right">{formatNumber(s.total_diarrhoea)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <InsightBox variant="critical" title="Northern plain dominates">
        Delhi, UP, Bihar, Haryana and Punjab cluster at the top — all five states share the Indo-Gangetic geography that traps pollutants every winter. The same five also report the highest respiratory case totals.
      </InsightBox>
    </div>
  );
}
