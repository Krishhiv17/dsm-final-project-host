"""
FastAPI backend for the Air Quality & Public Health analytics platform.
Run:    uvicorn api.main:app --reload --port 8000
"""
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import overview, timeseries, correlations, clusters, graph, causal, advanced, predict, chat

app = FastAPI(
    title="Air Quality & Public Health API",
    description="Backend for the DSM Final Project — pollution / disease / graph analytics",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "service": "Air Quality & Public Health API",
        "status":  "ok",
        "endpoints": [
            "/overview/kpis", "/overview/states", "/overview/seasonality",
            "/timeseries", "/timeseries/districts",
            "/correlations/scatter", "/correlations/heatmap",
            "/clusters",
            "/graph/nodes", "/graph/edges", "/graph/communities",
            "/graph/spatial-autocorr", "/graph/knowledge", "/graph/link-prediction",
            "/graph/centrality-top",
            "/causal/granger-within", "/causal/cross-correlation",
            "/causal/dose-response", "/causal/counterfactual",
            "/causal/changepoint", "/causal/attributable", "/causal/var-forecast",
            "/advanced/pca", "/advanced/mediation", "/advanced/panel-fe",
            "/advanced/gwr", "/advanced/epi-metrics",
            "/advanced/partial-correlation", "/advanced/spatial-lag",
            "/predict",
            "/chat",
        ],
    }


app.include_router(overview.router)
app.include_router(timeseries.router)
app.include_router(correlations.router)
app.include_router(clusters.router)
app.include_router(graph.router)
app.include_router(causal.router)
app.include_router(advanced.router)
app.include_router(predict.router)
app.include_router(chat.router)
