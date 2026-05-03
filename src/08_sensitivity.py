"""
08_sensitivity.py
Pollution Sensitivity Analysis — why does the same PM2.5 cause far more
respiratory disease in Cluster 3 (UP/Bihar) than anywhere else in India?

Uses district-level long-term averages (same data as the cluster scatter plot).

Outputs (all in data/processed/):
  sensitivity_coefficients.csv    — per-district residuals + excess burden
  cluster_sensitivity_summary.csv — per-cluster slope, excess burden, intercept
  cluster_dose_response.csv       — PM2.5-binned dose-response per cluster
  sensitivity_interaction.csv     — interaction regression (formal test)
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import statsmodels.formula.api as smf

ROOT      = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"

CLUSTER_LABELS = {
    0: "At Risk",
    1: "Critical — High Pollution",
    2: "Moderate",
    3: "Critical — High Disease Burden",
}

print("=" * 60)
print("08 — Pollution Sensitivity Analysis")
print("=" * 60)

# ── 1. Load district-level averages ──────────────────────────────
clust = pd.read_csv(PROCESSED / "district_clusters.csv")
dist  = pd.read_csv(PROCESSED / "districts_clean.csv")

df = clust.merge(dist[["district_id", "population"]], on="district_id", how="left")
df["cluster_label"] = df["cluster"].map(CLUSTER_LABELS)
df = df.dropna(subset=["pm25", "respiratory_cases", "cluster"])
df["log_pop"] = np.log1p(df["population"].fillna(df["population"].median()))

print(f"Districts available: {len(df)}")
print(df.groupby("cluster_label")["district_id"].count())

# ── 2. National regression + residuals ───────────────────────────
# Model: respiratory_cases ~ pm25 + log_pop (controls for district size)
model_nat = smf.ols("respiratory_cases ~ pm25 + log_pop", data=df).fit()
df["predicted_national"] = model_nat.fittedvalues
df["residual"]           = model_nat.resid
df["excess_pct"]         = (df["residual"] / df["predicted_national"].clip(lower=1)) * 100

nat_pm25_coeff = model_nat.params["pm25"]
nat_r2         = model_nat.rsquared
print(f"\nNational model (pop-controlled): R²={nat_r2:.3f}, "
      f"pm25 coeff={nat_pm25_coeff:.3f}, p={model_nat.pvalues['pm25']:.4f}")

# ── 3. Per-cluster sensitivity slopes ────────────────────────────
cluster_records = []
for cid, grp in df.groupby("cluster"):
    grp = grp.dropna(subset=["pm25", "respiratory_cases", "log_pop"])
    n = len(grp)
    if n < 4:
        continue
    try:
        m = smf.ols("respiratory_cases ~ pm25 + log_pop", data=grp).fit()
        pm25_coeff = m.params["pm25"]
        pm25_se    = m.bse["pm25"]
        pm25_p     = m.pvalues["pm25"]
        r2         = m.rsquared
    except Exception:
        sl, ic, r, p, se = stats.linregress(grp["pm25"], grp["respiratory_cases"])
        pm25_coeff, pm25_se, pm25_p, r2 = sl, se, p, r**2

    cluster_records.append({
        "cluster":           int(cid),
        "cluster_label":     CLUSTER_LABELS.get(int(cid), str(cid)),
        "n_districts":       n,
        "pm25_slope":        round(pm25_coeff, 3),
        "pm25_se":           round(pm25_se, 3),
        "pm25_p":            round(pm25_p, 4),
        "r2":                round(r2, 4),
        "significant":       pm25_p < 0.05,
        "mean_excess_cases": round(grp["residual"].mean(), 1),
        "median_excess_cases": round(grp["residual"].median(), 1),
        "mean_excess_pct":   round(grp["excess_pct"].mean(), 1),
        "mean_pm25":         round(grp["pm25"].mean(), 1),
        "mean_resp":         round(grp["respiratory_cases"].mean(), 1),
    })

summary = pd.DataFrame(cluster_records)
summary["sensitivity_ratio"] = (summary["pm25_slope"] / nat_pm25_coeff).round(3)

print("\nCluster sensitivity summary (pop-controlled slope):")
print(summary[["cluster_label", "n_districts", "pm25_slope", "sensitivity_ratio",
               "mean_excess_cases", "significant"]].to_string())

# ── 4. Cluster-stratified dose-response (absolute cases) ─────────
dose_records = []
for cid, grp in df.groupby("cluster"):
    grp = grp.dropna(subset=["pm25", "respiratory_cases"])
    n_bins = min(6, max(3, len(grp) // 3))
    try:
        grp = grp.copy()
        grp["pm25_bin"] = pd.qcut(grp["pm25"], q=n_bins, duplicates="drop")
    except ValueError:
        continue
    for bin_label, bgrp in grp.groupby("pm25_bin", observed=True):
        n    = len(bgrp)
        mean = bgrp["respiratory_cases"].mean()
        med  = bgrp["respiratory_cases"].median()
        se   = bgrp["respiratory_cases"].sem() if n > 1 else 0
        dose_records.append({
            "cluster":       int(cid),
            "cluster_label": CLUSTER_LABELS.get(int(cid), str(cid)),
            "pm25_bin_mid":  round(float(bin_label.mid), 1),
            "pm25_bin_lo":   round(float(bin_label.left), 1),
            "pm25_bin_hi":   round(float(bin_label.right), 1),
            "mean_resp":     round(mean, 1),
            "median_resp":   round(med, 1),
            "ci_lower":      round(max(0, mean - 1.96 * se), 1),
            "ci_upper":      round(mean + 1.96 * se, 1),
            "n":             n,
        })

dose_df = pd.DataFrame(dose_records).sort_values(["cluster", "pm25_bin_mid"])
print(f"\nCluster dose-response rows: {len(dose_df)}")

# ── 5. Interaction regression (formal test) ───────────────────────
reg_df = df.copy()
for c in [0, 1, 3]:
    reg_df[f"pm25_x_c{c}"] = reg_df["pm25"] * (reg_df["cluster"] == c).astype(int)
    reg_df[f"c{c}"]         = (reg_df["cluster"] == c).astype(int)

formula = ("respiratory_cases ~ pm25 + log_pop "
           "+ c0 + c1 + c3 "
           "+ pm25_x_c0 + pm25_x_c1 + pm25_x_c3")
try:
    model_int = smf.ols(formula, data=reg_df).fit()
    icoeffs = pd.DataFrame({
        "term":        model_int.params.index,
        "coefficient": model_int.params.values,
        "std_error":   model_int.bse.values,
        "p_value":     model_int.pvalues.values,
    })
    icoeffs["significant"] = icoeffs["p_value"] < 0.05
    icoeffs["r2"]          = model_int.rsquared
    icoeffs["n"]           = int(model_int.nobs)
    print(f"\nInteraction model R²={model_int.rsquared:.3f}, n={int(model_int.nobs)}")
    print(icoeffs[["term", "coefficient", "p_value", "significant"]].to_string())
except Exception as e:
    print(f"Interaction regression failed: {e}")
    icoeffs = pd.DataFrame()

# ── 6. Save outputs ───────────────────────────────────────────────
out_cols = ["district_id", "district_name", "state", "cluster", "cluster_label",
            "pm25", "respiratory_cases", "predicted_national", "residual", "excess_pct"]
out_cols = [c for c in out_cols if c in df.columns]
df[out_cols].round(3).to_csv(PROCESSED / "sensitivity_coefficients.csv", index=False)
summary.to_csv(PROCESSED / "cluster_sensitivity_summary.csv", index=False)
dose_df.to_csv(PROCESSED / "cluster_dose_response.csv", index=False)
if not icoeffs.empty:
    icoeffs.to_csv(PROCESSED / "sensitivity_interaction.csv", index=False)

print("\n✓ Script 08 complete — Pollution Sensitivity Analysis ready.")
