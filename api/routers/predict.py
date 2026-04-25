"""Health impact prediction endpoint."""
from fastapi import APIRouter
from pydantic import BaseModel, Field
import pandas as pd
from ..services.data_loader import all_data, trained_model

router = APIRouter(prefix="/predict", tags=["predict"])


class PredictionInput(BaseModel):
    pm25: float = Field(..., ge=0, le=500)
    pm10: float = Field(..., ge=0, le=600)
    no2:  float = Field(..., ge=0, le=200)
    so2:  float = Field(..., ge=0, le=100)
    urban_percentage: float = Field(..., ge=0, le=100)
    literacy_rate:    float = Field(..., ge=0, le=100)
    population: int   = Field(..., ge=1000)


@router.post("")
def predict(inp: PredictionInput):
    model, features = trained_model()
    if model is None:
        return {"error": "Model not available"}
    df = pd.DataFrame([inp.model_dump()])[features]
    prediction = float(model.predict(df.values)[0])
    rate = prediction / inp.population * 100_000

    if inp.pm25 > 100:
        risk = "Critical"
    elif inp.pm25 > 60:
        risk = "High"
    elif inp.pm25 > 40:
        risk = "Moderate"
    else:
        risk = "Low"

    # National baseline
    merged = all_data()["merged"]
    nat_avg = float(merged["respiratory_cases"].mean()) if merged is not None else 0
    pct_diff = (prediction - nat_avg) / nat_avg * 100 if nat_avg else 0

    return {
        "predicted_cases":  int(round(prediction)),
        "rate_per_100k":    round(rate, 1),
        "risk_level":       risk,
        "national_avg":     int(round(nat_avg)),
        "pct_vs_baseline":  round(pct_diff, 1),
    }
