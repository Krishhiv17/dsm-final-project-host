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


@router.get("/scatter3d")
def scatter3d(
    x: str = Query("pm25"),
    y: str = Query("pm10"),
    z: str = Query("respiratory_cases"),
    sample: int = Query(2500, le=4000),
):
    """Sampled 3D scatter for any three numeric variables in the merged panel."""
    d = all_data()
    merged = d["merged"]
    if merged is None or any(c not in merged.columns for c in (x, y, z)):
        return {"data": [], "stats": {}}
    df = merged[[x, y, z, "state"]].dropna()
    if len(df) > sample:
        df = df.sample(sample, random_state=42)
    return {
        "data": df_to_records(df.rename(columns={x: "x", y: "y", z: "z"})),
        "stats": {"n": int(len(df)), "x_var": x, "y_var": y, "z_var": z},
    }


@router.get("/heatmap")
def heatmap():
    """Full correlation matrix for the heatmap on the correlations page."""
    d = all_data()
    merged = d["merged"]
    if merged is None:
        return {"vars": [], "matrix": []}
    cols = POLLUTANTS + ["respiratory_cases"] + ["urban_percentage", "literacy_rate"]
    cols = [c for c in cols if c in merged.columns]
    corr = merged[cols].corr().round(3)
    import math
    matrix = [
        [None if isinstance(v, float) and math.isnan(v) else v for v in row]
        for row in corr.values.tolist()
    ]
    return {
        "vars": cols,
        "matrix": matrix,
    }
