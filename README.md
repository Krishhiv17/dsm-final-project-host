# Air Quality & Public Health in Indian Districts

**DSM Final Project** — A full data-science pipeline analysing the relationship between ambient
air quality (PM2.5, PM10, NO₂, SO₂) and public health outcomes (respiratory & cardiovascular
diseases) across **150 districts in 15 Indian states**, 2018–2023.

The project ships with **three** front-ends, all backed by the same processed data:

| Layer | Stack | Purpose |
|-------|-------|---------|
| **Web app** (primary) | Next.js 15 + Tailwind + shadcn/ui + react-plotly + deck.gl | Premium interactive dashboard with 11 pages including a long-form storytelling blog |
| **API** | FastAPI + pandas + scikit-learn | Backend that serves all data + the trained Random Forest predictor |
| **Streamlit** (legacy, still works) | Streamlit + plotly + pydeck | Original quick-iterate dashboard, kept as a fallback |

---

## Quick Start

### 0. One-time setup

```bash
# Python deps (Streamlit, pipeline scripts, FastAPI all share these)
pip install -r requirements.txt
pip install -r api/requirements.txt   # FastAPI-specific extras

# Build the data pipeline once (creates data/processed/* and db/air_health.db)
python src/01_data_collection.py
python src/02_eda.py
python src/03_database.py
python src/04_analysis.py
python src/05_graph_spatial.py
python src/06_causal_inference.py
python src/07_advanced_stats.py

# Web frontend deps
cd web && npm install && cd ..
```

### 1. Run the FastAPI backend (required for the Next.js app)

```bash
uvicorn api.main:app --reload --port 8000
```

Visit `http://localhost:8000/` — you'll see the list of endpoints. Try
`http://localhost:8000/overview/kpis` and `http://localhost:8000/correlations/scatter?x=pm25&y=respiratory_cases`.

### 2. Run the Next.js web app (premium dashboard)

```bash
cd web
npm run dev
```

Visit **`http://localhost:3000`**. The 11 pages in the sidebar are:

| Page | What it shows |
|------|---------------|
| Overview | KPIs, top-10 polluted states, seasonality strip |
| State Comparison | Bar ranking + bubble chart + full state table |
| Time-Series | District-level pollutant explorer (daily/weekly/monthly) |
| Correlations | Scatter + full correlation heatmap |
| District Clusters | K-Means risk groups + sortable district table |
| Seasonality | Pollutant + health monthly cycles |
| Health Predictor | Random-Forest sandbox with sliders |
| Disease Graph | 3D deck.gl spatial graph + communities + centrality + Moran's I + knowledge graph + link prediction |
| Causal Inference | Dose-response, cross-correlation, Granger, counterfactual, change-points, attributable fraction |
| Advanced Analytics | PCA, mediation, panel FE, GWR, partial corr., spatial lag, epi metrics |
| **The Story** | Long-form blog walking through raw → intermediate → final interpretations and policy recommendations |

If the API runs on a different host, set:

```bash
# web/.env.local
NEXT_PUBLIC_API_BASE=http://your-host:8000
```

### 3. Run the legacy Streamlit dashboard (optional)

```bash
streamlit run src/dashboard.py
```

The Streamlit app remains fully functional, including the AI Assistant page powered by Groq.

---

## Project Structure

