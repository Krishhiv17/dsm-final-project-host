"use client";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { PlotlyChart } from "@/components/plot";
import { InsightBox } from "@/components/insight-box";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { getSeasonality } from "@/lib/api";

export default function SeasonalityPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { getSeasonality().then(setData).catch(console.error); }, []);

  return (
    <div className="space-y-8">
      <PageHeader badge="Seasonality" title="The Annual Pollution Trend"
        subtitle="National PM2.5 has remained stubbornly flat at ~59 µg/m³ from 2013–2023. Despite GRAP, BS-VI vehicles, odd-even schemes, and crop-burning bans, the trend line barely moves." />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Pollution Trend 2013–2023</CardTitle>
            <CardDescription>Annual mean across all districts. No sustained improvement visible over the decade.</CardDescription>
          </CardHeader>
          <CardContent>
            {data?.pollution && (
              <PlotlyChart
                height={420}
                data={[
                  { type: "scatter", mode: "lines+markers", name: "PM2.5",
                    x: data.pollution.map((d: any) => d.year),
                    y: data.pollution.map((d: any) => d.pm25),
                    line: { width: 3, color: "#f87171" }, marker: { size: 9 } },
                  { type: "scatter", mode: "lines+markers", name: "PM10",
                    x: data.pollution.map((d: any) => d.year),
                    y: data.pollution.map((d: any) => d.pm10),
                    line: { width: 3, color: "#fbbf24" }, marker: { size: 9 } },
                  { type: "scatter", mode: "lines+markers", name: "NO₂",
                    x: data.pollution.map((d: any) => d.year),
                    y: data.pollution.map((d: any) => d.no2),
                    line: { width: 3, color: "#a78bfa" }, marker: { size: 9 } },
                  { type: "scatter", mode: "lines+markers", name: "SO₂",
                    x: data.pollution.map((d: any) => d.year),
                    y: data.pollution.map((d: any) => d.so2),
                    line: { width: 3, color: "#22d3ee" }, marker: { size: 9 } },
                ]}
                layout={{
                  xaxis: { title: { text: "Year" }, dtick: 1 },
                  yaxis: { title: { text: "Annual mean concentration (µg/m³)" } },
                  legend: { orientation: "h", y: -0.2 },
                }}
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Health Burden Trend 2013–2023</CardTitle>
            <CardDescription>Annual mean cases per district. Respiratory burden grows as pollution stays flat.</CardDescription>
          </CardHeader>
          <CardContent>
            {data?.health && (
              <PlotlyChart
                height={420}
                data={[
                  { type: "scatter", mode: "lines+markers", name: "Respiratory",
                    x: data.health.map((d: any) => d.year),
                    y: data.health.map((d: any) => d.respiratory_cases),
                    line: { width: 3, color: "#38bdf8" }, marker: { size: 9 },
                    fill: "tozeroy", fillcolor: "rgba(56,189,248,0.08)" },
                ]}
                layout={{
                  xaxis: { title: { text: "Year" }, dtick: 1 },
                  yaxis: { title: { text: "Average cases / district" } },
                  legend: { orientation: "h", y: -0.2 },
                }}
              />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <InsightBox variant="critical" title="Six years of policy, zero movement">
          National PM2.5 in 2018: ~59 µg/m³. In 2023: ~59 µg/m³. BS-VI fuel standards, GRAP escalation frameworks, odd-even vehicle schemes, and paddy-stubble bans have not moved the national average. The levers being pulled are not the ones that matter at scale.
        </InsightBox>
        <InsightBox variant="info" title="The data is annual district averages">
          The CPCB/NDAP dataset provides annual summary statistics per district (250,008 records across 233 districts). Each point on these charts is one year&apos;s mean. District-level variation is large — northern states run 2–5× southern baselines even within the same year.
        </InsightBox>
      </div>
    </div>
  );
}
