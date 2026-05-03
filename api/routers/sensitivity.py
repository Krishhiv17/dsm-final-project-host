"""Pollution sensitivity analysis endpoints."""
from fastapi import APIRouter
from ..services.data_loader import all_data, df_to_records

router = APIRouter(prefix="/sensitivity", tags=["sensitivity"])


@router.get("/coefficients")
def sensitivity_coefficients():
    """Per-district PM2.5 → respiratory OLS slope with cluster labels."""
    return df_to_records(all_data().get("sensitivity_coefficients"))


@router.get("/cluster-summary")
def cluster_summary():
    """Mean/median sensitivity coefficient and excess ratio per K-Means cluster."""
    return df_to_records(all_data().get("cluster_sensitivity_summary"))


@router.get("/cluster-dose-response")
def cluster_dose_response():
    """Cluster-stratified dose-response: mean respiratory cases per PM2.5 decile bin."""
    return df_to_records(all_data().get("cluster_dose_response"))


@router.get("/interaction")
def interaction():
    """Interaction regression coefficients (PM2.5 × cluster) with significance flags."""
    return df_to_records(all_data().get("sensitivity_interaction"))
