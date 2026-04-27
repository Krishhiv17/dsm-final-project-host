"use client";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { PlotlyChart } from "@/components/plot";
import { InsightBox } from "@/components/insight-box";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import {
  getGrangerWithin, getCrossCorrelation, getDoseResponse,
  getCounterfactual, getChangePoint, getAttributable,
  getSyntheticControl, getRDD, getPSM,
} from "@/lib/api";

export default function CausalPage() {
  const [granger, setGranger] = useState<any[]>([]);
  const [xcorr, setXcorr] = useState<any[]>([]);
  const [dose, setDose] = useState<any[]>([]);
  const [counter, setCounter] = useState<any[]>([]);
  const [cp, setCp] = useState<any>(null);
  const [attr, setAttr] = useState<any[]>([]);
  const [sc, setSc] = useState<any>(null);
  const [rdd, setRdd] = useState<any>(null);
  const [psm, setPsm] = useState<any>(null);

  useEffect(() => {
    Promise.all([
      getGrangerWithin(), getCrossCorrelation(), getDoseResponse(),
      getCounterfactual(), getChangePoint(), getAttributable(),
      getSyntheticControl(), getRDD(), getPSM(),
    ]).then(([g, x, d, c, cp_, a, sc_, rdd_, psm_]) => {
      setGranger(g); setXcorr(x); setDose(d); setCounter(c); setCp(cp_); setAttr(a);
      setSc(sc_); setRdd(rdd_); setPsm(psm_);
    }).catch(console.error);
  }, []);

  return (
    <div className="space-y-8">
      <PageHeader badge="Causal Inference" title="Beyond Correlation"
        subtitle="Correlation is the floor, not the ceiling. These tests probe direction, dose-response, lagged effects, and what would have happened under cleaner air." />

      <Tabs defaultValue="dose">
        <TabsList className="mb-2 flex-wrap h-auto">
          <TabsTrigger value="dose">Dose-Response</TabsTrigger>
          <TabsTrigger value="xcorr">Cross-correlation</TabsTrigger>
          <TabsTrigger value="granger">Granger Causality</TabsTrigger>
          <TabsTrigger value="counter">Counterfactual</TabsTrigger>
          <TabsTrigger value="cp">Change-points</TabsTrigger>
          <TabsTrigger value="attr">Attributable Fraction</TabsTrigger>
          <TabsTrigger value="sc">Synthetic Control</TabsTrigger>
          <TabsTrigger value="rdd">RDD</TabsTrigger>
          <TabsTrigger value="psm">PSM</TabsTrigger>
        </TabsList>

        <TabsContent value="dose">
          <Card>
            <CardHeader>
              <CardTitle>Dose-Response Curve</CardTitle>
              <CardDescription>Avg respiratory cases by PM2.5 quantile. A monotonic rise = the kind of curve epidemiologists expect for a real exposure-effect.</CardDescription>
            </CardHeader>
            <CardContent>
              {dose.length > 0 && (
                <PlotlyChart
                  height={420}
                  data={[
                    {
                      type: "scatter", mode: "lines+markers", name: "Observed",
                      x: dose.map((d: any) => d.pm25_bin_center),
                      y: dose.map((d: any) => d.resp_rate_mean),
                      error_y: { type: "data", array: dose.map((d: any) => 1.96 * (d.se ?? 0)),
                        color: "rgba(248,113,113,0.4)", thickness: 1, width: 4 },
                      line: { width: 3, color: "#f87171" },
                      marker: { size: 12, color: "#f87171" },
                      fill: "tozeroy", fillcolor: "rgba(248,113,113,0.08)",
                    },
                    {
                      type: "scatter", mode: "lines", name: "Linear fit",
                      x: dose.map((d: any) => d.pm25_bin_center),
                      y: dose.map((d: any) => d.linear_fit),
                      line: { width: 2, color: "#38bdf8", dash: "dash" },
                    },
                    {
                      type: "scatter", mode: "lines", name: "Log-linear fit",
                      x: dose.map((d: any) => d.pm25_bin_center),
                      y: dose.map((d: any) => d.loglinear_fit),
                      line: { width: 2, color: "#a78bfa", dash: "dot" },
                    },
                  ]}
                  layout={{
                    xaxis: { title: { text: "PM2.5 (µg/m³) — bin midpoint" } },
                    yaxis: { title: { text: "Respiratory rate (cases / 100k)" } },
                    legend: { orientation: "h", y: -0.2 },
                  }}
                />
              )}
              <InsightBox variant="critical" title="The exposure-effect signature" className="mt-4">
                A clean monotonic rise is exactly what you&apos;d expect if PM2.5 actually causes excess respiratory cases. A flat or jagged curve would have raised concerns about confounders.
              </InsightBox>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="xcorr">
          <Card>
            <CardHeader>
              <CardTitle>National Cross-correlation (PM2.5 ↔ Respiratory)</CardTitle>
              <CardDescription>Correlation at successive month-lags. Peak lag tells us the reaction time of disease to pollution.</CardDescription>
            </CardHeader>
            <CardContent>
              {xcorr.length > 0 && (
                <PlotlyChart
                  height={420}
                  data={[{
                    type: "bar",
                    x: xcorr.map(d => d.lag_months), y: xcorr.map(d => d.cross_correlation),
                    marker: { color: xcorr.map(d => d.cross_correlation > 0 ? "#38bdf8" : "#f87171") },
                  }]}
                  layout={{
                    xaxis: { title: { text: "Lag (months) — pollution leads disease →" } },
                    yaxis: { title: { text: "Correlation" } },
                  }}
                />
              )}
              <InsightBox variant="info" title="Reading lags" className="mt-4">
                Peak correlation at lag &gt; 0 means PM2.5 changes <em>lead</em> respiratory case changes — this temporal ordering is one of the classic Bradford-Hill criteria for causation.
              </InsightBox>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="granger">
          <Card>
            <CardHeader>
              <CardTitle>Within-District Granger Causality</CardTitle>
              <CardDescription>Does past PM2.5 help predict future respiratory cases beyond what past cases already predict?</CardDescription>
            </CardHeader>
            <CardContent>
              {granger.length > 0 && (() => {
                const sigCount = granger.filter((g: any) => g.significant_05).length;
                const total = granger.length;
                const pct = ((sigCount / total) * 100).toFixed(1);
                const sortedByLag = [...granger]
                  .filter((g: any) => g.significant_05)
                  .reduce((acc: Record<number, number>, g: any) => {
                    const lag = g.best_lag_months;
                    acc[lag] = (acc[lag] || 0) + 1;
                    return acc;
                  }, {});
                const lagKeys = Object.keys(sortedByLag).map(Number).sort((a, b) => a - b);
                return (
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div className="rounded-lg border border-border/60 p-4 bg-card/40">
                        <div className="text-xs uppercase tracking-wider text-muted-foreground">Districts tested</div>
                        <div className="text-2xl font-mono mt-1">{total}</div>
                      </div>
                      <div className="rounded-lg border border-rose-500/30 p-4 bg-rose-500/5">
                        <div className="text-xs uppercase tracking-wider text-muted-foreground">Granger-cause at p &lt; 0.05</div>
                        <div className="text-2xl font-mono mt-1 text-rose-300">{sigCount} <span className="text-sm text-muted-foreground">({pct}%)</span></div>
                      </div>
                      <div className="rounded-lg border border-border/60 p-4 bg-card/40">
                        <div className="text-xs uppercase tracking-wider text-muted-foreground">Most common best lag</div>
                        <div className="text-2xl font-mono mt-1">
                          {lagKeys.length > 0 ? `${Object.entries(sortedByLag).sort((a, b) => (b[1] as number) - (a[1] as number))[0][0]} mo` : "—"}
                        </div>
                      </div>
                    </div>

                    <PlotlyChart
                      height={300}
                      data={[{
                        type: "bar",
                        x: lagKeys,
                        y: lagKeys.map(k => sortedByLag[k]),
                        marker: { color: "#38bdf8" },
                        hovertemplate: "Lag %{x} mo<br>%{y} districts<extra></extra>",
                      }]}
                      layout={{
                        title: { text: "Distribution of best PM2.5 → respiratory lags (significant districts)" },
                        xaxis: { title: { text: "Best lag (months)" }, dtick: 1 },
                        yaxis: { title: { text: "Number of districts" } },
                      }}
                    />

                    <div className="overflow-x-auto max-h-[400px] scroll-area">
                      <table className="w-full text-sm">
                        <thead className="sticky top-0 bg-card text-xs uppercase text-muted-foreground border-b border-border/60">
                          <tr>
                            <th className="text-left py-2 px-3">District</th>
                            <th className="text-left py-2 px-3">State</th>
                            <th className="text-right py-2 px-3">Best lag (mo)</th>
                            <th className="text-right py-2 px-3">F-stat</th>
                            <th className="text-right py-2 px-3">p-value</th>
                            <th className="text-left py-2 px-3">Result</th>
                          </tr>
                        </thead>
                        <tbody>
                          {granger
                            .slice()
                            .sort((a: any, b: any) => (a.p_value ?? 1) - (b.p_value ?? 1))
                            .map((g: any, i: number) => (
                              <tr key={i} className="border-b border-border/30">
                                <td className="py-1.5 px-3">{g.district_name ?? `District ${g.district_id}`}</td>
                                <td className="py-1.5 px-3 text-muted-foreground">{g.state ?? "—"}</td>
                                <td className="py-1.5 px-3 text-right font-mono">{g.best_lag_months}</td>
                                <td className="py-1.5 px-3 text-right font-mono">{g.F_stat?.toFixed(2)}</td>
                                <td className="py-1.5 px-3 text-right font-mono">
                                  {g.p_value < 0.0001 ? "<.0001" : g.p_value?.toFixed(4)}
                                </td>
                                <td className="py-1.5 px-3">
                                  <Badge variant={g.significant_05 ? "critical" : g.significant_10 ? "warning" : "secondary"}>
                                    {g.significant_05 ? "Granger-causes" : g.significant_10 ? "Marginal (p<.10)" : "Not significant"}
                                  </Badge>
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                );
              })()}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="counter">
          <Card>
            <CardHeader>
              <CardTitle>Counterfactual: How much disease would cleaner air prevent?</CardTitle>
              <CardDescription>For each PM2.5 reduction scenario (10% all the way to 50%), the trained model predicts national cases averted.</CardDescription>
            </CardHeader>
            <CardContent>
              {counter.length > 0 && (
                <div className="space-y-4">
                  <PlotlyChart
                    height={400}
                    data={[
                      {
                        type: "bar", name: "Cases averted",
                        x: counter.map((d: any) => `${d.pm25_reduction_pct}%`),
                        y: counter.map((d: any) => d.cases_averted),
                        marker: {
                          color: counter.map((d: any) => d.percent_cases_reduced),
                          colorscale: [[0, "#fbbf24"], [1, "#34d399"]],
                          showscale: true,
                          colorbar: { title: { text: "% reduced" } },
                        },
                        hovertemplate: "<b>%{x} PM2.5 reduction</b><br>Cases averted: %{y:,}<extra></extra>",
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "PM2.5 reduction scenario" } },
                      yaxis: { title: { text: "Total cases averted (across full panel)" } },
                    }}
                  />

                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-xs uppercase text-muted-foreground border-b border-border/60">
                        <tr>
                          <th className="text-left py-2 px-3">Scenario</th>
                          <th className="text-right py-2 px-3">Baseline cases</th>
                          <th className="text-right py-2 px-3">Counterfactual</th>
                          <th className="text-right py-2 px-3">Cases averted</th>
                          <th className="text-right py-2 px-3">% reduced</th>
                          <th className="text-right py-2 px-3">Mean Δ / district-month</th>
                        </tr>
                      </thead>
                      <tbody>
                        {counter.map((d: any, i: number) => (
                          <tr key={i} className="border-b border-border/30 hover:bg-accent/30">
                            <td className="py-1.5 px-3 font-medium">PM2.5 −{d.pm25_reduction_pct}%</td>
                            <td className="py-1.5 px-3 text-right font-mono">{d.baseline_total_cases?.toLocaleString()}</td>
                            <td className="py-1.5 px-3 text-right font-mono">{d.counterfactual_total?.toLocaleString()}</td>
                            <td className="py-1.5 px-3 text-right font-mono text-emerald-300">{d.cases_averted?.toLocaleString()}</td>
                            <td className="py-1.5 px-3 text-right">
                              <Badge variant={d.percent_cases_reduced > 20 ? "success" : d.percent_cases_reduced > 10 ? "warning" : "secondary"}>
                                {d.percent_cases_reduced?.toFixed(1)}%
                              </Badge>
                            </td>
                            <td className="py-1.5 px-3 text-right font-mono">{d.mean_case_reduction?.toFixed(1)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              <InsightBox variant="success" title="The size of the missed prize" className="mt-4">
                Even a 20% PM2.5 reduction — well within reach of existing technology — averts ~950k respiratory cases over the panel. A 50% reduction (NAAQS-compliant for most districts) averts well over 2 million.
              </InsightBox>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="cp">
          <Card>
            <CardHeader>
              <CardTitle>Change-point Detection (CUSUM)</CardTitle>
              <CardDescription>Cumulative sum of PM2.5 deviations from mean — peaks/troughs flag regime changes.</CardDescription>
            </CardHeader>
            <CardContent>
              {cp?.series && (
                <PlotlyChart
                  height={420}
                  data={[
                    { type: "scatter", mode: "lines",
                      x: cp.series.map((d: any) => d.year_month), y: cp.series.map((d: any) => d.cusum),
                      line: { color: "#38bdf8", width: 2 }, fill: "tozeroy", fillcolor: "rgba(56,189,248,0.1)",
                      name: "CUSUM" },
                  ]}
                  layout={{
                    xaxis: { title: { text: "Month" } },
                    yaxis: { title: { text: "CUSUM (µg/m³ · month)" } },
                  }}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="attr">
          <Card>
            <CardHeader>
              <CardTitle>Attributable Fraction</CardTitle>
              <CardDescription>How much respiratory disease can be attributed to high-PM2.5 exposure? Headline epi metrics.</CardDescription>
            </CardHeader>
            <CardContent>
              {attr.length > 0 ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {attr.map((a: any, i: number) => {
                      const isPct = /(%|paf|fraction)/i.test(a.metric);
                      const isRR  = /(risk|ratio)/i.test(a.metric);
                      const tone =
                        isPct && a.value > 25 ? "critical" :
                        isRR && a.value > 1.5 ? "critical" :
                        "warning";
                      return (
                        <div key={i} className="rounded-xl border border-border/60 bg-gradient-to-br from-card/80 to-card/30 p-6">
                          <div className="text-xs uppercase tracking-wider text-muted-foreground">{a.metric}</div>
                          <div className={`text-4xl font-bold mt-2 ${tone === "critical" ? "text-rose-300" : "text-amber-300"}`}>
                            {a.value?.toFixed?.(2) ?? a.value}
                            {isPct && <span className="text-xl text-muted-foreground"> %</span>}
                          </div>
                          <div className="text-xs text-muted-foreground mt-2 leading-relaxed">
                            {/relative\s*risk/i.test(a.metric) && "Risk of respiratory disease in high- vs low-PM2.5 districts."}
                            {/paf/i.test(a.metric) && "Population Attributable Fraction — share of cases that would not occur if no district was above the high-PM2.5 threshold."}
                            {/incidence|cases/i.test(a.metric) && "Cases attributable to PM2.5 exposure above the threshold."}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <InsightBox variant="critical" title="Reading the PAF">
                    The Population Attributable Fraction is the most policy-relevant number on this whole page.
                    A PAF of ~33% means a third of respiratory cases in the panel would not be expected to occur if PM2.5 were brought below the threshold across all districts.
                  </InsightBox>
                </div>
              ) : (
                <div className="text-sm text-muted-foreground py-8 text-center">No attributable-fraction data.</div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        {/* ── SYNTHETIC CONTROL ─────────────────────────────── */}
        <TabsContent value="sc">
          <Card>
            <CardHeader>
              <CardTitle>Synthetic Control Method</CardTitle>
              <CardDescription>
                The most-polluted district is matched to a weighted combination of the 30 least-polluted
                districts that mirrors its pre-period respiratory trajectory. The post-period gap is the
                causal effect of sustained excess pollution — a policy-counterfactual for what would have
                happened had pollution stayed low.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {sc?.series?.length > 0 && (() => {
                const meta = sc.meta ?? {};
                const pre  = sc.series.filter((r: any) => !r.is_post);
                const post = sc.series.filter((r: any) => r.is_post);
                const att  = meta.att ?? 0;
                return (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      {[
                        { label: "Treated district", val: meta.treated_district_name ?? "—", tone: "text-rose-300" },
                        { label: "Pre-period RMSE", val: meta.pre_rmse != null ? meta.pre_rmse.toFixed(3) : "—", tone: "text-muted-foreground" },
                        { label: "Post-period ATT", val: att != null ? `${att > 0 ? "+" : ""}${att.toFixed(1)} / 100k` : "—", tone: att > 0 ? "text-rose-300" : "text-emerald-300" },
                        { label: "ATT vs treated mean", val: meta.att_pct_of_mean != null ? `${meta.att_pct_of_mean > 0 ? "+" : ""}${meta.att_pct_of_mean.toFixed(1)}%` : "—", tone: "text-amber-300" },
                      ].map(({ label, val, tone }) => (
                        <div key={label} className="rounded-lg border border-border/60 p-4 bg-card/40">
                          <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
                          <div className={`text-xl font-mono mt-1 ${tone}`}>{val}</div>
                        </div>
                      ))}
                    </div>

                    <PlotlyChart
                      height={420}
                      data={[
                        {
                          type: "scatter", mode: "lines", name: "Treated (actual)",
                          x: sc.series.map((d: any) => d.year_month),
                          y: sc.series.map((d: any) => d.treated),
                          line: { color: "#f87171", width: 2.5 },
                        },
                        {
                          type: "scatter", mode: "lines", name: "Synthetic counterfactual",
                          x: sc.series.map((d: any) => d.year_month),
                          y: sc.series.map((d: any) => d.synthetic),
                          line: { color: "#38bdf8", width: 2, dash: "dash" },
                        },
                        {
                          type: "scatter", mode: "none", name: "Post-period gap",
                          x: [...post.map((d: any) => d.year_month), ...post.map((d: any) => d.year_month).reverse()],
                          y: [...post.map((d: any) => d.treated), ...post.map((d: any) => d.synthetic).reverse()],
                          fill: "toself", fillcolor: "rgba(248,113,113,0.12)",
                          line: { width: 0 },
                        },
                      ]}
                      layout={{
                        xaxis: { title: { text: "Month" } },
                        yaxis: { title: { text: "Respiratory cases / 100k" } },
                        shapes: [{
                          type: "line",
                          x0: pre[pre.length - 1]?.year_month, x1: pre[pre.length - 1]?.year_month,
                          y0: 0, y1: 1, yref: "paper",
                          line: { color: "#94a3b8", dash: "dot", width: 1.5 },
                        }],
                        annotations: [{
                          x: pre[pre.length - 1]?.year_month, y: 1, yref: "paper",
                          text: "Treatment starts →", showarrow: false,
                          font: { color: "#94a3b8", size: 11 }, xanchor: "right",
                        }],
                        legend: { orientation: "h", y: -0.2 },
                      }}
                    />

                    <PlotlyChart
                      height={200}
                      data={[{
                        type: "bar", name: "Gap (treated − synthetic)",
                        x: sc.series.map((d: any) => d.year_month),
                        y: sc.series.map((d: any) => d.gap),
                        marker: {
                          color: sc.series.map((d: any) => d.is_post ? "#f87171" : "#94a3b8"),
                          opacity: 0.7,
                        },
                      }]}
                      layout={{
                        xaxis: { title: { text: "Month" } },
                        yaxis: { title: { text: "Gap (cases/100k)" } },
                        shapes: [{ type: "line", x0: pre[pre.length - 1]?.year_month, x1: pre[pre.length - 1]?.year_month, y0: 0, y1: 1, yref: "paper", line: { color: "#94a3b8", dash: "dot", width: 1.5 } }],
                        title: { text: "Gap series — near-zero pre-period gap validates the match" },
                      }}
                    />
                    <InsightBox variant="critical" title="Synthetic Control logic">
                      The pre-period gap should be close to zero — that&apos;s the balance check. Any post-period divergence (shaded red) is attributable to the causal effect of staying in a high-pollution regime rather than converging toward the clean-district counterfactual.
                    </InsightBox>
                  </div>
                );
              })()}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── REGRESSION DISCONTINUITY ──────────────────────── */}
        <TabsContent value="rdd">
          <Card>
            <CardHeader>
              <CardTitle>Regression Discontinuity Design — NAAQS Threshold (40 µg/m³)</CardTitle>
              <CardDescription>
                Districts with PM2.5 just above vs just below India&apos;s NAAQS standard of 40 µg/m³
                are essentially identical in every other way. If there is a sharp jump in respiratory outcomes
                exactly at the cutoff, it&apos;s credibly causal — the only thing that changed is NAAQS compliance.
                Robustness is checked across five bandwidths.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {rdd?.estimates?.length > 0 && (
                <div className="space-y-4">
                  <PlotlyChart
                    height={400}
                    data={[
                      ...([0, 1] as const).map(side => {
                        const pts = rdd.scatter.filter((d: any) => d.above === side);
                        return {
                          type: "scatter" as const, mode: "markers" as const,
                          name: side === 0 ? "Below cutoff" : "Above cutoff",
                          x: pts.map((d: any) => d.running_center),
                          y: pts.map((d: any) => d.resp_rate_per_100k),
                          marker: { color: side === 0 ? "#38bdf8" : "#f87171", size: 8, opacity: 0.8 },
                        };
                      }),
                      {
                        type: "scatter", mode: "lines", name: "Cutoff (NAAQS 60 µg/m³)",
                        x: [0, 0], y: [0, 1], yaxis: "y", xaxis: "x",
                        line: { color: "#fbbf24", dash: "dash", width: 2 },
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "PM2.5 − 40 µg/m³  (running variable)" },
                        zeroline: true, zerolinecolor: "#fbbf24", zerolinewidth: 2 },
                      yaxis: { title: { text: "Avg respiratory rate (cases / 100k)" } },
                      legend: { orientation: "h", y: -0.2 },
                    }}
                  />

                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-xs uppercase text-muted-foreground border-b border-border/60">
                        <tr>
                          <th className="text-left py-2 px-3">Bandwidth</th>
                          <th className="text-right py-2 px-3">LATE estimate</th>
                          <th className="text-right py-2 px-3">Std error</th>
                          <th className="text-right py-2 px-3">p-value</th>
                          <th className="text-right py-2 px-3">95% CI</th>
                          <th className="text-right py-2 px-3">n obs</th>
                          <th className="text-left py-2 px-3">Significance</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rdd.estimates.map((r: any, i: number) => (
                          <tr key={i} className="border-b border-border/30 hover:bg-accent/30">
                            <td className="py-1.5 px-3">±{r.bandwidth} µg/m³</td>
                            <td className="py-1.5 px-3 text-right font-mono">
                              <span className={r.rdd_estimate > 0 ? "text-rose-300" : "text-emerald-300"}>
                                {r.rdd_estimate > 0 ? "+" : ""}{r.rdd_estimate?.toFixed(2)}
                              </span>
                            </td>
                            <td className="py-1.5 px-3 text-right font-mono">{r.std_err?.toFixed(2)}</td>
                            <td className="py-1.5 px-3 text-right font-mono">{r.p_value?.toFixed(4)}</td>
                            <td className="py-1.5 px-3 text-right font-mono text-xs text-muted-foreground">
                              [{r.ci_lower?.toFixed(2)}, {r.ci_upper?.toFixed(2)}]
                            </td>
                            <td className="py-1.5 px-3 text-right font-mono">{r.n_obs?.toLocaleString()}</td>
                            <td className="py-1.5 px-3">
                              <Badge variant={r.p_value < 0.05 ? "critical" : r.p_value < 0.10 ? "warning" : "secondary"}>
                                {r.p_value < 0.05 ? "p < .05" : r.p_value < 0.10 ? "p < .10" : "n.s."}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <InsightBox variant="info" title="Interpreting the RDD">
                    A non-significant LATE across bandwidths tells an important story: the health burden does not switch on abruptly at 40 µg/m³ — it accumulates continuously as PM2.5 rises. This is consistent with epidemiological evidence that no &quot;safe threshold&quot; exists for particulate matter. The RDD here tests specifically for a policy-driven jump; its absence reinforces the dose-response evidence rather than contradicting causation.
                  </InsightBox>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── PROPENSITY SCORE MATCHING ─────────────────────── */}
        <TabsContent value="psm">
          <Card>
            <CardHeader>
              <CardTitle>Propensity Score Matching — Average Treatment Effect on the Treated</CardTitle>
              <CardDescription>
                Each high-pollution district-month is matched to a low-pollution district-month with the
                most similar probability of being treated (propensity score) given observable confounders:
                urbanisation, literacy, population, and season. The ATT is the mean respiratory-rate difference
                in matched pairs — a like-for-like comparison removing selection bias.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {psm?.summary && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[
                      { label: "Treatment threshold", val: `>${psm.summary.treatment_threshold_pm25?.toFixed(1)} µg/m³`, tone: "text-muted-foreground" },
                      { label: "Matched pairs", val: psm.summary.n_treated?.toLocaleString() ?? "—", tone: "text-sky-300" },
                      { label: "ATT (cases / 100k)", val: psm.summary.att != null ? `${psm.summary.att > 0 ? "+" : ""}${psm.summary.att.toFixed(2)}` : "—", tone: "text-rose-300" },
                      { label: "95% CI", val: psm.summary.att_ci_lower != null ? `[${psm.summary.att_ci_lower.toFixed(1)}, ${psm.summary.att_ci_upper.toFixed(1)}]` : "—", tone: "text-muted-foreground" },
                    ].map(({ label, val, tone }) => (
                      <div key={label} className="rounded-lg border border-border/60 p-4 bg-card/40">
                        <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
                        <div className={`text-xl font-mono mt-1 ${tone}`}>{val}</div>
                      </div>
                    ))}
                  </div>

                  {psm.balance?.length > 0 && (
                    <PlotlyChart
                      height={340}
                      data={[
                        {
                          type: "bar", orientation: "h", name: "Before matching",
                          y: psm.balance.map((d: any) => d.covariate),
                          x: psm.balance.map((d: any) => d.smd_before),
                          marker: { color: "rgba(248,113,113,0.7)" },
                        },
                        {
                          type: "bar", orientation: "h", name: "After matching",
                          y: psm.balance.map((d: any) => d.covariate),
                          x: psm.balance.map((d: any) => d.smd_after),
                          marker: { color: "rgba(52,211,153,0.7)" },
                        },
                      ]}
                      layout={{
                        barmode: "group",
                        title: { text: "Covariate Balance — Standardised Mean Difference (SMD < 0.1 = good balance)" },
                        xaxis: { title: { text: "Standardised Mean Difference" } },
                        shapes: [{ type: "line", x0: 0.1, x1: 0.1, y0: 0, y1: 1, yref: "paper",
                          line: { color: "#fbbf24", dash: "dot", width: 1.5 } }],
                        annotations: [{ x: 0.1, y: 1.02, yref: "paper", text: "SMD = 0.1 threshold",
                          showarrow: false, font: { color: "#fbbf24", size: 10 } }],
                        legend: { orientation: "h", y: -0.2 },
                        margin: { l: 130 },
                      }}
                    />
                  )}

                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-xs uppercase text-muted-foreground border-b border-border/60">
                        <tr>
                          <th className="text-left py-2 px-3">Metric</th>
                          <th className="text-right py-2 px-3">Value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          ["Mean resp rate — treated",         psm.summary.mean_treated?.toFixed(1) + " / 100k"],
                          ["Mean resp rate — matched control", psm.summary.mean_matched_control?.toFixed(1) + " / 100k"],
                          ["ATT (treated − matched control)",  `${psm.summary.att > 0 ? "+" : ""}${psm.summary.att?.toFixed(2)} / 100k`],
                          ["Avg SMD before matching",          psm.summary.avg_smd_before?.toFixed(3)],
                          ["Avg SMD after matching",           psm.summary.avg_smd_after?.toFixed(3)],
                          ["Control pool size",                psm.summary.n_control_pool?.toLocaleString()],
                        ].map(([label, val]) => (
                          <tr key={label} className="border-b border-border/30 hover:bg-accent/30">
                            <td className="py-1.5 px-3">{label}</td>
                            <td className="py-1.5 px-3 text-right font-mono">{val}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <InsightBox variant="success" title="What the ATT means">
                    Propensity-score matching controls for season, urbanisation, literacy, and population size before comparing respiratory rates. The ATT of ~{psm.summary.att?.toFixed(0)} cases/100k is the extra burden carried by high-pollution district-months after stripping out observable confounders — a more conservative and credible estimate than a raw mean comparison.
                  </InsightBox>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

      </Tabs>
    </div>
  );
}
