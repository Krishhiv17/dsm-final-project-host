"""District clustering endpoint."""
from fastapi import APIRouter
from ..services.data_loader import all_data, df_to_records

router = APIRouter(prefix="/clusters", tags=["clusters"])

CLUSTER_LABELS = {
    0: "At Risk",
    1: "Critical — High Pollution",
    2: "Moderate",
    3: "Critical — High Disease Burden",
}


@router.get("")
def get_clusters():
    """Return the district clusters with semantic labels."""
    d = all_data()
    clusters = d["clusters"]
    if clusters is None:
        return {"clusters": [], "summary": []}
    df = clusters.copy()
    df["risk_label"] = df["cluster"].map(CLUSTER_LABELS).fillna("Unknown")

    # Summary
    summary = (
        df.groupby(["cluster", "risk_label"])
          .agg(n_districts=("district_name", "count"),
               avg_pm25=("pm25", "mean"),
               avg_resp=("respiratory_cases", "mean"))
          .round(1).reset_index()
    )

    return {
        "clusters": df_to_records(df),
        "summary":  df_to_records(summary),
    }
