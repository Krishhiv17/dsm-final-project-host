"""Time-series endpoints for the explorer page."""
from fastapi import APIRouter, Query
from typing import Literal
from ..services.data_loader import all_data, df_to_records

router = APIRouter(prefix="/timeseries", tags=["timeseries"])


@router.get("/districts")
def districts():
    """List districts that actually have air-quality data (id, name, state)."""
    d = all_data()
    if d["districts"] is None or d["aq"] is None:
        return []
    aq_ids = set(d["aq"]["district_id"].dropna().astype(int))
    df = d["districts"].copy()
    df = df[df["district_id"].astype(int).isin(aq_ids)]
    return df_to_records(
        df[["district_id", "district_name", "state"]].sort_values(["state", "district_name"])
    )


@router.get("")
def get_series(
    district_id: int = Query(...),
    pollutant: Literal["pm25", "pm10", "no2", "so2", "aqi"] = "pm25",
    aggregation: Literal["daily", "weekly", "monthly"] = "monthly",
):
    """Return a time series for a single district + pollutant."""
    d = all_data()
    aq = d["aq"]
    if aq is None:
        return []
    series = aq[aq["district_id"] == district_id][["date", pollutant]].sort_values("date").copy()
    if aggregation == "weekly":
        series = series.resample("W", on="date").mean().reset_index()
    elif aggregation == "monthly":
        series = series.resample("ME", on="date").mean().reset_index()
    series["date"] = series["date"].astype(str)
    return df_to_records(series)
