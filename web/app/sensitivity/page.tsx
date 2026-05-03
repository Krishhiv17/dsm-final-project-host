"use client";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { PlotlyChart } from "@/components/plot";
import { InsightBox } from "@/components/insight-box";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import {
  getSensitivityCoefficients,
  getClusterSensitivitySummary,
  getClusterDoseResponse,
  getSensitivityInteraction,
} from "@/lib/api";

const CLUSTER_COLORS: Record<string, string> = {
  "At Risk":                       "#f59e0b",
  "Critical — High Pollution":     "#f87171",
  "Moderate":                      "#34d399",
  "Critical — High Disease Burden":"#a78bfa",
};

export default function SensitivityPage() {
  const [coeffs,   setCoeffs]   = useState<any[]>([]);
  const [summary,  setSummary]  = useState<any[]>([]);
  const [dose,     setDose]     = useState<any[]>([]);
  const [interact, setInteract] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([
      getSensitivityCoefficients(),
      getClusterSensitivitySummary(),
      getClusterDoseResponse(),
      getSensitivityInteraction(),
    ]).then(([c, s, d, i]) => {
      setCoeffs(c); setSummary(s); setDose(d); setInteract(i);
    }).catch(console.error);
  }, []);

  const c3        = summary.find((s: any) => s.cluster === 3);
  const c3Inter   = interact.find((i: any) => i.term === "c3");
  const clusterLabels = [...new Set(dose.map((d: any) => d.cluster_label as string))];

  return (
    <div className="space-y-8">
      <PageHeader
        badge="New Analysis"
        title="Pollution Sensitivity: The Cluster 3 Anomaly"
        subtitle="A uniform NAAQS standard assumes every district generates the same respiratory burden per µg/m³. The data proves otherwise. Cluster 3 districts (UP/Bihar) produce nearly 3× more cases at the same pollution level as any other cluster — and the gap is statistically significant even after controlling for population and PM2.5."
      />

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-5 text-center">
            <div className="text-3xl font-bold text-violet-400">
              {c3Inter ? `+${Math.round(c3Inter.coefficient).toLocaleString()}` : "—"}
            </div>
            <div className="text-xs text-muted-foreground mt-1">extra cases/month</div>
            <div className="text-xs text-muted-foreground">Cluster 3 structural excess</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5 text-center">
            <div className="text-3xl font-bold text-violet-400">
              {c3Inter ? (c3Inter.p_value < 0.001 ? "p < 0.001" : `p = ${c3Inter.p_value?.toFixed(3)}`) : "—"}
            </div>
            <div className="text-xs text-muted-foreground mt-1">significance</div>
            <div className="text-xs text-muted-foreground">controlling for PM2.5 + population</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5 text-center">
            <div className="text-3xl font-bold text-sky-400">
              {c3 ? `+${Math.round(c3.mean_excess_cases).toLocaleString()}` : "—"}
            </div>
            <div className="text-xs text-muted-foreground mt-1">mean excess cases/month</div>
            <div className="text-xs text-muted-foreground">avg per Cluster 3 district</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5 text-center">
            <div className="text-3xl font-bold text-sky-400">
              {c3 ? `~${(c3.mean_resp / (summary.find((s:any)=>s.cluster===0)?.mean_resp ?? c3.mean_resp) ).toFixed(1)}×` : "—"}
            </div>
            <div className="text-xs text-muted-foreground mt-1">Cluster 3 vs At Risk</div>
            <div className="text-xs text-muted-foreground">at comparable PM2.5 levels</div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="dose">
        <TabsList className="mb-2 flex-wrap h-auto">
          <TabsTrigger value="dose">Cluster Dose-Response</TabsTrigger>
          <TabsTrigger value="residuals">Excess Burden</TabsTrigger>
          <TabsTrigger value="summary">Cluster Comparison</TabsTrigger>
          <TabsTrigger value="interaction">Formal Test</TabsTrigger>
        </TabsList>

        {/* ── Cluster Dose-Response ── */}
        <TabsContent value="dose">
          <Card>
            <CardHeader>
              <CardTitle>Same pollution level, vastly different outcomes</CardTitle>
              <CardDescription>
                Mean monthly respiratory cases per PM2.5 concentration bin, computed separately for
                each K-Means cluster. At PM2.5 ~60–70 µg/m³, Cluster 3 (purple) produces
                1,700–1,800 cases/month while other clusters at the same level produce 400–700.
                The gap is a structural shift, not a dosage difference.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {dose.length > 0 && (
                <PlotlyChart
                  height={480}
                  data={clusterLabels.map((label) => {
                    const rows = dose
                      .filter((d: any) => d.cluster_label === label)
                      .sort((a: any, b: any) => a.pm25_bin_mid - b.pm25_bin_mid);
                    const color = CLUSTER_COLORS[label] ?? "#94a3b8";
                    return {
                      type: "scatter",
                      mode: "lines+markers",
                      name: label,
                      x: rows.map((r: any) => r.pm25_bin_mid),
                      y: rows.map((r: any) => r.mean_resp),
                      error_y: {
                        type: "data", symmetric: false,
                        array:      rows.map((r: any) => Math.max(0, r.ci_upper - r.mean_resp)),
                        arrayminus: rows.map((r: any) => Math.max(0, r.mean_resp - r.ci_lower)),
                        visible: true, color, opacity: 0.3, thickness: 1.5,
                      },
                      line:   { color, width: label.includes("Disease") ? 3.5 : 2 },
                      marker: { color, size: label.includes("Disease") ? 10 : 7 },
                      hovertemplate:
                        `<b>${label}</b><br>PM2.5: %{x:.1f} µg/m³<br>Resp: %{y:.0f} cases/mo<extra></extra>`,
                    };
                  })}
                  layout={{
                    xaxis: { title: { text: "PM2.5 (µg/m³) — bin midpoint" } },
                    yaxis: { title: { text: "Mean respiratory cases / month" } },
                    legend: { orientation: "h", y: -0.28 },
                  }}
                />
              )}
              <InsightBox variant="warning" title="Key observation">
                Every Cluster 3 bin — at every PM2.5 level — sits above every other cluster at the same
                pollution level. This is not a slope effect (the curves are roughly parallel): it is a
                vertical shift. Cluster 3 districts start at a higher disease baseline and stay above it
                regardless of how much pollution they have.
              </InsightBox>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Excess Burden Scatter ── */}
        <TabsContent value="residuals">
          <Card>
            <CardHeader>
              <CardTitle>Residuals from the national regression</CardTitle>
              <CardDescription>
                The national model predicts respiratory cases from PM2.5 + population.
                The residual is how many cases each district generates above or below that prediction.
                Positive = more cases than the national trend explains. Cluster 3 districts should
                cluster tightly in the positive region regardless of their PM2.5 level.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {coeffs.length > 0 && (() => {
                const byCluster = [...new Set(coeffs.map((c: any) => c.cluster_label as string))];
                return (
                  <PlotlyChart
                    height={460}
                    data={[
                      // zero reference line
                      {
                        type: "scatter", mode: "lines",
                        x: [0, 170], y: [0, 0],
                        line: { color: "#475569", width: 1, dash: "dot" },
                        showlegend: false, hoverinfo: "none",
                      } as any,
                      ...byCluster.map((label) => {
                        const pts = coeffs.filter((c: any) => c.cluster_label === label);
                        const color = CLUSTER_COLORS[label] ?? "#94a3b8";
                        return {
                          type: "scatter", mode: "markers",
                          name: label,
                          x: pts.map((c: any) => c.pm25),
                          y: pts.map((c: any) => c.residual),
                          text: pts.map((c: any) => c.district_name),
                          marker: { color, size: 8, opacity: 0.8 },
                          hovertemplate:
                            "%{text}<br>PM2.5: %{x:.1f}<br>Excess cases: %{y:+.0f}<extra></extra>",
                        };
                      }),
                    ]}
                    layout={{
                      xaxis: { title: { text: "Mean PM2.5 (µg/m³)" } },
                      yaxis: {
                        title: { text: "Excess cases/month above national prediction" },
                        zeroline: false,
                      },
                      legend: { orientation: "h", y: -0.28 },
                    }}
                  />
                );
              })()}
              <div className="text-xs text-muted-foreground text-center mt-1">
                Dotted line = national model prediction. Points above = more cases than predicted.
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Cluster Summary ── */}
        <TabsContent value="summary">
          <Card>
            <CardHeader>
              <CardTitle>Mean excess burden per cluster</CardTitle>
              <CardDescription>
                Average residual (cases above the national trend) per district in each cluster.
                Only Cluster 3 has a systematically positive excess — the other clusters are near zero
                or slightly below, confirming the national model fits them well.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {summary.length > 0 && (
                <>
                  <PlotlyChart
                    height={300}
                    data={[{
                      type: "bar",
                      x: summary.map((s: any) => s.cluster_label),
                      y: summary.map((s: any) => s.mean_excess_cases),
                      marker: {
                        color: summary.map((s: any) => CLUSTER_COLORS[s.cluster_label] ?? "#64748b"),
                      },
                      text: summary.map((s: any) =>
                        `${s.mean_excess_cases > 0 ? "+" : ""}${Math.round(s.mean_excess_cases)}`
                      ),
                      textposition: "outside",
                      hovertemplate:
                        "%{x}<br>Mean excess: %{y:+.0f} cases/month<extra></extra>",
                    }]}
                    layout={{
                      yaxis: {
                        title: { text: "Mean excess cases/month above national prediction" },
                        zeroline: true, zerolinecolor: "#475569", zerolinewidth: 1,
                      },
                      xaxis: { tickangle: -12 },
                    }}
                  />
                  <div className="overflow-x-auto mt-4">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border/60 text-left">
                          <th className="pb-2 pr-4 font-semibold">Cluster</th>
                          <th className="pb-2 pr-4 font-semibold text-right">Districts</th>
                          <th className="pb-2 pr-4 font-semibold text-right">Mean PM2.5</th>
                          <th className="pb-2 pr-4 font-semibold text-right">Mean Resp/mo</th>
                          <th className="pb-2 font-semibold text-right">Mean Excess</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.map((s: any) => (
                          <tr key={s.cluster} className="border-b border-border/30">
                            <td className="py-2 pr-4 flex items-center gap-2">
                              <span className="inline-block w-3 h-3 rounded-sm shrink-0"
                                style={{ background: CLUSTER_COLORS[s.cluster_label] ?? "#64748b" }} />
                              {s.cluster_label}
                            </td>
                            <td className="py-2 pr-4 text-right font-mono">{s.n_districts}</td>
                            <td className="py-2 pr-4 text-right font-mono">{s.mean_pm25?.toFixed(1)} µg/m³</td>
                            <td className="py-2 pr-4 text-right font-mono">{Math.round(s.mean_resp).toLocaleString()}</td>
                            <td className="py-2 text-right font-mono font-semibold"
                              style={{ color: s.cluster === 3 ? "#a78bfa" : s.mean_excess_cases > 0 ? "#34d399" : "#94a3b8" }}>
                              {s.mean_excess_cases > 0 ? "+" : ""}{Math.round(s.mean_excess_cases).toLocaleString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Formal Test ── */}
        <TabsContent value="interaction">
          <Card>
            <CardHeader>
              <CardTitle>Formal regression test: is the Cluster 3 shift real?</CardTitle>
              <CardDescription>
                OLS with cluster dummy variables and PM2.5 × cluster interaction terms, controlling
                for population. Cluster 2 (Moderate) is the reference.
                A significant <code>c3</code> coefficient means Cluster 3 has a statistically
                distinct structural excess, independent of pollution level.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {interact.length > 0 && (
                <>
                  <PlotlyChart
                    height={320}
                    data={[{
                      type: "bar",
                      orientation: "h",
                      x: interact.map((i: any) => i.coefficient),
                      y: interact.map((i: any) => i.term),
                      error_x: {
                        type: "data",
                        array: interact.map((i: any) => i.std_error * 1.96),
                        visible: true,
                        color: "rgba(148,163,184,0.5)",
                      },
                      marker: {
                        color: interact.map((i: any) =>
                          i.term === "c3"    ? "#a78bfa"
                          : i.significant   ? "#38bdf8"
                          : "#475569"
                        ),
                      },
                      hovertemplate:
                        "%{y}<br>β = %{x:.1f} (95% CI ±%{error_x.array:.1f})<extra></extra>",
                    }]}
                    layout={{
                      xaxis: {
                        title: { text: "Coefficient (respiratory cases/month)" },
                        zeroline: true, zerolinecolor: "#475569", zerolinewidth: 1,
                      },
                      margin: { l: 120 },
                    }}
                  />
                  <div className="overflow-x-auto mt-4">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border/60 text-left">
                          <th className="pb-2 pr-6 font-semibold">Term</th>
                          <th className="pb-2 pr-6 font-semibold text-right">Coefficient</th>
                          <th className="pb-2 pr-6 font-semibold text-right">Std Error</th>
                          <th className="pb-2 font-semibold text-right">p-value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {interact.map((i: any, idx: number) => (
                          <tr key={idx}
                            className={`border-b border-border/30 ${i.term === "c3" ? "bg-violet-500/5" : ""}`}>
                            <td className="py-1.5 pr-6 font-mono text-xs"
                              style={{ color: i.term === "c3" ? "#a78bfa" : undefined }}>
                              {i.term}
                              {i.term === "c3" && (
                                <span className="ml-2 text-violet-400 font-sans not-italic">← Cluster 3 level shift</span>
                              )}
                            </td>
                            <td className="py-1.5 pr-6 text-right font-mono">{i.coefficient?.toFixed(1)}</td>
                            <td className="py-1.5 pr-6 text-right font-mono">{i.std_error?.toFixed(1)}</td>
                            <td className="py-1.5 text-right">
                              <Badge variant={i.significant ? "critical" : "secondary"}>
                                {i.p_value < 0.001 ? "< 0.001" : i.p_value?.toFixed(3)}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {interact[0]?.r2 && (
                      <div className="text-xs text-muted-foreground mt-2 text-center">
                        Model R² = {interact[0].r2?.toFixed(3)} · n = {interact[0].n} districts
                      </div>
                    )}
                  </div>
                  <InsightBox variant="info" title="What the significant c3 term means">
                    The <code>c3</code> coefficient (+1,735, p&lt;0.001) is statistically significant while
                    none of the PM2.5 × cluster interaction terms are. This means Cluster 3&apos;s excess
                    is a <strong>structural level shift</strong> — not a steeper dose-response slope.
                    These districts generate ~1,735 extra cases per month compared to the reference,
                    controlling for both pollution level and population size. Cutting PM2.5 alone will
                    not close this gap.
                  </InsightBox>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <InsightBox variant="warning" title="Why this finding changes the policy picture">
        Every other analysis in this project frames the problem as: <em>reduce PM2.5 → reduce disease</em>.
        The sensitivity analysis reveals a harder constraint: Cluster 3 districts have a baseline structural
        deficit of ~1,735 extra cases/month that exists independently of pollution level. This means
        air quality improvement in UP/Bihar will produce smaller health gains per µg/m³ of PM2.5 reduced
        than in Delhi or Maharashtra — not because the interventions don&apos;t work, but because a substantial
        share of the disease burden has other structural drivers. Healthcare infrastructure, sanitation, and
        nutritional access must be treated as co-equal interventions, not downstream afterthoughts.
      </InsightBox>
    </div>
  );
}
