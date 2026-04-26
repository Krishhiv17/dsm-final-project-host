"use client";
import { useEffect, useState } from "react";
import { Wind, Heart, MapPin, Activity, TrendingUp, AlertTriangle } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { KPICard } from "@/components/kpi-card";
import { InsightBox } from "@/components/insight-box";
import { PlotlyChart } from "@/components/plot";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { getKPIs, getStates, getSeasonality } from "@/lib/api";
import { formatNumber } from "@/lib/utils";

export default function OverviewPage() {
  const [kpis, setKpis] = useState<any>(null);
  const [states, setStates] = useState<any[]>([]);
  const [season, setSeason] = useState<any>(null);

  useEffect(() => {
    Promise.all([getKPIs(), getStates(), getSeasonality()])
      .then(([k, s, se]) => { setKpis(k); setStates(s); setSeason(se); })
      .catch(console.error);
  }, []);

  const top10 = states.slice(0, 10);

  return (
    <div className="space-y-8">
      <PageHeader
        badge="Overview"
        title="Air Quality & Public Health"
        subtitle="Six years of district-level data across 15 Indian states. The story begins with what the air looks like — and who is breathing it."
      />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <KPICard label="Avg PM2.5" tone="warning" icon={<Wind className="w-4 h-4" />}
          value={kpis ? `${kpis.avg_pm25}` : "—"}
          delta="µg/m³ · 6× WHO guideline" />
        <KPICard label="Peak PM2.5" tone="critical" icon={<AlertTriangle className="w-4 h-4" />}
          value={kpis ? `${kpis.max_pm25}` : "—"}
          delta="µg/m³ · winter spike" />
        <KPICard label="Respiratory Cases" tone="critical" icon={<Activity className="w-4 h-4" />}
          value={kpis ? formatNumber(kpis.total_respiratory) : "—"}
          delta="total reported · 2018–2023" />
        <KPICard label="Cardiovascular" tone="warning" icon={<Heart className="w-4 h-4" />}
          value={kpis ? formatNumber(kpis.total_cardiovascular) : "—"}
          delta="total reported" />
        <KPICard label="Districts" tone="info" icon={<MapPin className="w-4 h-4" />}
          value={kpis ? kpis.num_districts : "—"}
          delta={kpis ? `${kpis.num_states} states` : ""} />
        <KPICard label="Time Span" tone="success" icon={<TrendingUp className="w-4 h-4" />}
          value={kpis ? `${kpis.date_range_start?.slice(0, 4)}–${kpis.date_range_end?.slice(0, 4)}` : "—"}
          delta="daily AQ + monthly health" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Top 10 States by Average PM2.5</CardTitle>
            <CardDescription>The pollution gradient runs north-to-south. Delhi and the Indo-Gangetic plain dominate.</CardDescription>
          </CardHeader>
          <CardContent>
            {top10.length > 0 && (
              <PlotlyChart
                height={420}
                data={[{
                  type: "bar",
                  orientation: "h",
                  x: [...top10].reverse().map(s => s.avg_pm25),
                  y: [...top10].reverse().map(s => s.state),
                  marker: {
                    color: [...top10].reverse().map(s => s.avg_pm25),
                    colorscale: [[0, "#34d399"], [0.5, "#fbbf24"], [1, "#f87171"]],
                  },
                  hovertemplate: "<b>%{y}</b><br>PM2.5: %{x:.1f} µg/m³<extra></extra>",
                }]}
                layout={{
                  xaxis: { title: { text: "PM2.5 (µg/m³)" } },
                  margin: { l: 140, r: 30, t: 20, b: 50 },
                  shapes: [{
                    type: "line", x0: 40, x1: 40, y0: -0.5, y1: top10.length - 0.5,
                    line: { color: "#f87171", dash: "dash", width: 2 },
                  }],
                  annotations: [{
                    x: 40, y: top10.length - 0.5, text: "NAAQS limit",
                    showarrow: false, font: { color: "#fda4af", size: 10 },
                    xanchor: "left", yanchor: "bottom",
                  }],
                }}
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quick Read</CardTitle>
            <CardDescription>What jumps out from the headline numbers</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <InsightBox variant="critical" title="Pollution is structural">
              The national average PM2.5 sits at <b>{kpis?.avg_pm25} µg/m³</b> — over <b>6× the WHO guideline</b> of 5 µg/m³ and above India&apos;s own NAAQS standard of 40.
            </InsightBox>
            <InsightBox variant="warning" title="Disease burden is enormous">
              <b>{kpis ? formatNumber(kpis.total_respiratory) : "—"}</b> respiratory cases reported across the panel — concentrated in winter months and northern states.
            </InsightBox>
            <InsightBox variant="info" title="Geography matters">
              {kpis?.num_districts} districts across {kpis?.num_states} states cover the full range from Kerala (~25 µg/m³) to Delhi (~150 µg/m³).
            </InsightBox>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Year-Over-Year Trend</CardTitle>
          <CardDescription>
            Annual mean across all districts, 2013–2023. National PM2.5 has remained flat at ~59 µg/m³ despite GRAP, BS-VI, and crop-burning bans.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {season && season.pollution.length > 0 && (
            <PlotlyChart
              height={380}
              data={[
                {
                  type: "scatter", mode: "lines+markers",
                  x: season.pollution.map((d: any) => d.year),
                  y: season.pollution.map((d: any) => d.pm25),
                  name: "PM2.5", line: { width: 3, color: "#f87171" },
                  marker: { size: 8 },
                },
                {
                  type: "scatter", mode: "lines+markers",
                  x: season.pollution.map((d: any) => d.year),
                  y: season.pollution.map((d: any) => d.pm10),
                  name: "PM10", line: { width: 3, color: "#fbbf24" },
                  marker: { size: 8 },
                },
                {
                  type: "scatter", mode: "lines+markers", yaxis: "y2",
                  x: season.health.map((d: any) => d.year),
                  y: season.health.map((d: any) => d.respiratory_cases),
                  name: "Respiratory cases", line: { width: 3, color: "#38bdf8", dash: "dot" },
                  marker: { size: 8 },
                },
              ]}
              layout={{
                xaxis: { title: { text: "Year" }, dtick: 1 },
                yaxis:  { title: { text: "Pollutant (µg/m³)" } },
                yaxis2: { title: { text: "Avg respiratory cases / district" }, overlaying: "y", side: "right", showgrid: false },
                legend: { orientation: "h", y: -0.2 },
              }}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
