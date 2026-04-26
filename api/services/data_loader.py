"""
Cached singleton data loader. Loads all processed CSVs once per process
and serves them to the routers.
"""
from __future__ import annotations
from pathlib import Path
from functools import lru_cache
import pandas as pd
import numpy as np
import pickle

PROJECT_ROOT  = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def _read(name: str) -> pd.DataFrame | None:
    p = PROCESSED_DIR / name
    if not p.exists():
        return None
    return pd.read_csv(p)


@lru_cache(maxsize=1)
def all_data() -> dict:
    """Load every processed CSV into a single dict."""
    merged    = _read("air_health_merged.csv")
    districts = _read("districts_clean.csv")
    aq        = _read("air_quality_clean.csv")
    health    = _read("health_clean.csv")
    geo       = _read("districts_geocoded.csv")
    clusters  = _read("district_clusters.csv")

    if merged is not None and "respiratory_cases" in merged.columns:
        merged["resp_rate_per_100k"] = (
            merged["respiratory_cases"] * 100_000 / merged["population"].replace(0, np.nan)
        )
        merged["year_month"] = pd.to_datetime(merged["year_month"], errors="coerce")

    if aq is not None and "date" in aq.columns:
        aq["date"] = pd.to_datetime(aq["date"], errors="coerce")

    return {
        "merged": merged,
        "districts": districts,
        "aq": aq,
        "health": health,
        "geo": geo,
        "clusters": clusters,
        # Graph & analysis outputs (may be None if scripts not yet run)
        "graph_nodes":      _read("graph_nodes.csv"),
        "graph_edges":      _read("graph_edges.csv"),
        "knowledge_graph":  _read("knowledge_graph.csv"),
        "link_prediction":  _read("link_prediction.csv"),
        "spatial_autocorr": _read("spatial_autocorr.csv"),
        "granger_neighbor": _read("granger_neighbor_results.csv"),
        # Causal inference
        "granger_within":       _read("granger_within_district.csv"),
        "dose_response":        _read("dose_response.csv"),
        "counterfactual":       _read("counterfactual.csv"),
        "changepoint":          _read("changepoint.csv"),
        "attributable":         _read("attributable_fraction.csv"),
        "var_forecast":         _read("var_forecast.csv"),
        # Research-grade counterfactuals
        "synthetic_control":    _read("synthetic_control.csv"),
        "synthetic_ctrl_meta":  _read("synthetic_control_meta.csv"),
        "rdd_results":          _read("rdd_results.csv"),
        "rdd_scatter":          _read("rdd_scatter.csv"),
        "psm_summary":          _read("psm_summary.csv"),
        "psm_balance":          _read("psm_balance.csv"),
        # Advanced stats
        "pca":              _read("pca_results.csv"),
        "mediation":        _read("mediation_results.csv"),
        "panel_fe":         _read("panel_fe_results.csv"),
        "gwr":              _read("gwr_region_results.csv"),
        "epi":              _read("epi_metrics.csv"),
        "partial_corr":     _read("partial_corr.csv"),
        "spatial_lag":      _read("spatial_lag_results.csv"),
    }


@lru_cache(maxsize=1)
def trained_model():
    """Train (and cache) the RandomForest predictor used by the predict endpoint."""
    from sklearn.ensemble import RandomForestRegressor
    data = all_data()
    merged = data["merged"]
    if merged is None:
        return None, None
    features = ["pm25", "pm10", "no2", "so2", "urban_percentage",
                "literacy_rate", "population"]
    df = merged[features + ["respiratory_cases"]].dropna()
    X = df[features].values
    y = df["respiratory_cases"].values
    model = RandomForestRegressor(n_estimators=100, max_depth=15,
                                  random_state=42, n_jobs=-1)
    model.fit(X, y)
    return model, features


def df_to_records(df: pd.DataFrame | None, replace_nan=None) -> list:
    """Safely convert a DataFrame to a list of dicts, replacing NaN with None or scalar."""
    if df is None or df.empty:
        return []
    out = df.copy()
    if replace_nan is None:
        out = out.where(pd.notnull(out), None)
    else:
        out = out.fillna(replace_nan)
    return out.to_dict(orient="records")
