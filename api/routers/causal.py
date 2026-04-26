"""Causal inference endpoints."""
from fastapi import APIRouter
import numpy as np
from ..services.data_loader import all_data, df_to_records

router = APIRouter(prefix="/causal", tags=["causal"])


@router.get("/granger-within")
def granger_within():
    """Granger causality results enriched with district name + state."""
    d = all_data()
    g = d["granger_within"]
    districts = d["districts"]
    if g is None:
        return []
    out = g.copy()
    if districts is not None:
        out = out.merge(
            districts[["district_id", "district_name", "state"]],
            on="district_id", how="left",
        )
    return df_to_records(out)


@router.get("/cross-correlation")
def cross_correlation():
    """Compute national cross-correlation between PM2.5 and respiratory cases at lags 0..12."""
    d = all_data()
    merged = d["merged"]
    if merged is None:
        return []
    nat = (merged.groupby("year_month")
           .agg(pm25=("pm25", "mean"), resp=("respiratory_cases", "mean"))
           .reset_index().sort_values("year_month"))
    pm = (nat["pm25"] - nat["pm25"].mean()) / nat["pm25"].std()
    rs = (nat["resp"] - nat["resp"].mean()) / nat["resp"].std()
    out = []
    for lag in range(0, 13):
        if lag == 0:
            r = float(np.corrcoef(pm.values, rs.values)[0, 1])
        else:
            r = float(np.corrcoef(pm.values[:-lag], rs.values[lag:])[0, 1])
        out.append({"lag_months": lag, "cross_correlation": round(r, 5)})
    return out


@router.get("/dose-response")
def dose_response():
    return df_to_records(all_data()["dose_response"])


@router.get("/counterfactual")
def counterfactual():
    return df_to_records(all_data()["counterfactual"])


@router.get("/changepoint")
def changepoint():
    """Return CUSUM series + detected change points."""
    d = all_data()
    merged = d["merged"]
    cp_df = d["changepoint"]
    if merged is None:
        return {"series": [], "changepoints": []}
    nat = (merged.groupby("year_month")
           .agg(pm25=("pm25", "mean"))
           .reset_index().sort_values("year_month"))
    nat["cusum"] = np.cumsum(nat["pm25"] - nat["pm25"].mean())
    nat["year_month"] = nat["year_month"].astype(str).str[:7]
    return {
        "series":       df_to_records(nat),
        "changepoints": df_to_records(cp_df),
    }


@router.get("/attributable")
def attributable():
    return df_to_records(all_data()["attributable"])


@router.get("/var-forecast")
def var_forecast():
    return df_to_records(all_data()["var_forecast"])


@router.get("/synthetic-control")
def synthetic_control():
    """Treated district trajectory vs synthetic counterfactual + gap series."""
    d = all_data()
    series = df_to_records(d["synthetic_control"])
    meta   = df_to_records(d["synthetic_ctrl_meta"])
    return {"series": series, "meta": meta[0] if meta else {}}


@router.get("/rdd")
def rdd():
    """RDD estimates at multiple bandwidths + binned scatter near the NAAQS cutoff."""
    d = all_data()
    return {
        "estimates": df_to_records(d["rdd_results"]),
        "scatter":   df_to_records(d["rdd_scatter"]),
    }


@router.get("/psm")
def psm():
    """Propensity-score-matched ATT + covariate balance table."""
    d = all_data()
    summary = df_to_records(d["psm_summary"])
    balance = df_to_records(d["psm_balance"])
    return {
        "summary": summary[0] if summary else {},
        "balance": balance,
    }
