"""Advanced statistical analytics endpoints."""
from fastapi import APIRouter
from ..services.data_loader import all_data, df_to_records

router = APIRouter(prefix="/advanced", tags=["advanced"])


@router.get("/pca")
def pca_results():
    d = all_data()
    df = d["pca"]
    if df is None:
        return {"sample": [], "n_total": 0}
    merged = d["merged"]
    sample = df.sample(min(3000, len(df)), random_state=42).copy()
    if merged is not None:
        st = merged[["district_id", "state"]].drop_duplicates()
        sample = sample.merge(st, on="district_id", how="left")
    return {"sample": df_to_records(sample), "n_total": int(len(df))}


@router.get("/mediation")
def mediation():
    df = all_data()["mediation"]
    if df is None or df.empty:
        return None
    return df.iloc[0].where(df.iloc[0].notnull(), None).to_dict()


@router.get("/panel-fe")
def panel_fe():
    return df_to_records(all_data()["panel_fe"])


@router.get("/gwr")
def gwr():
    return df_to_records(all_data()["gwr"])


@router.get("/epi-metrics")
def epi_metrics():
    return df_to_records(all_data()["epi"])


@router.get("/partial-correlation")
def partial_correlation():
    df = all_data()["partial_corr"]
    if df is None or df.empty:
        return None
    return df.iloc[0].where(df.iloc[0].notnull(), None).to_dict()


@router.get("/spatial-lag")
def spatial_lag():
    return df_to_records(all_data()["spatial_lag"])
