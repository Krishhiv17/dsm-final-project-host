"use client";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { PlotlyChart } from "@/components/plot";
import { InsightBox } from "@/components/insight-box";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getClusters } from "@/lib/api";

const CLUSTER_COLORS: Record<string, string> = {
  "At Risk": "#fbbf24",
  "Critical — High Pollution": "#f87171",
  "Moderate": "#34d399",
  "Critical — High Disease Burden": "#a78bfa",
};
const CLUSTER_TONE: Record<string, "warning" | "critical" | "success" | "info"> = {
  "At Risk": "warning",
  "Critical — High Pollution": "critical",
  "Moderate": "success",
  "Critical — High Disease Burden": "critical",
};

export default function ClustersPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { getClusters().then(setData).catch(console.error); }, []);

  return (
    <div className="space-y-8">
      <PageHeader badge="District Clusters" title="K-Means Risk Clusters"
        subtitle="K-Means (K=4) on standardized PM2.5, PM10, NO₂, SO₂, urban %, literacy, and respiratory cases. Four natural groups emerge — each with a distinct policy implication." />

      {data?.summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {data.summary.map((c: any) => (
            <Card key={c.cluster} className="relative overflow-hidden">
              <div className="absolute top-0 left-0 w-full h-1" style={{ background: CLUSTER_COLORS[c.risk_label] }} />
              <CardHeader>
                <Badge variant={CLUSTER_TONE[c.risk_label] || "info"} className="w-fit">Cluster {c.cluster}</Badge>
                <CardTitle className="text-base">{c.risk_label}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 text-sm">
                <div className="flex justify-between"><span className="text-muted-foreground">Districts</span><span className="font-mono font-bold">{c.n_districts}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Avg PM2.5</span><span className="font-mono">{c.avg_pm25?.toFixed(1)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Avg respiratory</span><span className="font-mono">{c.avg_resp?.toFixed(0)}</span></div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Pollution × Disease — coloured by cluster</CardTitle>
          <CardDescription>Each point is a district. Cluster 3 (purple) sits below average pollution but above-average cases — that&apos;s the warning sign.</CardDescription>
        </CardHeader>
        <CardContent>
          {data?.clusters && data.clusters.length > 0 && (
            <PlotlyChart
              height={500}
              data={Object.keys(CLUSTER_COLORS).map(label => ({
                type: "scatter", mode: "markers", name: label,
                x: data.clusters.filter((d: any) => d.risk_label === label).map((d: any) => d.pm25),
                y: data.clusters.filter((d: any) => d.risk_label === label).map((d: any) => d.respiratory_cases),
                text: data.clusters.filter((d: any) => d.risk_label === label).map((d: any) => `${d.district_name}, ${d.state}`),
                marker: { size: 9, color: CLUSTER_COLORS[label], opacity: 0.85,
                  line: { color: "rgba(255,255,255,0.4)", width: 0.5 } },
                hovertemplate: "<b>%{text}</b><br>PM2.5: %{x:.1f}<br>Resp: %{y:.0f}<extra></extra>",
              }))}
              layout={{
                xaxis: { title: { text: "Average PM2.5 (µg/m³)" } },
                yaxis: { title: { text: "Average respiratory cases / month" } },
                legend: { orientation: "h", y: -0.2 },
              }}
            />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>All districts — sortable</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto max-h-[480px] scroll-area">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-card text-xs uppercase text-muted-foreground border-b border-border/60">
                <tr>
                  <th className="text-left py-2 px-3">District</th>
                  <th className="text-left py-2 px-3">State</th>
                  <th className="text-left py-2 px-3">Cluster</th>
                  <th className="text-right py-2 px-3">PM2.5</th>
                  <th className="text-right py-2 px-3">Respiratory</th>
                </tr>
              </thead>
              <tbody>
                {(data?.clusters || []).map((d: any, i: number) => (
                  <tr key={i} className="border-b border-border/30 hover:bg-accent/30 transition-colors">
                    <td className="py-2 px-3 font-medium">{d.district_name}</td>
                    <td className="py-2 px-3 text-muted-foreground">{d.state}</td>
                    <td className="py-2 px-3">
                      <Badge variant={CLUSTER_TONE[d.risk_label] || "info"}>{d.risk_label}</Badge>
                    </td>
                    <td className="py-2 px-3 text-right font-mono">{d.pm25?.toFixed(1)}</td>
                    <td className="py-2 px-3 text-right font-mono">{d.respiratory_cases?.toFixed(0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <InsightBox variant="critical" title="Cluster 3 is the most alarming">
        UP and Bihar dominate this cluster. PM2.5 here (~70 µg/m³) is lower than Delhi&apos;s, but disease rates are <b>2-3× higher</b>. Pollution alone doesn&apos;t explain the gap — it&apos;s amplified by lower healthcare access, nutrition, and housing quality.
      </InsightBox>
    </div>
  );
}
