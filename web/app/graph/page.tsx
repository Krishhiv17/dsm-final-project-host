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
              <CardDescription>Tests whether values cluster geographically. I &gt; 0 means similar values are geographically near each other.</CardDescription>
            </CardHeader>
            <CardContent>
              {moran.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-xs uppercase text-muted-foreground border-b border-border/60">
                      <tr><th className="text-left py-2 px-3">Variable</th>
                          <th className="text-right py-2 px-3">Moran&apos;s I</th>
                          <th className="text-right py-2 px-3">p-value</th>
                          <th className="text-left py-2 px-3">Interpretation</th></tr>
                    </thead>
                    <tbody>
                      {moran.map((m: any, i: number) => (
                        <tr key={i} className="border-b border-border/30">
                          <td className="py-2 px-3 font-medium">{m.variable}</td>
                          <td className="py-2 px-3 text-right font-mono">{m.morans_i?.toFixed(4)}</td>
                          <td className="py-2 px-3 text-right font-mono">{m.p_value < 1e-4 ? "< 0.0001" : m.p_value?.toFixed(4)}</td>
                          <td className="py-2 px-3">
                            <Badge variant={m.morans_i > 0.3 ? "critical" : m.morans_i > 0.1 ? "warning" : "secondary"}>
                              {m.morans_i > 0.3 ? "Strong clustering" : m.morans_i > 0.1 ? "Moderate" : "Weak/random"}
                            </Badge>
                          </td>
                        </tr>
                      ))}
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
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle>Relationship counts</CardTitle>
              </CardHeader>
              <CardContent>
                {kg?.counts && (
                  <div className="space-y-2 text-sm">
                    {kg.counts.map((c: any, i: number) => (
                      <div key={i} className="flex justify-between items-center py-1.5 border-b border-border/30">
                        <span className="text-muted-foreground">{c.relationship}</span>
                        <Badge variant="secondary">{c.count}</Badge>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Top triples</CardTitle>
                <CardDescription>(subject, relationship, object) — the structural shape of pollution-health knowledge.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto max-h-[420px] scroll-area">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-card text-xs uppercase text-muted-foreground border-b border-border/60">
                      <tr><th className="text-left py-2 px-3">Subject</th><th className="text-left py-2 px-3">Relationship</th><th className="text-left py-2 px-3">Object</th></tr>
                    </thead>
                    <tbody>
                      {(kg?.triples || []).slice(0, 60).map((t: any, i: number) => (
                        <tr key={i} className="border-b border-border/30">
                          <td className="py-1.5 px-3">{t.subject}</td>
                          <td className="py-1.5 px-3"><Badge variant="outline">{t.relationship}</Badge></td>
                          <td className="py-1.5 px-3 text-muted-foreground">{t.object}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="prediction">
          <Card>
            <CardHeader>
              <CardTitle>Top 20 Predicted Future Edges</CardTitle>
              <CardDescription>Adamic-Adar / Jaccard scoring on the existing graph — district pairs that are likely to behave similarly even though they aren&apos;t connected today.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-xs uppercase text-muted-foreground border-b border-border/60">
                    <tr>
                      <th className="text-left py-2 px-3">District A</th>
                      <th className="text-left py-2 px-3">District B</th>
                      <th className="text-right py-2 px-3">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {linkPred.map((l: any, i: number) => (
                      <tr key={i} className="border-b border-border/30">
                        <td className="py-1.5 px-3">{l.district_a || l.source_name || l.source}</td>
                        <td className="py-1.5 px-3">{l.district_b || l.target_name || l.target}</td>
                        <td className="py-1.5 px-3 text-right font-mono">
                          {(l.score ?? l.adamic_adar ?? l.weight)?.toFixed?.(3) ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