```
dsm-final-project/
├── api/                          ← FastAPI backend
│   ├── main.py                   ← App + CORS + router registration
│   ├── routers/                  ← /overview /timeseries /correlations
│   │                                /clusters /graph /causal /advanced /predict
│   └── services/data_loader.py   ← Cached CSV loader + RF model trainer
│
├── web/                          ← Next.js 15 frontend
│   ├── app/
│   │   ├── page.tsx              ← Overview
│   │   ├── states/               ← State Comparison
│   │   ├── timeseries/
│   │   ├── correlations/
│   │   ├── clusters/
│   │   ├── seasonality/
│   │   ├── predict/              ← Health Predictor
│   │   ├── graph/                ← Disease Propagation Graph (deck.gl)
│   │   ├── causal/               ← Causal Inference
│   │   ├── advanced/             ← Advanced Analytics
│   │   ├── blog/                 ← The Story (long-form analysis)
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/               ← Sidebar, KPI cards, plot wrapper, deck-map, UI primitives
│   └── lib/api.ts                ← Typed API client
│
├── src/                          ← Pipeline + Streamlit
│   ├── 01_data_collection.py     ← NDAP / data.gov.in ingestion
│   ├── 02_eda.py                 ← Cleaning + EDA
│   ├── 03_database.py            ← SQLite schema + ingestion
│   ├── 04_analysis.py            ← Stats tests + ML models
│   ├── 05_graph_spatial.py       ← Graph construction + community detection
│   ├── 06_causal_inference.py    ← Granger, dose-response, counterfactual
│   ├── 07_advanced_stats.py      ← PCA, mediation, panel FE
│   ├── dashboard.py              ← Streamlit dashboard (legacy, still maintained)
│   ├── pages/                    ← Streamlit multi-page (3D map + AI Assistant)
│   └── chat/                     ← Groq-powered AI Assistant for Streamlit
│
├── data/
│   ├── raw/                      ← Source CSVs
│   └── processed/                ← Cleaned + analysis output CSVs
├── db/air_health.db              ← SQLite database
├── report/final_report.md        ← Written report
├── requirements.txt              ← Pipeline + Streamlit deps
└── api/requirements.txt          ← FastAPI-only deps
```

---

## Data Sources

| Dataset | Source | Records | Granularity |
|---------|--------|---------|-------------|
| Air Quality (CPCB) | NDAP / data.gov.in | ~328k | Daily × 150 districts |
| Health (HMIS) | data.gov.in | 10,800 | Monthly × 150 districts |
| Water Quality (JJM) | data.gov.in | 3,000 | Quarterly × 150 districts |
| District Demographics | Census / NDAP | 150 | Per district |

---

## Headline Findings

- **PM2.5 ↔ Respiratory cases**: r = 0.38 (p ≈ 0, n ≈ 10k district-months) — robust under
  t-test, Mann-Whitney, ANOVA, panel fixed-effects.
- **Random Forest**: R² = 0.81 on respiratory case prediction from air quality + demographics.
- **Cross-correlation**: peak at positive lag (pollution leads disease) — temporal precedence.
- **Cluster 3 is the surprise**: UP/Bihar districts with moderate PM2.5 (~70 µg/m³) but disease
  rates 2-3× higher than Delhi. Socioeconomic factors compound pollution's harm.
- **No improvement in 6 years**: National PM2.5 went from 58.9 (2018) → 59.0 (2023). Existing
  policy levers haven't moved the headline number.

For the full narrative — raw observations, intermediate findings, final interpretations, and
policy recommendations — see **`/blog`** in the web app.

---

## Tech Stack Summary

| Category | Tool |
|----------|------|
| Frontend | Next.js 15, React 18, Tailwind CSS, shadcn/ui, react-plotly.js, deck.gl, MapLibre |
| Backend | FastAPI, Uvicorn, pandas, scikit-learn, scipy, statsmodels, NetworkX |
| Legacy UI | Streamlit, Plotly, PyDeck |
| AI Chat | Groq (Llama 3.3 70B / Llama 3.1 8B) |
| Database | SQLite + SQLAlchemy |
| Language | Python 3.12, TypeScript 5.7 |

---

## Common Issues

- **Web app shows nothing / network errors** — make sure the FastAPI backend is running on port 8000
  (or update `NEXT_PUBLIC_API_BASE`).
- **Empty pages** — most analysis pages need `data/processed/*.csv` files; rerun the pipeline scripts
  in order if any are missing.
- **`groq` package not found** when running Streamlit's AI Assistant — install in the same Python
  interpreter Streamlit uses: `pyenv which python` then `<that path> -m pip install groq python-dotenv`.
