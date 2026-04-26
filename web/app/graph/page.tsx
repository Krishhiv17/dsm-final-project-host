"use client";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { DeckMap } from "@/components/deck-map";
import { PlotlyChart } from "@/components/plot";
import { InsightBox } from "@/components/insight-box";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import {
  getGraphNodes, getGraphEdges, getCommunities, getMoransI,
  getKnowledgeGraph, getLinkPrediction, getCentralityTop,
} from "@/lib/api";

const COMMUNITY_COLORS: Record<number, string> = {
  0: "#38bdf8", 1: "#34d399", 2: "#fbbf24", 3: "#f87171",
  4: "#a78bfa", 5: "#f472b6", 6: "#22d3ee",
};

export default function GraphPage() {
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<any[]>([]);
  const [communities, setCommunities] = useState<any[]>([]);
  const [moran, setMoran] = useState<any[]>([]);
  const [colorBy, setColorBy] = useState<"community" | "pm25_mean" | "resp_rate_mean">("community");
  const [kg, setKg] = useState<any>(null);
  const [linkPred, setLinkPred] = useState<any[]>([]);
  const [centrality, setCentrality] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([
      getGraphNodes(), getGraphEdges(), getCommunities(), getMoransI(),
      getKnowledgeGraph(), getLinkPrediction(20), getCentralityTop("betweenness_centrality"),
    ]).then(([n, e, c, m, k, lp, ct]) => {
      setNodes(n); setEdges(e); setCommunities(c); setMoran(m);
      setKg(k); setLinkPred(lp); setCentrality(ct);
    }).catch(console.error);
  }, []);

  return (
    <div className="space-y-8">
      <PageHeader badge="Disease Propagation Graph"
        title="The Spatial Network of Pollution"
        subtitle="Districts wired together by similarity in air-quality and health profile. Communities (colours) reveal cross-state pollution zones that policy keeps ignoring." />

      <Tabs defaultValue="map">
        <TabsList className="mb-2">
          <TabsTrigger value="map">3D Map</TabsTrigger>
          <TabsTrigger value="communities">Communities</TabsTrigger>
          <TabsTrigger value="centrality">Centrality</TabsTrigger>
          <TabsTrigger value="moran">Spatial autocorrelation</TabsTrigger>
          <TabsTrigger value="knowledge">Knowledge graph</TabsTrigger>
          <TabsTrigger value="prediction">Link prediction</TabsTrigger>
        </TabsList>

        <TabsContent value="map">
          <Card>
            <CardHeader className="flex-row justify-between items-center">
              <div>
                <CardTitle>Disease Propagation Map</CardTitle>
                <CardDescription>Edges = high-similarity district pairs · Node size = betweenness centrality.</CardDescription>
              </div>
              <div className="flex gap-2 text-xs">
                {(["community", "pm25_mean", "resp_rate_mean"] as const).map(opt => (
                  <button key={opt} onClick={() => setColorBy(opt)}
                    className={`px-3 py-1.5 rounded-md border transition-colors ${
                      colorBy === opt ? "bg-primary/10 border-primary/30 text-primary" : "border-border text-muted-foreground hover:bg-accent"
                    }`}>
                    {opt === "community" ? "Community" : opt === "pm25_mean" ? "PM2.5" : "Resp. rate"}
                  </button>
                ))}
              </div>
            </CardHeader>
            <CardContent>
              {nodes.length > 0 && <DeckMap nodes={nodes} edges={edges} colorBy={colorBy} height={620} />}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="communities" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {communities.map((c: any) => (
              <Card key={c.community} className="relative overflow-hidden">
                <div className="absolute top-0 left-0 w-full h-1" style={{ background: COMMUNITY_COLORS[c.community] || "#94a3b8" }} />
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">Community {c.community}</CardTitle>
                    {c.cross_state && <Badge variant="warning">Cross-state</Badge>}
                  </div>
                  <CardDescription>{c.n_districts} districts · {c.n_states} states</CardDescription>
                </CardHeader>
                <CardContent className="text-sm space-y-2">
                  <div className="text-muted-foreground text-xs leading-relaxed">{c.states}</div>
                  <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border/50">
                    <div><span className="text-muted-foreground text-xs">PM2.5</span><div className="font-mono">{c.avg_pm25?.toFixed(1)}</div></div>
                    <div><span className="text-muted-foreground text-xs">Resp rate</span><div className="font-mono">{c.avg_resp_rate?.toFixed(0)}</div></div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
          <InsightBox variant="warning" title="Pollution doesn&apos;t respect borders">
            Cross-state communities (badge above) prove that contiguous districts share pollution dynamics regardless of which state administers them. Policy designed at state level misses this entirely.
          </InsightBox>
        </TabsContent>

        <TabsContent value="centrality">
          <Card>
            <CardHeader>
              <CardTitle>Top 15 Bridge Districts</CardTitle>
              <CardDescription>Highest betweenness centrality — these districts sit on the most paths through the network. Intervention here has the largest cascading effect.</CardDescription>
            </CardHeader>
            <CardContent>
              {centrality.length > 0 && (
                <PlotlyChart
                  height={500}
                  data={[{
                    type: "bar", orientation: "h",
                    x: [...centrality].reverse().map(c => c.betweenness_centrality),
                    y: [...centrality].reverse().map(c => `${c.district_name} (${c.state})`),
                    marker: { color: "#38bdf8" },
                    hovertemplate: "<b>%{y}</b><br>Betweenness: %{x:.4f}<extra></extra>",
                  }]}
                  layout={{ xaxis: { title: { text: "Betweenness centrality" } }, margin: { l: 200, r: 30, t: 20, b: 50 } }}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="moran">
          <Card>
            <CardHeader>
              <CardTitle>Moran&apos;s I — Spatial Autocorrelation</CardTitle>
              <CardDescription>Tests whether values cluster geographically. I &gt; 0 means similar values are geographically near each other. p-values from 999-permutation Monte Carlo.</CardDescription>
            </CardHeader>
            <CardContent>
              {moran.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-xs uppercase text-muted-foreground border-b border-border/60">
                      <tr><th className="text-left py-2 px-3">Variable</th>
                          <th className="text-right py-2 px-3">Moran&apos;s I</th>
                          <th className="text-right py-2 px-3">Expected I</th>
                          <th className="text-right py-2 px-3">z-score</th>
                          <th className="text-right py-2 px-3">p-value (MC)</th>
                          <th className="text-left py-2 px-3">Interpretation</th></tr>
                    </thead>
                    <tbody>
                      {moran.map((m: any, i: number) => {
                        const I = m.morans_I ?? m.morans_i;
                        const p = m.p_value_mc ?? m.p_value;
                        return (
                          <tr key={i} className="border-b border-border/30">
                            <td className="py-2 px-3 font-medium">{m.variable}</td>
                            <td className="py-2 px-3 text-right font-mono">{I?.toFixed(4)}</td>
                            <td className="py-2 px-3 text-right font-mono text-muted-foreground">{m.expected_I?.toFixed(4) ?? "—"}</td>
                            <td className="py-2 px-3 text-right font-mono">{m.z_score?.toFixed(2) ?? "—"}</td>
                            <td className="py-2 px-3 text-right font-mono">{p != null && p < 1e-3 ? "< 0.001" : p?.toFixed(4)}</td>
                            <td className="py-2 px-3">
                              <Badge variant={I > 0.3 ? "critical" : I > 0.1 ? "warning" : "secondary"}>
                                {I > 0.3 ? "Strong clustering" : I > 0.1 ? "Moderate" : "Weak/random"}
                              </Badge>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              <InsightBox variant="info" title="Why this matters" className="mt-4">
                Strong positive Moran&apos;s I for PM2.5 confirms pollution spreads through contiguous neighbourhoods of districts — exactly the mechanism that justifies airshed-level policy.
              </InsightBox>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="knowledge">
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Relationship counts</CardTitle>
                  <CardDescription>How many edges of each typed relation are encoded in the KG.</CardDescription>
                </CardHeader>
                <CardContent>
                  {kg?.counts && kg.counts.length > 0 && (
                    <PlotlyChart
                      height={320}
                      data={[{
                        type: "bar", orientation: "h",
                        x: [...kg.counts].reverse().map((c: any) => c.count),
                        y: [...kg.counts].reverse().map((c: any) => c.relationship),
                        marker: {
                          color: [...kg.counts].reverse().map((c: any) => c.count),
                          colorscale: [[0, "#38bdf8"], [0.5, "#a78bfa"], [1, "#f472b6"]],
                        },
                        text: [...kg.counts].reverse().map((c: any) => c.count.toLocaleString()),
                        textposition: "outside",
                        hovertemplate: "<b>%{y}</b><br>%{x:,} edges<extra></extra>",
                      }]}
                      layout={{
                        xaxis: { title: { text: "edges" } },
                        margin: { l: 200, r: 50, t: 10, b: 40 },
                      }}
                    />
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Relationship mix</CardTitle>
                  <CardDescription>Share of each typed edge in the full KG.</CardDescription>
                </CardHeader>
                <CardContent>
                  {kg?.counts && kg.counts.length > 0 && (
                    <PlotlyChart
                      height={320}
                      data={[{
                        type: "pie",
                        labels: kg.counts.map((c: any) => c.relationship),
                        values: kg.counts.map((c: any) => c.count),
                        hole: 0.55,
                        marker: { colors: ["#38bdf8", "#34d399", "#fbbf24", "#f472b6", "#a78bfa"] },
                        textinfo: "label+percent",
                        hovertemplate: "<b>%{label}</b><br>%{value:,} edges (%{percent})<extra></extra>",
                      }]}
                      layout={{ showlegend: false, margin: { l: 20, r: 20, t: 20, b: 20 } }}
                    />
                  )}
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Top triples</CardTitle>
                <CardDescription>
                  (subject, relationship, object) — the structural shape of pollution-health knowledge.
                  Shown across all relationship types so you can see the full schema.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto max-h-[480px] scroll-area">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-card text-xs uppercase text-muted-foreground border-b border-border/60">
                      <tr>
                        <th className="text-left py-2 px-3">Subject</th>
                        <th className="text-left py-2 px-3">Relationship</th>
                        <th className="text-left py-2 px-3">Object</th>
                        <th className="text-right py-2 px-3">Weight</th>
                        <th className="text-left py-2 px-3">Metadata</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(kg?.triples || []).map((t: any, i: number) => (
                        <tr key={i} className="border-b border-border/30 hover:bg-accent/30">
                          <td className="py-1.5 px-3">
                            <div>{t.subject ?? t.source_id}</div>
                            {t.subject_state && <div className="text-xs text-muted-foreground">{t.subject_state}</div>}
                          </td>
                          <td className="py-1.5 px-3"><Badge variant="outline">{t.relationship}</Badge></td>
                          <td className="py-1.5 px-3">
                            <div>{t.object ?? t.target_id}</div>
                            {t.object_state && <div className="text-xs text-muted-foreground">{t.object_state}</div>}
                          </td>
                          <td className="py-1.5 px-3 text-right font-mono text-xs">{t.weight?.toFixed?.(3) ?? "—"}</td>
                          <td className="py-1.5 px-3 text-xs text-muted-foreground">{t.metadata ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="prediction" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Predicted Long-Range Pollution Corridors</CardTitle>
              <CardDescription>
                Arcs between districts that the model expects to behave similarly even though they aren&apos;t
                spatially adjacent. Color and width encode the combined Jaccard + Adamic-Adar score —
                deeper red / thicker = stronger predicted similarity. These are the latent connections that a
                geographic-only view of pollution misses.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {nodes.length > 0 && linkPred.length > 0 && (
                <DeckMap
                  nodes={nodes}
                  predictedEdges={linkPred}
                  showBaseEdges={false}
                  colorBy="community"
                  height={560}
                />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Top {linkPred.length} Predicted Future Edges</CardTitle>
              <CardDescription>Score = Jaccard + scaled Adamic-Adar over shared graph neighbours.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto max-h-[420px] scroll-area">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-card text-xs uppercase text-muted-foreground border-b border-border/60">
                    <tr>
                      <th className="text-left py-2 px-3">District A</th>
                      <th className="text-left py-2 px-3">District B</th>
                      <th className="text-right py-2 px-3">Jaccard</th>
                      <th className="text-right py-2 px-3">Adamic-Adar</th>
                      <th className="text-right py-2 px-3">Score</th>
                      <th className="text-left py-2 px-3">Same community</th>
                    </tr>
                  </thead>
                  <tbody>
                    {linkPred.map((l: any, i: number) => (
                      <tr key={i} className="border-b border-border/30 hover:bg-accent/30">
                        <td className="py-1.5 px-3">
                          <div>{l.name_a ?? l.district_a}</div>
                          {l.state_a && <div className="text-xs text-muted-foreground">{l.state_a}</div>}
                        </td>
                        <td className="py-1.5 px-3">
                          <div>{l.name_b ?? l.district_b}</div>
                          {l.state_b && <div className="text-xs text-muted-foreground">{l.state_b}</div>}
                        </td>
                        <td className="py-1.5 px-3 text-right font-mono">{l.jaccard?.toFixed(3) ?? "—"}</td>
                        <td className="py-1.5 px-3 text-right font-mono">{l.adamic_adar?.toFixed(3) ?? "—"}</td>
                        <td className="py-1.5 px-3 text-right font-mono text-amber-300">
                          {(l.combined_score ?? l.score ?? l.adamic_adar)?.toFixed?.(3) ?? "—"}
                        </td>
                        <td className="py-1.5 px-3">
                          <Badge variant={l.same_community ? "warning" : "secondary"}>
                            {l.same_community ? "Yes" : "Cross-community"}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <InsightBox variant="critical" title="Why long-range links matter">
            Most pollution edges in this graph are short-range (proximity). The predicted corridors connect
            districts hundreds of kilometres apart — Punjab ↔ Haryana, UP ↔ Rajasthan, etc. These are the
            airshed-level relationships that single-district interventions cannot break.
          </InsightBox>
        </TabsContent>
      </Tabs>
    </div>
  );
}
