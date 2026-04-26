"""Overview & summary KPI endpoints."""
from fastapi import APIRouter
from ..services.data_loader import all_data, df_to_records

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("/kpis")
def kpis():
    """Top-level KPI metrics for the dashboard hero."""
    d = all_data()
    merged, districts, aq = d["merged"], d["districts"], d["aq"]
    return {
        "avg_pm25":          float(round(aq["pm25"].mean(), 1)) if aq is not None else None,
        "max_pm25":          float(round(aq["pm25"].max(), 1)) if aq is not None else None,
        "total_respiratory": int(merged["respiratory_cases"].sum()) if merged is not None else None,
        "total_cardiovascular": int(merged["cardiovascular_cases"].sum()) if merged is not None else None,
        "num_districts":     int(len(districts)) if districts is not None else None,
        "num_states":        int(districts["state"].nunique()) if districts is not None else None,
        "date_range_start":  str(aq["date"].min())[:10] if aq is not None else None,
        "date_range_end":    str(aq["date"].max())[:10] if aq is not None else None,
    }


@router.get("/states")
def states():
    """State-wise pollution + health summary for state comparison page."""
    d = all_data()
    merged = d["merged"]
    if merged is None:
        return []
    agg = (
        merged.groupby("state")
        .agg(avg_pm25=("pm25", "mean"),
             avg_pm10=("pm10", "mean"),
             avg_no2=("no2", "mean"),
             avg_so2=("so2", "mean"),
             total_respiratory=("respiratory_cases", "sum"),
             total_cardiovascular=("cardiovascular_cases", "sum"),
             total_diarrhoea=("diarrhoea_cases", "sum"),
             num_districts=("district_id", "nunique"))
        .round(2).reset_index()
        .sort_values("avg_pm25", ascending=False)
    )
    return df_to_records(agg)


@router.get("/seasonality")
def seasonality():
    """Monthly seasonality of pollutants and disease incidence."""
    d = all_data()
    aq, merged = d["aq"], d["merged"]
    if aq is None or merged is None:
        return {"pollution": [], "health": []}

    aq_m = aq.copy()
    aq_m["year"] = aq_m["date"].dt.year
    poll = aq_m.groupby("year")[["pm25", "pm10", "no2", "so2"]].mean().round(1).reset_index()
    poll = poll[poll["year"].between(2013, 2023)]

    h_m = merged.copy()
    if hasattr(h_m["year_month"], "dt"):
        h_m["year"] = h_m["year_month"].dt.year
    else:
        h_m["year"] = h_m["year_month"].astype(str).str[:4].astype(int)
    health = h_m.groupby("year")[["respiratory_cases", "cardiovascular_cases", "diarrhoea_cases"]].mean().round(1).reset_index()
    health = health[health["year"].between(2013, 2023)]

    return {
        "pollution": df_to_records(poll),
        "health":    df_to_records(health),
    }
