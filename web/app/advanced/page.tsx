"use client";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { PlotlyChart } from "@/components/plot";
import { InsightBox } from "@/components/insight-box";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import {
  getPCA, getMediation, getPanelFE, getGWR, getEpiMetrics,
  getPartialCorrelation, getSpatialLag,
} from "@/lib/api";

export default function AdvancedPage() {
  const [pca, setPca] = useState<any>(null);
  const [med, setMed] = useState<any>(null);
  const [panel, setPanel] = useState<any[]>([]);
  const [gwr, setGwr] = useState<any[]>([]);
  const [epi, setEpi] = useState<any[]>([]);
  const [partial, setPartial] = useState<any>(null);
  const [spatial, setSpatial] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([
      getPCA(), getMediation(), getPanelFE(), getGWR(),
      getEpiMetrics(), getPartialCorrelation(), getSpatialLag(),
    ]).then(([p, m, pn, g, e, pc, sl]) => {
      setPca(p); setMed(m); setPanel(pn); setGwr(g);
      setEpi(e); setPartial(pc); setSpatial(sl);
    }).catch(console.error);
  }, []);

  return (
    <div className="space-y-8">
      <PageHeader badge="Advanced Analytics" title="Heavy Statistical Machinery"
        subtitle="PCA structure, mediation paths, fixed-effects panel models, geographically-weighted regression, partial correlation, spatial lag, and epidemiological metrics — the full statistical case." />

      <Tabs defaultValue="pca">
        <TabsList className="mb-2 flex-wrap h-auto">
          <TabsTrigger value="pca">PCA</TabsTrigger>
          <TabsTrigger value="mediation">Mediation</TabsTrigger>
          <TabsTrigger value="panel">Panel FE</TabsTrigger>
          <TabsTrigger value="gwr">GWR</TabsTrigger>
          <TabsTrigger value="epi">Epi metrics</TabsTrigger>
          <TabsTrigger value="partial">Partial corr.</TabsTrigger>
          <TabsTrigger value="spatial">Spatial lag</TabsTrigger>
        </TabsList>

        <TabsContent value="pca">
          <Card>
            <CardHeader>
              <CardTitle>Principal Component Analysis</CardTitle>
              <CardDescription>Districts projected to 2D space of dominant pollution-health variation. Clusters confirm the 4-group structure from K-Means.</CardDescription>
            </CardHeader>
            <CardContent>
              {pca?.sample && pca.sample.length > 0 && (
                <PlotlyChart
                  height={500}
                  data={[{
                    type: "scatter", mode: "markers",
                    x: pca.sample.map((d: any) => d.PC1 ?? d.pc1),
                    y: pca.sample.map((d: any) => d.PC2 ?? d.pc2),
                    text: pca.sample.map((d: any) => d.state),
                    marker: { size: 5, color: pca.sample.map((d: any) => d.PC1 ?? d.pc1),
                      colorscale: "Viridis", showscale: true,
                      colorbar: { title: { text: "PC1" } } },
                    hovertemplate: "%{text}<br>PC1=%{x:.2f}<br>PC2=%{y:.2f}<extra></extra>",
                  }]}
                  layout={{ xaxis: { title: { text: "PC1" } }, yaxis: { title: { text: "PC2" } } }}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="mediation">
          <Card>
            <CardHeader>
              <CardTitle>Mediation Analysis</CardTitle>
              <CardDescription>Does the effect of PM2.5 on respiratory cases run <em>through</em> a mediator?</CardDescription>
            </CardHeader>
            <CardContent>
              {med ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {Object.entries(med).map(([k, v]: any) => (
                    <div key={k} className="p-4 rounded-lg border border-border/60 bg-card/40">
                      <div className="text-xs uppercase tracking-wider text-muted-foreground">{k}</div>
                      <div className="text-2xl font-mono mt-1">{typeof v === "number" ? v.toFixed(4) : String(v)}</div>
                    </div>
                  ))}
                </div>
              ) : <div className="text-sm text-muted-foreground py-8 text-center">Mediation not yet computed.</div>}
              <InsightBox variant="info" title="What this tests" className="mt-4">
                A significant indirect effect implies part of the pollution-health link operates through an intermediate variable (e.g. urbanisation density). Direct effect remaining significant ⇒ pollution still has an autonomous causal pathway.
              </InsightBox>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="panel">
          <Card>
            <CardHeader>
              <CardTitle>Panel Fixed-Effects Regression</CardTitle>
              <CardDescription>Controls for unobserved district-level constants. Cleaner coefficient on PM2.5 than naive OLS.</CardDescription>
            </CardHeader>
            <CardContent>
              {panel.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-xs uppercase text-muted-foreground border-b border-border/60">
                      <tr>
                        <th className="text-left py-2 px-3">Variable</th>
                        <th className="text-right py-2 px-3">Coefficient</th>
                        <th className="text-right py-2 px-3">Std error</th>
                        <th className="text-right py-2 px-3">t-stat</th>
                        <th className="text-right py-2 px-3">p-value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {panel.map((r: any, i: number) => (
                        <tr key={i} className="border-b border-border/30">
                          <td className="py-1.5 px-3 font-medium">{r.variable ?? r.feature ?? r.name}</td>
                          <td className="py-1.5 px-3 text-right font-mono">{(r.coef ?? r.coefficient)?.toFixed(4)}</td>
                          <td className="py-1.5 px-3 text-right font-mono">{(r.std_err ?? r.se)?.toFixed?.(4) ?? "—"}</td>
                          <td className="py-1.5 px-3 text-right font-mono">{(r.t_stat ?? r.tstat)?.toFixed?.(2) ?? "—"}</td>
                          <td className="py-1.5 px-3 text-right">
                            <Badge variant={(r.p_value ?? r.pvalue) < 0.05 ? "critical" : "secondary"}>
                              {(r.p_value ?? r.pvalue) < 0.0001 ? "<.0001" : (r.p_value ?? r.pvalue)?.toFixed?.(4)}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <div className="text-sm text-muted-foreground py-8 text-center">Panel FE not available.</div>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="gwr">
          <Card>
            <CardHeader>
              <CardTitle>Geographically-Weighted Regression</CardTitle>
              <CardDescription>The PM2.5 coefficient isn&apos;t constant — it depends on where you are. Separate models per zone:</CardDescription>
            </CardHeader>
            <CardContent>
              {gwr.length > 0 ? (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <PlotlyChart
                      height={360}
                      data={[
                        {
                          type: "bar", name: "PM2.5",
                          x: gwr.map((r: any) => r.zone),
                          y: gwr.map((r: any) => r.coeff_pm25),
                          marker: { color: gwr.map((r: any) => r.coeff_pm25 > 0 ? "#f87171" : "#34d399") },
                          hovertemplate: "<b>%{x}</b><br>β(PM2.5) = %{y:.2f}<extra></extra>",
                        },
                      ]}
                      layout={{
                        title: { text: "β on PM2.5" },
                        yaxis: { title: { text: "Coefficient" }, zeroline: true, zerolinecolor: "rgba(148,163,184,0.4)" },
                      }}
                    />
                    <PlotlyChart
                      height={360}
                      data={[
                        {
                          type: "bar", name: "PM10",
                          x: gwr.map((r: any) => r.zone),
                          y: gwr.map((r: any) => r.coeff_pm10),
                          marker: { color: gwr.map((r: any) => r.coeff_pm10 > 0 ? "#fbbf24" : "#34d399") },
                          hovertemplate: "<b>%{x}</b><br>β(PM10) = %{y:.2f}<extra></extra>",
                        },
                      ]}
                      layout={{
                        title: { text: "β on PM10" },
                        yaxis: { title: { text: "Coefficient" }, zeroline: true, zerolinecolor: "rgba(148,163,184,0.4)" },
                      }}
                    />
                  </div>

                  <PlotlyChart
                    height={300}
                    data={[
                      {
                        type: "bar", name: "R²",
                        x: gwr.map((r: any) => r.zone),
                        y: gwr.map((r: any) => r.r2),
                        marker: { color: "#38bdf8" },
                        hovertemplate: "<b>%{x}</b><br>R² = %{y:.3f}<extra></extra>",
                      },
                    ]}
                    layout={{
                      title: { text: "Local model R² by zone" },
                      yaxis: { title: { text: "R²" }, range: [0, 1] },
                    }}
                  />

                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-xs uppercase text-muted-foreground border-b border-border/60">
                        <tr>
                          <th className="text-left py-2 px-3">Zone</th>
                          <th className="text-right py-2 px-3">N obs</th>
                          <th className="text-right py-2 px-3">R²</th>
                          <th className="text-right py-2 px-3">β PM2.5</th>
                          <th className="text-right py-2 px-3">β PM10</th>
                          <th className="text-right py-2 px-3">β Urban %</th>
                        </tr>
                      </thead>
                      <tbody>
                        {gwr.map((r: any, i: number) => (
                          <tr key={i} className="border-b border-border/30 hover:bg-accent/30">
                            <td className="py-1.5 px-3 font-medium">{r.zone}</td>
                            <td className="py-1.5 px-3 text-right font-mono">{r.n_obs?.toLocaleString()}</td>
                            <td className="py-1.5 px-3 text-right">
                              <Badge variant={r.r2 > 0.5 ? "success" : r.r2 > 0.3 ? "warning" : "secondary"}>
                                {r.r2?.toFixed(3)}
                              </Badge>
                            </td>
                            <td className="py-1.5 px-3 text-right font-mono">{r.coeff_pm25?.toFixed(2)}</td>
                            <td className="py-1.5 px-3 text-right font-mono">{r.coeff_pm10?.toFixed(2)}</td>
                            <td className="py-1.5 px-3 text-right font-mono">{r.coeff_urban_percentage?.toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <InsightBox variant="info" title="Why GWR matters">
                    A single national regression hides geography — every zone gets the same β. Splitting by zone reveals that the same µg/m³ of PM2.5 is associated with very different excess case-loads in North vs South India. Policy designed at a national average will systematically under-protect the worst-fit zones.
                  </InsightBox>
                </div>
              ) : <div className="text-sm text-muted-foreground py-8 text-center">GWR results not available — re-run <code className="text-xs bg-muted px-1.5 py-0.5 rounded">src/07_advanced_stats.py</code>.</div>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="epi">
          <Card>
            <CardHeader>
              <CardTitle>Epidemiological Metrics</CardTitle>
              <CardDescription>Relative risk, odds ratios, and population-attributable risk per district / region.</CardDescription>
            </CardHeader>
            <CardContent>
              {epi.length > 0 ? (
                <div className="overflow-x-auto max-h-[480px] scroll-area">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-card text-xs uppercase text-muted-foreground border-b border-border/60">
                      <tr>{Object.keys(epi[0]).map(k => (
                        <th key={k} className="text-left py-2 px-3">{k}</th>
                      ))}</tr>
                    </thead>
                    <tbody>
                      {epi.map((r: any, i: number) => (
                        <tr key={i} className="border-b border-border/30">
                          {Object.entries(r).map(([k, v]: any) => (
                            <td key={k} className="py-1.5 px-3 font-mono text-xs">
                              {typeof v === "number" ? v.toFixed(3) : String(v)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <div className="text-sm text-muted-foreground py-8 text-center">Epi metrics not available.</div>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="partial">
          <Card>
            <CardHeader>
              <CardTitle>Partial Correlation</CardTitle>
              <CardDescription>PM2.5 ↔ Respiratory <em>after controlling for</em> population, urban %, literacy. Survives ⇒ pollution has independent explanatory power.</CardDescription>
            </CardHeader>
            <CardContent>
              {partial ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {Object.entries(partial).map(([k, v]: any) => (
                    <div key={k} className="p-4 rounded-lg border border-border/60 bg-card/40">
                      <div className="text-xs uppercase tracking-wider text-muted-foreground">{k}</div>
                      <div className="text-2xl font-mono mt-1">{typeof v === "number" ? v.toFixed(4) : String(v)}</div>
                    </div>
                  ))}
                </div>
              ) : <div className="text-sm text-muted-foreground py-8 text-center">Partial correlation not available.</div>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="spatial">
          <Card>
            <CardHeader>
              <CardTitle>Spatial Lag Model</CardTitle>
              <CardDescription>Adds a neighbours-weighted-average term: does a district&apos;s outcome depend on its neighbours&apos; outcomes?</CardDescription>
            </CardHeader>
            <CardContent>
              {spatial.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-xs uppercase text-muted-foreground border-b border-border/60">
                      <tr>{Object.keys(spatial[0]).map(k => (
                        <th key={k} className="text-left py-2 px-3">{k}</th>
                      ))}</tr>
                    </thead>
                    <tbody>
                      {spatial.map((r: any, i: number) => (
                        <tr key={i} className="border-b border-border/30">
                          {Object.entries(r).map(([k, v]: any) => (
                            <td key={k} className="py-1.5 px-3 font-mono text-xs">
                              {typeof v === "number" ? v.toFixed(4) : String(v)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <div className="text-sm text-muted-foreground py-8 text-center">Spatial lag not available.</div>}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
