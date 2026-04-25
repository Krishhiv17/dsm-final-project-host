"""Correlation & scatter-plot endpoints."""
from fastapi import APIRouter, Query
from typing import Literal
from scipy import stats
import numpy as np
from ..services.data_loader import all_data, df_to_records

router = APIRouter(prefix="/correlations", tags=["correlations"])

POLLUTANTS = ["pm25", "pm10", "no2", "so2", "aqi"]
HEALTH    = ["respiratory_cases", "cardiovascular_cases", "diarrhoea_cases"]
DEMO      = ["urban_percentage", "literacy_rate", "population"]


@router.get("/scatter")
def scatter(
    x: str = Query("pm25"),
    y: str = Query("respiratory_cases"),
    sample: int = Query(3000, le=5000),
):
    """Sampled scatter data + Pearson r/p for the correlations page."""
    d = all_data()
    merged = d["merged"]
    if merged is None or x not in merged.columns or y not in merged.columns:
        return {"data": [], "stats": {}}
    df = merged[[x, y, "state"]].dropna()
    if len(df) > sample:
        df = df.sample(sample, random_state=42)
    r, p = stats.pearsonr(df[x], df[y])
    return {
        "data": df_to_records(df.rename(columns={x: "x", y: "y"})),
        "stats": {
            "pearson_r": float(round(r, 4)),
            "p_value":   float(p),
            "n":         int(len(df)),
            "x_var":     x,
            "y_var":     y,
        }
    }


@router.get("/heatmap")
def heatmap():
    """Full correlation matrix for the heatmap on the correlations page."""
    d = all_data()
    merged = d["merged"]
    if merged is None:
        return {"vars": [], "matrix": []}
    cols = POLLUTANTS + HEALTH + ["urban_percentage", "literacy_rate"]
    cols = [c for c in cols if c in merged.columns]
    corr = merged[cols].corr().round(3)
    return {
        "vars": cols,
        "matrix": corr.values.tolist(),
    }
