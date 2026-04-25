"use client";
import { useState } from "react";
import { Sparkles, AlertTriangle, TrendingUp } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { InsightBox } from "@/components/insight-box";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { predict } from "@/lib/api";
import { formatNumber } from "@/lib/utils";

interface Inputs {
  pm25: number; pm10: number; no2: number; so2: number;
  urban_percentage: number; literacy_rate: number; population: number;
}

const PRESETS: Record<string, Inputs> = {
  "Delhi (Critical)":      { pm25: 130, pm10: 220, no2: 60, so2: 18, urban_percentage: 95, literacy_rate: 86, population: 1500000 },
  "Lucknow (High)":        { pm25: 90,  pm10: 165, no2: 40, so2: 12, urban_percentage: 60, literacy_rate: 77, population: 800000  },
  "Mumbai (Moderate)":     { pm25: 50,  pm10: 95,  no2: 35, so2: 10, urban_percentage: 88, literacy_rate: 90, population: 2000000 },
  "Bengaluru (Lower)":     { pm25: 35,  pm10: 70,  no2: 28, so2: 8,  urban_percentage: 80, literacy_rate: 88, population: 1500000 },
  "Kerala District":       { pm25: 22,  pm10: 45,  no2: 18, so2: 5,  urban_percentage: 35, literacy_rate: 95, population: 600000  },
};

const RISK_TONE: Record<string, "critical" | "warning" | "info" | "success"> = {
  Critical: "critical", High: "warning", Moderate: "info", Low: "success",
};

export default function PredictPage() {
  const [inp, setInp] = useState<Inputs>(PRESETS["Lucknow (High)"]);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    try { setResult(await predict(inp)); }
    catch (e) { console.error(e); }
    setLoading(false);
  }

  function set<K extends keyof Inputs>(k: K, v: Inputs[K]) { setInp(prev => ({ ...prev, [k]: v })); }

  return (
    <div className="space-y-8">
      <PageHeader badge="Predictor" title="Health Impact Predictor"
        subtitle="A Random Forest trained on the full panel (R² = 0.81). Move the sliders to simulate any district scenario and see the predicted respiratory burden." />

      <div className="flex flex-wrap gap-2">
        {Object.entries(PRESETS).map(([name, vals]) => (
          <Button key={name} variant="outline" size="sm" onClick={() => { setInp(vals); setResult(null); }}>
            {name}
          </Button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>District Inputs</CardTitle>
            <CardDescription>Drag sliders to set the scenario.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <SliderRow label="PM2.5 (µg/m³)" value={inp.pm25} min={5} max={250} step={1} onChange={v => set("pm25", v)} threshold={40} />
            <SliderRow label="PM10 (µg/m³)" value={inp.pm10} min={10} max={400} step={1} onChange={v => set("pm10", v)} threshold={60} />
            <SliderRow label="NO₂ (µg/m³)" value={inp.no2} min={5} max={150} step={1} onChange={v => set("no2", v)} threshold={40} />
            <SliderRow label="SO₂ (µg/m³)" value={inp.so2} min={1} max={80} step={1} onChange={v => set("so2", v)} threshold={50} />
            <SliderRow label="Urban %" value={inp.urban_percentage} min={0} max={100} step={1} onChange={v => set("urban_percentage", v)} />
            <SliderRow label="Literacy Rate %" value={inp.literacy_rate} min={40} max={100} step={1} onChange={v => set("literacy_rate", v)} />
            <SliderRow label="Population" value={inp.population} min={100_000} max={5_000_000} step={50_000} onChange={v => set("population", v)} formatter={formatNumber} />

            <Button className="w-full" size="lg" onClick={run} disabled={loading}>
              <Sparkles className="w-4 h-4" />
              {loading ? "Predicting…" : "Predict Respiratory Cases"}
            </Button>
          </CardContent>
        </Card>

        <div className="space-y-4">
          {result ? (
            <>
              <Card className="surface-elevated">
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-primary" />
                    Predicted Outcome
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wider">Respiratory cases / month</div>
                    <div className="text-4xl font-bold gradient-text-warm mt-1">{formatNumber(result.predicted_cases)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wider">Rate per 100k</div>
                    <div className="text-2xl font-mono mt-1">{result.rate_per_100k}</div>
                  </div>
                  <div className="flex items-center gap-2 pt-2 border-t border-border/50">
                    <span className="text-xs text-muted-foreground">Risk:</span>
                    <Badge variant={RISK_TONE[result.risk_level]}>{result.risk_level}</Badge>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">vs National Baseline</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-muted-foreground">National avg</span>
                    <span className="font-mono">{formatNumber(result.national_avg)}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">This district</span>
                    <span className="font-mono">{formatNumber(result.predicted_cases)}</span></div>
                  <div className="flex justify-between pt-2 border-t border-border/50"><span className="text-muted-foreground">Difference</span>
                    <Badge variant={result.pct_vs_baseline > 30 ? "critical" : result.pct_vs_baseline > 0 ? "warning" : "success"}>
                      {result.pct_vs_baseline > 0 ? "+" : ""}{result.pct_vs_baseline}%
                    </Badge>
                  </div>
                </CardContent>
              </Card>
            </>
          ) : (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground text-sm">
                <AlertTriangle className="w-6 h-6 mx-auto mb-3 opacity-50" />
                Set inputs and click Predict.
              </CardContent>
            </Card>
          )}

          <InsightBox variant="info" title="Model context">
            Random Forest, R² = 0.81, MAE = 181 cases / month. Trained on ~10,000 district-month observations.
          </InsightBox>
        </div>
      </div>
    </div>
  );
}

function SliderRow({ label, value, min, max, step, onChange, threshold, formatter }: {
  label: string; value: number; min: number; max: number; step: number;
  onChange: (v: number) => void; threshold?: number; formatter?: (n: number) => string;
}) {
  const display = formatter ? formatter(value) : value.toString();
  const overThreshold = threshold !== undefined && value > threshold;
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="text-sm font-medium">{label}</label>
        <span className={`font-mono text-sm ${overThreshold ? "text-rose-300" : "text-foreground"}`}>{display}</span>
      </div>
      <Slider value={[value]} onValueChange={(v) => onChange(v[0])} min={min} max={max} step={step} />
    </div>
  );
}
