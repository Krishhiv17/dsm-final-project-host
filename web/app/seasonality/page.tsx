"use client";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { PlotlyChart } from "@/components/plot";
import { InsightBox } from "@/components/insight-box";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { getSeasonality } from "@/lib/api";

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

export default function SeasonalityPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { getSeasonality().then(setData).catch(console.error); }, []);

  return (
    <div className="space-y-8">
      <PageHeader badge="Seasonality" title="The Winter Pollution Cycle"
        subtitle="One of the strongest patterns in this dataset: PM2.5 levels in November-February are 2-3× higher than the monsoon trough. Health outcomes track this rhythm with a short lag." />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Pollutant Seasonality</CardTitle>
            <CardDescription>Monthly mean across all districts — averaged over 2018-2023.</CardDescription>
          </CardHeader>
          <CardContent>
            {data?.pollution && (
              <PlotlyChart
                height={420}
                data={[
                  { type: "scatter", mode: "lines+markers", name: "PM2.5",
                    x: data.pollution.map((d: any) => MONTHS[d.month - 1]),
                    y: data.pollution.map((d: any) => d.pm25),
                    line: { width: 3, color: "#f87171" }, marker: { size: 8 } },
                  { type: "scatter", mode: "lines+markers", name: "PM10",
                    x: data.pollution.map((d: any) => MONTHS[d.month - 1]),
                    y: data.pollution.map((d: any) => d.pm10),
                    line: { width: 3, color: "#fbbf24" }, marker: { size: 8 } },
                  { type: "scatter", mode: "lines+markers", name: "NO₂",
                    x: data.pollution.map((d: any) => MONTHS[d.month - 1]),
                    y: data.pollution.map((d: any) => d.no2),
                    line: { width: 3, color: "#a78bfa" }, marker: { size: 8 } },
                  { type: "scatter", mode: "lines+markers", name: "SO₂",
                    x: data.pollution.map((d: any) => MONTHS[d.month - 1]),
                    y: data.pollution.map((d: any) => d.so2),
                    line: { width: 3, color: "#22d3ee" }, marker: { size: 8 } },
                ]}
                layout={{
                  yaxis: { title: { text: "Concentration (µg/m³)" } },
                  legend: { orientation: "h", y: -0.2 },
                }}
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Health Seasonality</CardTitle>
            <CardDescription>Monthly mean cases per district. Note diarrhoea&apos;s opposite phase.</CardDescription>
          </CardHeader>
          <CardContent>
            {data?.health && (
              <PlotlyChart
                height={420}
                data={[
                  { type: "scatter", mode: "lines+markers", name: "Respiratory",
                    x: data.health.map((d: any) => MONTHS[d.month - 1]),
                    y: data.health.map((d: any) => d.respiratory_cases),
                    line: { width: 3, color: "#38bdf8" }, marker: { size: 8 },
                    fill: "tozeroy", fillcolor: "rgba(56,189,248,0.08)" },
                  { type: "scatter", mode: "lines+markers", name: "Cardiovascular",
                    x: data.health.map((d: any) => MONTHS[d.month - 1]),
                    y: data.health.map((d: any) => d.cardiovascular_cases),
                    line: { width: 3, color: "#f472b6" }, marker: { size: 8 } },
                  { type: "scatter", mode: "lines+markers", name: "Diarrhoea",
                    x: data.health.map((d: any) => MONTHS[d.month - 1]),
                    y: data.health.map((d: any) => d.diarrhoea_cases),
                    line: { width: 3, color: "#34d399" }, marker: { size: 8 } },
                ]}
                layout={{
                  yaxis: { title: { text: "Average cases / district" } },
                  legend: { orientation: "h", y: -0.2 },
                }}
              />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <InsightBox variant="critical" title="Winter inversions are the mechanism">
          Cold air sinking under warmer aloft layers traps pollutants near ground level. Combined with crop-residue burning in Punjab/Haryana and reduced wind dispersion, this produces the November-February peak that&apos;s visible in <b>every</b> northern district.
        </InsightBox>
        <InsightBox variant="info" title="Diarrhoea runs opposite">
          Notice how diarrhoea cases rise in monsoon (Jun-Sep) — the same months when air pollution drops. This isn&apos;t pollution-driven; it&apos;s waterborne. A useful sanity check that respiratory ≠ diarrhoea ≠ random.
        </InsightBox>
      </div>
    </div>
  );
}
