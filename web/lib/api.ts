/**
 * Typed API client for the FastAPI backend.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...init,
    headers,
  });
  if (!res.ok) {
    throw new Error(`API ${path} → ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ── Overview ─────────────────────────────────────────────────────────
export async function getKPIs() {
  return fetchJSON<{
    avg_pm25: number; max_pm25: number;
    total_respiratory: number; total_cardiovascular: number;
    num_districts: number; num_states: number;
    date_range_start: string; date_range_end: string;
  }>("/overview/kpis");
}
export async function getStates() {
  return fetchJSON<any[]>("/overview/states");
}
export async function getSeasonality() {
  return fetchJSON<{ pollution: any[]; health: any[] }>("/overview/seasonality");
}

// ── Time series ──────────────────────────────────────────────────────
export async function getDistricts() { return fetchJSON<any[]>("/timeseries/districts"); }
export async function getTimeseries(district_id: number, pollutant: string, aggregation: string) {
  return fetchJSON<any[]>(`/timeseries?district_id=${district_id}&pollutant=${pollutant}&aggregation=${aggregation}`);
}

// ── Correlations ─────────────────────────────────────────────────────
export async function getScatter(x: string, y: string) {
  return fetchJSON<{ data: any[]; stats: { pearson_r: number; p_value: number; n: number } }>(
    `/correlations/scatter?x=${x}&y=${y}`
  );
}
export async function getHeatmap() {
  return fetchJSON<{ vars: string[]; matrix: number[][] }>("/correlations/heatmap");
}
export async function getScatter3D(x: string, y: string, z: string) {
  return fetchJSON<{ data: any[]; stats: { n: number; x_var: string; y_var: string; z_var: string } }>(
    `/correlations/scatter3d?x=${x}&y=${y}&z=${z}`
  );
}

// ── Clusters ─────────────────────────────────────────────────────────
export async function getClusters() {
  return fetchJSON<{ clusters: any[]; summary: any[] }>("/clusters");
}

// ── Graph ────────────────────────────────────────────────────────────
export async function getGraphNodes() { return fetchJSON<any[]>("/graph/nodes"); }
export async function getGraphEdges()  { return fetchJSON<any[]>("/graph/edges?limit=1500"); }
export async function getCommunities() { return fetchJSON<any[]>("/graph/communities"); }
export async function getMoransI()     { return fetchJSON<any[]>("/graph/spatial-autocorr"); }
export async function getKnowledgeGraph(rel?: string) {
  const q = rel ? `?relationship=${rel}` : "";
  return fetchJSON<{ counts: any[]; triples: any[] }>(`/graph/knowledge${q}`);
}
export async function getLinkPrediction(top_n = 150) {
  return fetchJSON<any[]>(`/graph/link-prediction?top_n=${top_n}`);
}
export async function getCentralityTop(metric = "betweenness_centrality") {
  return fetchJSON<any[]>(`/graph/centrality-top?metric=${metric}&top_n=15`);
}

// ── Causal ───────────────────────────────────────────────────────────
export async function getGrangerWithin()    { return fetchJSON<any[]>("/causal/granger-within"); }
export async function getCrossCorrelation() { return fetchJSON<any[]>("/causal/cross-correlation"); }
export async function getDoseResponse()     { return fetchJSON<any[]>("/causal/dose-response"); }
export async function getCounterfactual()   { return fetchJSON<any[]>("/causal/counterfactual"); }
export async function getChangePoint()      { return fetchJSON<{ series: any[]; changepoints: any[] }>("/causal/changepoint"); }
export async function getAttributable()     { return fetchJSON<any[]>("/causal/attributable"); }
export async function getSyntheticControl() {
  return fetchJSON<{ series: any[]; meta: any }>("/causal/synthetic-control");
}
export async function getRDD() {
  return fetchJSON<{ estimates: any[]; scatter: any[] }>("/causal/rdd");
}
export async function getPSM() {
  return fetchJSON<{ summary: any; balance: any[] }>("/causal/psm");
}

// ── Advanced stats ───────────────────────────────────────────────────
export async function getPCA()               { return fetchJSON<{ sample: any[]; n_total: number }>("/advanced/pca"); }
export async function getMediation()         { return fetchJSON<any>("/advanced/mediation"); }
export async function getPanelFE()           { return fetchJSON<any[]>("/advanced/panel-fe"); }
export async function getGWR()               { return fetchJSON<any[]>("/advanced/gwr"); }
export async function getEpiMetrics()        { return fetchJSON<any[]>("/advanced/epi-metrics"); }
export async function getPartialCorrelation(){ return fetchJSON<any>("/advanced/partial-correlation"); }
export async function getSpatialLag()        { return fetchJSON<any[]>("/advanced/spatial-lag"); }

// ── Chat ─────────────────────────────────────────────────────────────
export interface ChatMessage { role: "user" | "assistant"; content: string; }
export async function sendChatMessage(messages: ChatMessage[]) {
  return fetchJSON<{ reply: string; queries: string[] }>("/chat/message", {
    method: "POST",
    body: JSON.stringify({ messages }),
  });
}

// ── Predict ──────────────────────────────────────────────────────────
export interface PredictionInput {
  pm25: number; pm10: number; no2: number; so2: number;
  urban_percentage: number; literacy_rate: number; population: number;
}
export async function predict(input: PredictionInput) {
  return fetchJSON<{
    predicted_cases: number; rate_per_100k: number;
    risk_level: string; national_avg: number; pct_vs_baseline: number;
  }>("/predict", { method: "POST", body: JSON.stringify(input) });
}
