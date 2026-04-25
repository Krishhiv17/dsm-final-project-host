"use client";
import { useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { PlotlyChart } from "@/components/plot";
import { InsightBox } from "@/components/insight-box";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { getDistricts, getTimeseries } from "@/lib/api";

const POLLUTANTS = [
  { value: "pm25", label: "PM2.5" },
  { value: "pm10", label: "PM10"  },
  { value: "no2",  label: "NO₂"   },
  { value: "so2",  label: "SO₂"   },
  { value: "aqi",  label: "AQI"   },
];
const AGG = [
  { value: "monthly", label: "Monthly"  },
  { value: "weekly",  label: "Weekly"   },
  { value: "daily",   label: "Daily"    },
];

export default function TimeseriesPage() {
  const [districts, setDistricts] = useState<any[]>([]);
  const [districtId, setDistrictId] = useState<string>("");
  const [pollutant, setPollutant] = useState("pm25");
  const [agg, setAgg] = useState("monthly");
  const [series, setSeries] = useState<any[]>([]);

  useEffect(() => {
    getDistricts().then(d => {
      setDistricts(d);
      if (d.length > 0) setDistrictId(String(d[0].district_id));
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (!districtId) return;
    getTimeseries(Number(districtId), pollutant, agg).then(setSeries).catch(console.error);
  }, [districtId, pollutant, agg]);

  const meta = useMemo(() => districts.find(d => String(d.district_id) === districtId), [districts, districtId]);

  // Group by state for the dropdown
  const grouped = useMemo(() => {
    const m: Record<string, any[]> = {};
    districts.forEach(d => { (m[d.state] ||= []).push(d); });
    return Object.entries(m).sort();
  }, [districts]);

  return (
    <div className="space-y-8">
      <PageHeader badge="Time-Series" title="Pollutant Time-Series Explorer"
        subtitle="Daily-level air quality data per district. Pick anywhere from Mumbai to Muzaffarpur and see exactly how its air evolved." />

      <Card>
        <CardHeader>
          <CardTitle>Pick what to plot</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-xs text-muted-foreground mb-1.5 block">District</label>
              <Select value={districtId} onValueChange={setDistrictId}>
                <SelectTrigger><SelectValue placeholder="District" /></SelectTrigger>
                <SelectContent className="max-h-72">
                  {grouped.map(([state, list]) => (
                    <div key={state}>
                      <div className="px-2 py-1 text-[10px] uppercase tracking-wider text-muted-foreground">{state}</div>
                      {list.map((d: any) => (
                        <SelectItem key={d.district_id} value={String(d.district_id)}>{d.district_name}</SelectItem>
                      ))}
                    </div>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1.5 block">Pollutant</label>
              <Select value={pollutant} onValueChange={setPollutant}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {POLLUTANTS.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1.5 block">Aggregation</label>
              <Select value={agg} onValueChange={setAgg}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {AGG.map(a => <SelectItem key={a.value} value={a.value}>{a.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{meta ? `${meta.district_name}, ${meta.state}` : "—"}</CardTitle>
          <CardDescription>{POLLUTANTS.find(p => p.value === pollutant)?.label} · {agg}</CardDescription>
        </CardHeader>
        <CardContent>
          {series.length > 0 ? (
            <PlotlyChart
              height={420}
              data={[{
                type: "scatter", mode: agg === "daily" ? "lines" : "lines+markers",
                x: series.map(d => d.date),
                y: series.map(d => d[pollutant]),
                line: { width: 2, color: "#38bdf8" },
                marker: { size: 5, color: "#38bdf8" },
                fill: "tozeroy", fillcolor: "rgba(56,189,248,0.08)",
                hovertemplate: "<b>%{x}</b><br>" + pollutant.toUpperCase() + ": %{y:.1f}<extra></extra>",
              }]}
              layout={{
                xaxis: { title: { text: "Date" }, type: "date" },
                yaxis: { title: { text: pollutant === "aqi" ? "AQI" : "µg/m³" } },
                shapes: pollutant === "pm25" ? [
                  { type: "line", x0: series[0]?.date, x1: series[series.length - 1]?.date, y0: 40, y1: 40,
                    line: { color: "#f87171", dash: "dash", width: 1.5 } },
                ] : [],
              }}
            />
          ) : (
            <div className="text-sm text-muted-foreground py-12 text-center">Loading…</div>
          )}
        </CardContent>
      </Card>

      <InsightBox variant="info" title="Read the rhythm">
        Almost every northern district shows a sawtooth pattern — winter peaks 2-3× higher than monsoon troughs. Southern districts (Kerala, Tamil Nadu) show much flatter time-series, reflecting better year-round dispersion.
      </InsightBox>
    </div>
  );
}
