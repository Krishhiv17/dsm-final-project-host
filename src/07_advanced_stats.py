"""
07_advanced_stats.py
====================
Advanced Statistical Modelling

1.  PCA + Factor Analysis         — latent pollution dimensions
2.  Mediation Analysis (SEM-lite) — PM2.5 → urban% → respiratory (path model)
3.  Panel Fixed-Effects Regression — within-district estimator (controls for
                                     all time-invariant district heterogeneity)
4.  Spatial Lag Regression (OLS)  — manually encode neighbour-average PM2.5
5.  GWR-lite (by geographic zone) — coefficients vary across India's regions
6.  Epidemiological Metrics       — RR, OR, NNT, PAF by pollutant threshold
7.  Spearman / partial correlation — rank-based + controlling for confounders
8.  Interaction effects            — pollution × urbanisation synergy

Outputs (data/processed/):
    pca_results.csv
    mediation_results.csv
    panel_fe_results.csv
    gwr_region_results.csv
    epi_metrics.csv
    partial_corr.csv

Figures (notebooks/figures/):
    24_pca_biplot.png
    25_mediation_sem.png
    26_panel_fe.png
    27_gwr_regions.png
    28_epi_metrics.png
"""

import warnings
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from pathlib import Path
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression

warnings.filterwarnings("ignore")

# ── Paths ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FIG_DIR       = PROJECT_ROOT / "notebooks" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

plt.style.use("seaborn-v0_8-whitegrid")
DPI = 150

NAAQS_PM25 = 60.0

GEOGRAPHIC_ZONES = {
    "North":  ["Delhi", "Haryana", "Punjab", "Rajasthan", "Uttar Pradesh"],
    "East":   ["Bihar", "West Bengal"],
    "Central":["Madhya Pradesh"],
    "West":   ["Gujarat", "Maharashtra"],
    "South":  ["Andhra Pradesh", "Karnataka", "Kerala", "Tamil Nadu", "Telangana"],
}


# ════════════════════════════════════════════════════════════════════
# LOAD DATA
# ════════════════════════════════════════════════════════════════════

def load_data():
    print("\n  Loading data...")
    merged    = pd.read_csv(PROCESSED_DIR / "air_health_merged.csv")
    districts = pd.read_csv(PROCESSED_DIR / "districts_clean.csv")
    merged["year_month"] = pd.to_datetime(merged["year_month"])
    merged["month"] = merged["year_month"].dt.month
    merged["year"]  = merged["year_month"].dt.year
    merged["resp_rate_per_100k"] = (
        merged["respiratory_cases"] * 100_000 / merged["population"].replace(0, np.nan)
    )

    # Assign geographic zone
    state_to_zone = {s: z for z, states in GEOGRAPHIC_ZONES.items() for s in states}
    merged["zone"] = merged["state"].map(state_to_zone).fillna("Other")

    print(f"  Merged: {merged.shape}   |  Districts: {len(districts)}")
    return merged, districts


# ════════════════════════════════════════════════════════════════════
# 1. PCA + FACTOR ANALYSIS
# ════════════════════════════════════════════════════════════════════

def pca_factor_analysis(merged: pd.DataFrame):
    """
    PCA on [pm25, pm10, no2, so2].
    Interpret loadings as latent pollution factors.
    """
    print("\n  [1] PCA / Factor Analysis on pollution variables...")

    poll_cols = ["pm25", "pm10", "no2", "so2"]
    df_poll   = merged[["district_id", "year_month"] + poll_cols].dropna()

    X      = df_poll[poll_cols].values
    scaler = StandardScaler()
    X_s    = scaler.fit_transform(X)

    pca = PCA(n_components=4)
    pca.fit(X_s)
    X_pca = pca.transform(X_s)

    evr = pca.explained_variance_ratio_
    print(f"\n  Explained variance:")
    for i, (ev, cevr) in enumerate(zip(evr, np.cumsum(evr))):
        print(f"    PC{i+1}: {ev*100:.1f}%  (cumulative: {cevr*100:.1f}%)")

    # Loadings
    loadings = pd.DataFrame(
        pca.components_.T,
        index=poll_cols,
        columns=[f"PC{i+1}" for i in range(4)]
    )
    print("\n  Factor Loadings:")
    print(loadings.round(3).to_string())

    # Interpret components
    component_names = []
    for i in range(4):
        dominant = loadings[f"PC{i+1}"].abs().idxmax()
        sign = "high" if loadings.loc[dominant, f"PC{i+1}"] > 0 else "low"
        name = (
            "Particulate Pollution (PM)"   if dominant in ["pm25", "pm10"] else
            "Industrial / Traffic Gases"   if dominant in ["no2", "so2"] else
            "Mixed Pollution"
        )
        component_names.append(f"PC{i+1}: {name}")
        print(f"  PC{i+1} dominant: {dominant} ({sign}) → {name}")

    # Save district-level PC scores
    pca_df = pd.DataFrame(X_pca, columns=[f"PC{i+1}" for i in range(4)])
    pca_df["district_id"]  = df_poll["district_id"].values
    pca_df["year_month"]   = df_poll["year_month"].values
    pca_df.to_csv(PROCESSED_DIR / "pca_results.csv", index=False)
    print("  → Saved: pca_results.csv")

    return pca, loadings, pca_df, evr, component_names


# ════════════════════════════════════════════════════════════════════
# 2. MEDIATION ANALYSIS (SEM-LITE)
# ════════════════════════════════════════════════════════════════════

def mediation_analysis(merged: pd.DataFrame):
    """
    Test whether urbanisation mediates the PM2.5 → respiratory relationship.

    Path diagram:
        PM2.5 ──────────────────────→ Respiratory  (direct: c')
          └──→ Urban% ──────────────→ Respiratory  (indirect: a × b)

    Total effect: c = c' + a×b
    Bootstrapped CI for indirect effect.
    """
    print("\n  [2] Mediation Analysis (SEM-lite): PM2.5 → Urban% → Respiratory...")

    df = merged[["pm25", "urban_percentage", "resp_rate_per_100k",
                 "literacy_rate"]].dropna()

    X  = df["pm25"].values.reshape(-1, 1)
    M  = df["urban_percentage"].values.reshape(-1, 1)
    Y  = df["resp_rate_per_100k"].values

    # Path a: X → M
    model_a = LinearRegression().fit(X, M.ravel())
    a = model_a.coef_[0]

    # Path b+c': [X, M] → Y
    XM = np.hstack([X, M])
    model_bc = LinearRegression().fit(XM, Y)
    c_prime = model_bc.coef_[0]   # direct effect
    b       = model_bc.coef_[1]   # b path

    # Path c: X → Y (total)
    model_c = LinearRegression().fit(X, Y)
    c_total = model_c.coef_[0]

    indirect = a * b
    prop_mediated = indirect / c_total if c_total != 0 else np.nan

    # Bootstrap CI for indirect effect
    rng = np.random.default_rng(42)
    boot_indirect = []
    n = len(df)
    for _ in range(2000):
        idx  = rng.integers(0, n, n)
        Xb   = df["pm25"].values[idx].reshape(-1, 1)
        Mb   = df["urban_percentage"].values[idx].reshape(-1, 1)
        Yb   = Y[idx]
        a_b  = LinearRegression().fit(Xb, Mb.ravel()).coef_[0]
        XMb  = np.hstack([Xb, Mb])
        b_b  = LinearRegression().fit(XMb, Yb).coef_[1]
        boot_indirect.append(a_b * b_b)

    ci = np.percentile(boot_indirect, [2.5, 97.5])

    print(f"\n  Path a  (PM2.5 → Urban%):        {a:+.5f}")
    print(f"  Path b  (Urban% → Resp, ctrl PM): {b:+.5f}")
    print(f"  Path c  (PM2.5 → Resp, total):    {c_total:+.5f}")
    print(f"  Path c' (PM2.5 → Resp, direct):   {c_prime:+.5f}")
    print(f"  Indirect effect (a×b):             {indirect:+.5f}")
    print(f"  95% Bootstrap CI: [{ci[0]:+.5f}, {ci[1]:+.5f}]")
    print(f"  Proportion mediated:               {prop_mediated*100:.1f}%")
    significant = not (ci[0] < 0 < ci[1])
    print(f"  Mediation: {'SIGNIFICANT' if significant else 'not significant'} "
          f"(zero {'outside' if significant else 'inside'} 95% CI)")

    results = {
        "path_a":           round(a, 6),
        "path_b":           round(b, 6),
        "path_c_total":     round(c_total, 6),
        "path_c_direct":    round(c_prime, 6),
        "indirect_effect":  round(indirect, 6),
        "ci_lower":         round(ci[0], 6),
        "ci_upper":         round(ci[1], 6),
        "prop_mediated_pct": round(prop_mediated * 100, 2),
        "significant":      significant,
    }
    pd.DataFrame([results]).to_csv(PROCESSED_DIR / "mediation_results.csv", index=False)
    print("  → Saved: mediation_results.csv")
    return results, boot_indirect


# ════════════════════════════════════════════════════════════════════
# 3. PANEL FIXED-EFFECTS REGRESSION
# ════════════════════════════════════════════════════════════════════

def panel_fixed_effects(merged: pd.DataFrame):
    """
    Within-district estimator: demean all variables by district, then run OLS.
    This controls for ALL time-invariant district characteristics
    (geography, industrial history, baseline health, etc.).
    Identifies only the within-district, over-time effect of PM2.5.
    """
    print("\n  [3] Panel Fixed-Effects Regression (within-district estimator)...")

    features = ["pm25", "pm10", "no2", "so2", "month"]
    target   = "resp_rate_per_100k"
    df = merged[["district_id"] + features + [target]].dropna()

    # Demean by district
    df_demean = df.copy()
    for col in features + [target]:
        group_means = df.groupby("district_id")[col].transform("mean")
        df_demean[col] = df[col] - group_means

    X = df_demean[features].values
    y = df_demean[target].values

    from sklearn.linear_model import LinearRegression
    fe_model = LinearRegression(fit_intercept=False)
    fe_model.fit(X, y)
    y_pred = fe_model.predict(X)

    from sklearn.metrics import r2_score, mean_absolute_error
    r2  = r2_score(y, y_pred)
    mae = mean_absolute_error(y, y_pred)
    sse = ((y - y_pred) ** 2).sum()
    sst = ((y - y.mean()) ** 2).sum()

    # Standard errors via residuals
    n, k = len(y), len(features)
    residuals = y - y_pred
    sigma2    = sse / (n - k)
    XtX_inv   = np.linalg.pinv(X.T @ X)
    se        = np.sqrt(np.diag(sigma2 * XtX_inv))
    t_stats   = fe_model.coef_ / se
    p_values  = 2 * (1 - stats.t.cdf(np.abs(t_stats), df=n - k))

    print(f"\n  Panel FE Results (within-district):")
    print(f"  Within R² = {r2:.4f}   MAE = {mae:.2f}")
    print(f"\n  {'Feature':<15} {'Coeff':>10} {'SE':>10} {'t':>8} {'p':>10} {'sig':>5}")
    print(f"  {'-'*60}")

    fe_rows = []
    for feat, coef, se_val, t, p in zip(features, fe_model.coef_, se, t_stats, p_values):
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
        print(f"  {feat:<15} {coef:>+10.4f} {se_val:>10.4f} {t:>8.3f} {p:>10.4f}  {sig}")
        fe_rows.append({"feature": feat, "coefficient": round(coef, 6),
                        "std_error": round(se_val, 6), "t_stat": round(t, 4),
                        "p_value": round(p, 5), "significant": p < 0.05})

    fe_df = pd.DataFrame(fe_rows)
    fe_df["within_r2"] = round(r2, 5)
    fe_df.to_csv(PROCESSED_DIR / "panel_fe_results.csv", index=False)
    print("  → Saved: panel_fe_results.csv")
    return fe_df


# ════════════════════════════════════════════════════════════════════
# 4. SPATIAL LAG REGRESSION
# ════════════════════════════════════════════════════════════════════

def spatial_lag_regression(merged: pd.DataFrame):
    """
    Add spatial lag feature: for each district-month, compute the
    weighted-average PM2.5 of neighbouring districts (inverse-distance weighted).
    Then run OLS: resp ~ own_pm25 + spatial_lag_pm25 + controls.
    Tests: does neighbours' pollution explain LOCAL health burden?
    """
    print("\n  [4] Spatial Lag Regression...")

    geo_path = PROCESSED_DIR / "districts_geocoded.csv"
    if not geo_path.exists():
        print("  [SKIP] districts_geocoded.csv not found")
        return pd.DataFrame()

    geo = pd.read_csv(geo_path)[["district_id", "latitude", "longitude"]].dropna()

    # Build inverse-distance weight matrix (within 300 km)
    ids   = geo["district_id"].values
    lats  = geo["latitude"].values
    lons  = geo["longitude"].values
    n     = len(ids)
    W     = np.zeros((n, n))
    THRESH = 300.0
    R = 6371.0

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dlat = np.radians(lats[j] - lats[i])
            dlon = np.radians(lons[j] - lons[i])
            a    = (np.sin(dlat/2)**2
                    + np.cos(np.radians(lats[i])) * np.cos(np.radians(lats[j]))
                    * np.sin(dlon/2)**2)
            dist = 2 * R * np.arcsin(np.sqrt(a))
            if dist <= THRESH:
                W[i, j] = 1.0 / max(dist, 1.0)

    row_sums = W.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    W_rs = W / row_sums

    id_to_idx = {did: i for i, did in enumerate(ids)}

    # Compute spatial lag of PM2.5 per district-month
    monthly_pm25 = (
        merged.groupby(["district_id", "year_month"])["pm25"]
        .mean().reset_index()
        .pivot(index="year_month", columns="district_id", values="pm25")
        .fillna(method="ffill").fillna(method="bfill")
    )

    lag_records = []
    for ym in monthly_pm25.index:
        pm_row = monthly_pm25.loc[ym]
        for did in ids:
            if did not in monthly_pm25.columns:
                continue
            idx_i    = id_to_idx[did]
            pm_vec   = np.array([pm_row.get(d, 0) for d in ids])
            spat_lag = float(W_rs[idx_i] @ pm_vec)
            lag_records.append({"district_id": did, "year_month": ym,
                                 "spatial_lag_pm25": round(spat_lag, 2)})

    lag_df = pd.DataFrame(lag_records)
    lag_df["year_month"] = lag_df["year_month"].astype(str)
    merged["year_month_str"] = merged["year_month"].astype(str)
    merged_sl = merged.merge(lag_df, left_on=["district_id", "year_month_str"],
                             right_on=["district_id", "year_month"], how="left")

    features = ["pm25", "spatial_lag_pm25", "urban_percentage", "literacy_rate"]
    df = merged_sl[features + ["resp_rate_per_100k"]].dropna()

    X = StandardScaler().fit_transform(df[features])
    y = df["resp_rate_per_100k"].values

    model = LinearRegression().fit(X, y)
    y_pred = model.predict(X)
    r2 = 1 - ((y - y_pred)**2).sum() / ((y - y.mean())**2).sum()

    print(f"\n  Spatial Lag OLS Results (standardised coefficients):")
    print(f"  R² = {r2:.4f}")
    sl_rows = []
    for feat, coef in zip(features, model.coef_):
        print(f"    {feat:<25}: {coef:+.4f}")
        sl_rows.append({"feature": feat, "std_coeff": round(coef, 5)})

    sl_df = pd.DataFrame(sl_rows)
    sl_df["r2"] = round(r2, 5)
    sl_df.to_csv(PROCESSED_DIR / "spatial_lag_results.csv", index=False)
    print("  → Saved: spatial_lag_results.csv")
    return sl_df


# ════════════════════════════════════════════════════════════════════
# 5. GWR-LITE (regression by geographic zone)
# ════════════════════════════════════════════════════════════════════

def gwr_lite(merged: pd.DataFrame):
    """
    Run separate OLS regressions per geographic zone.
    Shows how the PM2.5 → respiratory relationship varies spatially.
    """
    print("\n  [5] GWR-lite (regression by geographic zone)...")

    features = ["pm25", "pm10", "urban_percentage"]
    target   = "resp_rate_per_100k"

    zone_rows = []
    for zone, states in GEOGRAPHIC_ZONES.items():
        df_z = merged[merged["state"].isin(states)][features + [target]].dropna()
        if len(df_z) < 50:
            continue

        X = StandardScaler().fit_transform(df_z[features])
        y = df_z[target].values
        model = LinearRegression().fit(X, y)
        y_pred = model.predict(X)
        r2 = 1 - ((y - y_pred)**2).sum() / ((y - y.mean())**2).sum()

        row = {"zone": zone, "n_obs": len(df_z), "r2": round(r2, 4)}
        for feat, coef in zip(features, model.coef_):
            row[f"coeff_{feat}"] = round(coef, 5)
        zone_rows.append(row)
        print(f"  Zone: {zone:<10}  n={len(df_z):>6,}  R²={r2:.3f}  "
              f"pm25_coeff={row['coeff_pm25']:+.4f}")

    gwr_df = pd.DataFrame(zone_rows)
    gwr_df.to_csv(PROCESSED_DIR / "gwr_region_results.csv", index=False)
    print("  → Saved: gwr_region_results.csv")
    return gwr_df


# ════════════════════════════════════════════════════════════════════
# 6. EPIDEMIOLOGICAL METRICS
# ════════════════════════════════════════════════════════════════════

def epidemiological_metrics(merged: pd.DataFrame):
    """
    For each pollutant threshold:
      - Relative Risk (RR) of respiratory disease
      - Odds Ratio (OR)
      - Number Needed to Treat (NNT) — pollution reduction needed to prevent 1 case
      - Attributable Risk (AR)
    """
    print("\n  [6] Epidemiological metrics...")

    thresholds = {
        "PM2.5 > NAAQS (60)":     ("pm25",  60),
        "PM2.5 > WHO (15)":       ("pm25",  15),
        "PM10 > NAAQS (100)":     ("pm10",  100),
        "NO2 > NAAQS (80)":       ("no2",   80),
        "AQI > Moderate (100)":   ("aqi",   100),
    }

    epi_rows = []
    df = merged[["pm25", "pm10", "no2", "aqi", "resp_rate_per_100k",
                 "respiratory_cases", "population"]].dropna()

    for label, (col, threshold) in thresholds.items():
        if col not in df.columns:
            continue
        exposed   = df[df[col] > threshold]["resp_rate_per_100k"]
        unexposed = df[df[col] <= threshold]["resp_rate_per_100k"]

        if len(exposed) < 10 or len(unexposed) < 10:
            continue

        re = exposed.mean()
        ru = unexposed.mean()
        pe = len(exposed) / len(df)

        RR = re / ru if ru > 0 else np.nan
        AR = re - ru
        PAF = pe * (RR - 1) / (pe * (RR - 1) + 1) if not np.isnan(RR) else np.nan
        NNT = 1 / max(AR, 0.001)

        # Odds Ratio
        p_e  = re / 100000
        p_u  = ru / 100000
        p_e  = min(p_e, 0.9999)
        p_u  = min(p_u, 0.9999)
        OR   = (p_e / (1 - p_e)) / (p_u / (1 - p_u)) if p_u > 0 else np.nan

        print(f"  {label:<30}  RR={RR:.3f}  OR={OR:.3f}  AR={AR:.1f}  PAF={PAF*100:.1f}%")
        epi_rows.append({
            "threshold_label": label,
            "pollutant": col,
            "threshold_value": threshold,
            "n_exposed": len(exposed),
            "n_unexposed": len(unexposed),
            "rate_exposed_per100k":   round(re, 2),
            "rate_unexposed_per100k": round(ru, 2),
            "relative_risk":   round(RR, 4),
            "odds_ratio":      round(OR, 4),
            "attributable_risk": round(AR, 2),
            "PAF_pct":         round(PAF * 100, 2),
            "NNT":             round(NNT, 1),
        })

    epi_df = pd.DataFrame(epi_rows)
    epi_df.to_csv(PROCESSED_DIR / "epi_metrics.csv", index=False)
    print("  → Saved: epi_metrics.csv")
    return epi_df


# ════════════════════════════════════════════════════════════════════
# 7. PARTIAL CORRELATION + INTERACTION EFFECTS
# ════════════════════════════════════════════════════════════════════

def partial_correlation_and_interactions(merged: pd.DataFrame):
    """
    Partial correlation: PM2.5 ↔ respiratory, controlling for urban% and literacy.
    Interaction: does the PM2.5 effect differ for high vs low urban districts?
    """
    print("\n  [7] Partial correlation & interaction effects...")

    df = merged[["pm25", "resp_rate_per_100k", "urban_percentage",
                 "literacy_rate"]].dropna()

    # ── Partial correlation (partialling out urban_pct, literacy_rate) ────
    def partial_corr(df, x, y, controls):
        X_ctrl = df[controls].values
        X_ctrl = np.hstack([np.ones((len(X_ctrl), 1)), X_ctrl])
        # Residualise x
        coef_x = np.linalg.lstsq(X_ctrl, df[x].values, rcond=None)[0]
        res_x  = df[x].values - X_ctrl @ coef_x
        # Residualise y
        coef_y = np.linalg.lstsq(X_ctrl, df[y].values, rcond=None)[0]
        res_y  = df[y].values - X_ctrl @ coef_y
        r, p   = stats.pearsonr(res_x, res_y)
        return r, p

    controls = ["urban_percentage", "literacy_rate"]
    r_raw,  p_raw  = stats.pearsonr(df["pm25"], df["resp_rate_per_100k"])
    r_part, p_part = partial_corr(df, "pm25", "resp_rate_per_100k", controls)

    print(f"\n  PM2.5 ↔ Resp Rate:")
    print(f"    Pearson r (raw):     {r_raw:.4f}  (p={p_raw:.2e})")
    print(f"    Partial r (ctrl):    {r_part:.4f}  (p={p_part:.2e})")
    print(f"    Confounding removed: {(r_raw - r_part):.4f} units")

    # ── Interaction: PM2.5 × Urban% ──────────────────────────────
    df2 = df.copy()
    df2["urban_high"] = (df2["urban_percentage"] > df2["urban_percentage"].median()).astype(int)
    df2["pm25_x_urban"] = df2["pm25"] * df2["urban_percentage"] / 100.0

    X_main  = StandardScaler().fit_transform(df2[["pm25", "urban_percentage"]])
    X_inter = np.hstack([X_main, (df2["pm25_x_urban"].values / df2["pm25_x_urban"].std()).reshape(-1, 1)])
    y       = df2["resp_rate_per_100k"].values

    model_main  = LinearRegression().fit(X_main, y)
    model_inter = LinearRegression().fit(X_inter, y)
    r2_main  = 1 - ((y - model_main.predict(X_main))**2).sum() / ((y - y.mean())**2).sum()
    r2_inter = 1 - ((y - model_inter.predict(X_inter))**2).sum() / ((y - y.mean())**2).sum()

    interaction_coeff = model_inter.coef_[2]
    print(f"\n  Interaction (PM2.5 × Urban%):")
    print(f"    R² without interaction: {r2_main:.4f}")
    print(f"    R² with interaction:    {r2_inter:.4f}")
    print(f"    Interaction coeff:      {interaction_coeff:+.5f}")
    sign = "amplifies" if interaction_coeff > 0 else "attenuates"
    print(f"    → Urbanisation {sign} the PM2.5 → respiratory effect")

    partial_corr_df = pd.DataFrame([{
        "r_pearson":    round(r_raw, 5),
        "p_pearson":    round(p_raw, 6),
        "r_partial":    round(r_part, 5),
        "p_partial":    round(p_part, 6),
        "r2_no_interaction":   round(r2_main, 5),
        "r2_with_interaction": round(r2_inter, 5),
        "interaction_coeff":   round(interaction_coeff, 6),
    }])
    partial_corr_df.to_csv(PROCESSED_DIR / "partial_corr.csv", index=False)
    print("  → Saved: partial_corr.csv")
    return r_raw, r_part, interaction_coeff


# ════════════════════════════════════════════════════════════════════
# VISUALISATIONS
# ════════════════════════════════════════════════════════════════════

def plot_pca(pca, loadings, pca_df, evr, component_names, merged):
    print("\n  Plotting PCA biplot...")
    fig, axes = plt.subplots(1, 3, figsize=(21, 7))

    # A: Scree plot
    ax = axes[0]
    ax.bar(range(1, 5), evr * 100, color=["#e74c3c", "#f39c12", "#3498db", "#2ecc71"],
           edgecolor="black")
    ax.plot(range(1, 5), np.cumsum(evr) * 100, "ko-", linewidth=2, markersize=6,
            label="Cumulative")
    ax.axhline(80, color="red", linestyle="--", alpha=0.5, label="80% threshold")
    ax.set_title("PCA Scree Plot", fontsize=12, fontweight="bold")
    ax.set_xlabel("Principal Component")
    ax.set_ylabel("Explained Variance (%)")
    ax.legend()

    # B: Biplot (PC1 vs PC2, district scores + feature arrows)
    ax = axes[1]
    district_avg_pc = pca_df.groupby("district_id")[["PC1", "PC2"]].mean()
    district_avg_pc = district_avg_pc.merge(
        merged[["district_id", "state"]].drop_duplicates(), on="district_id", how="left"
    )
    states = district_avg_pc["state"].unique()
    cmap   = plt.cm.tab20(np.linspace(0, 1, len(states)))
    state_colors = {s: c for s, c in zip(states, cmap)}

    for state in states:
        mask = district_avg_pc["state"] == state
        ax.scatter(district_avg_pc.loc[mask, "PC1"], district_avg_pc.loc[mask, "PC2"],
                   c=[state_colors[state]], s=40, alpha=0.7, label=state)

    # Feature arrows
    scale = 3.0
    for feat in loadings.index:
        ax.annotate("", xy=(loadings.loc[feat, "PC1"] * scale,
                             loadings.loc[feat, "PC2"] * scale),
                    xytext=(0, 0),
                    arrowprops=dict(arrowstyle="->", color="black", lw=1.5))
        ax.text(loadings.loc[feat, "PC1"] * scale * 1.1,
                loadings.loc[feat, "PC2"] * scale * 1.1,
                feat.upper(), fontsize=9, fontweight="bold")
    ax.axhline(0, color="gray", linewidth=0.5)
    ax.axvline(0, color="gray", linewidth=0.5)
    ax.set_title(f"PCA Biplot (PC1×PC2: {evr[:2].sum()*100:.0f}% variance)",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel(f"PC1 ({evr[0]*100:.1f}%)")
    ax.set_ylabel(f"PC2 ({evr[1]*100:.1f}%)")

    # C: Loadings heatmap
    ax = axes[2]
    sns.heatmap(loadings, annot=True, fmt=".3f", cmap="RdBu_r",
                center=0, vmin=-1, vmax=1, ax=ax, linewidths=0.5,
                cbar_kws={"shrink": 0.8})
    ax.set_title("Factor Loadings", fontsize=12, fontweight="bold")
    ax.set_xticklabels([f"PC{i+1}" for i in range(4)], rotation=0)

    plt.suptitle("PCA / Factor Analysis — Latent Pollution Dimensions",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "24_pca_biplot.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 24_pca_biplot.png")


def plot_mediation(med_results, boot_indirect):
    print("  Plotting mediation / SEM diagram...")
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # A: Path diagram
    ax = axes[0]
    ax.set_xlim(0, 10); ax.set_ylim(0, 8)
    ax.axis("off")

    # Nodes
    node_style = dict(boxstyle="round,pad=0.5", fc="white", ec="black", lw=2)
    ax.text(1, 4, "PM2.5\n(Exposure)", ha="center", va="center", fontsize=11,
            bbox=node_style, fontweight="bold")
    ax.text(5, 7, "Urban%\n(Mediator)", ha="center", va="center", fontsize=11,
            bbox=node_style, fontweight="bold")
    ax.text(9, 4, "Respiratory\n(Outcome)", ha="center", va="center", fontsize=11,
            bbox=node_style, fontweight="bold")

    # Arrows + path coefficients
    arrow_kw = dict(arrowstyle="->", lw=2)
    ax.annotate("", xy=(4.2, 6.7), xytext=(1.8, 4.4),
                arrowprops=dict(**arrow_kw, color="#e74c3c"))
    ax.text(2.5, 5.9, f"a={med_results['path_a']:.4f}", color="#e74c3c",
            fontsize=10, ha="center")

    ax.annotate("", xy=(8.0, 4.3), xytext=(5.8, 6.7),
                arrowprops=dict(**arrow_kw, color="#e74c3c"))
    ax.text(7.2, 5.9, f"b={med_results['path_b']:.4f}", color="#e74c3c",
            fontsize=10, ha="center")

    ax.annotate("", xy=(7.9, 4.0), xytext=(2.1, 4.0),
                arrowprops=dict(**arrow_kw, color="#2c3e50"))
    ax.text(5, 3.5, f"c'={med_results['path_c_direct']:.4f} (direct)",
            color="#2c3e50", fontsize=10, ha="center")

    ax.text(5, 0.8,
            f"Indirect: a×b = {med_results['indirect_effect']:.5f}\n"
            f"95% CI: [{med_results['ci_lower']:.5f}, {med_results['ci_upper']:.5f}]\n"
            f"Proportion mediated: {med_results['prop_mediated_pct']:.1f}%",
            ha="center", va="center", fontsize=10,
            bbox=dict(boxstyle="round", fc="#f0f4ff", ec="#4facfe", lw=1.5))
    ax.set_title("Mediation Path Diagram\n(PM2.5 → Urbanisation → Respiratory)",
                 fontsize=12, fontweight="bold")

    # B: Bootstrap distribution of indirect effect
    ax = axes[1]
    ax.hist(boot_indirect, bins=60, color="#9b59b6", alpha=0.7, edgecolor="black")
    ci = np.percentile(boot_indirect, [2.5, 97.5])
    ax.axvline(ci[0], color="red", linestyle="--", linewidth=1.5, label="95% CI")
    ax.axvline(ci[1], color="red", linestyle="--", linewidth=1.5)
    ax.axvline(med_results["indirect_effect"], color="black",
               linewidth=2, label=f"Observed = {med_results['indirect_effect']:.5f}")
    ax.axvline(0, color="green", linewidth=1.5, linestyle=":", label="Zero")
    ax.set_title("Bootstrap Distribution of Indirect Effect (a×b)",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Indirect effect magnitude")
    ax.set_ylabel("Bootstrap samples")
    ax.legend()

    plt.suptitle("Mediation Analysis — Does Urbanisation Mediate Pollution→Health?",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "25_mediation_sem.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 25_mediation_sem.png")


def plot_panel_fe(fe_df: pd.DataFrame):
    print("  Plotting panel FE results...")
    fig, ax = plt.subplots(figsize=(12, 6))

    colors = ["#e74c3c" if sig else "#aaaaaa" for sig in fe_df["significant"]]
    bars   = ax.barh(fe_df["feature"], fe_df["coefficient"],
                     color=colors, edgecolor="black", alpha=0.85)

    for bar, row in zip(bars, fe_df.itertuples()):
        ax.text(row.coefficient + (0.002 if row.coefficient >= 0 else -0.002),
                bar.get_y() + bar.get_height() / 2,
                f"  {row.coefficient:+.4f}" if row.coefficient >= 0
                else f"{row.coefficient:+.4f}  ",
                va="center",
                ha="left" if row.coefficient >= 0 else "right",
                fontsize=9)

    ax.axvline(0, color="black", linewidth=1)
    ax.set_title(f"Panel Fixed-Effects Regression Coefficients\n"
                 f"(within-district estimator, Within R²={fe_df['within_r2'].iloc[0]:.3f})\n"
                 f"Red = significant at p<0.05",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Coefficient (effect on resp rate per 100k)")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "26_panel_fe.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 26_panel_fe.png")


def plot_gwr(gwr_df: pd.DataFrame):
    print("  Plotting GWR-lite results...")
    if len(gwr_df) < 2:
        print("  [SKIP] Not enough zones")
        return

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # A: PM2.5 coefficient by zone
    ax = axes[0]
    zones  = gwr_df["zone"].values
    coeffs = gwr_df["coeff_pm25"].values
    colors = ["#e74c3c" if c > 0 else "#2ecc71" for c in coeffs]
    ax.barh(zones, coeffs, color=colors, edgecolor="black", alpha=0.85)
    ax.axvline(0, color="black", linewidth=1)
    ax.set_title("GWR-lite: PM2.5 Coefficient by Geographic Zone\n"
                 "(how strongly pollution drives respiratory burden regionally)",
                 fontsize=11, fontweight="bold")
    ax.set_xlabel("Standardised PM2.5 coefficient")

    # B: R² by zone
    ax = axes[1]
    ax.barh(zones, gwr_df["r2"].values, color="#3498db", edgecolor="black", alpha=0.85)
    for i, (zone, r2) in enumerate(zip(zones, gwr_df["r2"].values)):
        ax.text(r2 + 0.005, i, f"{r2:.3f}", va="center", fontsize=9)
    ax.set_title("GWR-lite: R² by Geographic Zone\n"
                 "(how well pollution explains health regionally)",
                 fontsize=11, fontweight="bold")
    ax.set_xlabel("R² (in-zone)")

    plt.suptitle("Geographically Weighted Regression — Regional Heterogeneity",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "27_gwr_regions.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 27_gwr_regions.png")


def plot_epi_metrics(epi_df: pd.DataFrame):
    print("  Plotting epidemiological metrics...")
    fig, axes = plt.subplots(1, 3, figsize=(21, 7))

    if len(epi_df) == 0:
        for ax in axes:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax.transAxes)
        plt.tight_layout()
        plt.savefig(FIG_DIR / "28_epi_metrics.png", dpi=DPI, bbox_inches="tight")
        plt.close()
        return

    labels = epi_df["threshold_label"].values
    colors = ["#e74c3c", "#c0392b", "#f39c12", "#3498db", "#9b59b6"][:len(labels)]

    # A: Relative Risk
    ax = axes[0]
    ax.barh(labels, epi_df["relative_risk"], color=colors, edgecolor="black", alpha=0.85)
    ax.axvline(1, color="black", linewidth=1.5, linestyle="--", label="RR=1 (no effect)")
    ax.set_title("Relative Risk of Respiratory Disease\n(exposed vs. unexposed)",
                 fontsize=11, fontweight="bold")
    ax.set_xlabel("Relative Risk")
    ax.legend(fontsize=8)

    # B: PAF
    ax = axes[1]
    ax.barh(labels, epi_df["PAF_pct"], color=colors, edgecolor="black", alpha=0.85)
    ax.set_title("Population Attributable Fraction (%)\n(burden attributable to excess pollution)",
                 fontsize=11, fontweight="bold")
    ax.set_xlabel("PAF (%)")

    # C: Attributable risk per 100k
    ax = axes[2]
    ax.barh(labels, epi_df["attributable_risk"], color=colors, edgecolor="black", alpha=0.85)
    ax.set_title("Attributable Risk per 100k\n(excess cases in exposed vs. unexposed)",
                 fontsize=11, fontweight="bold")
    ax.set_xlabel("Excess cases per 100k per month")

    plt.suptitle("Epidemiological Metrics — Quantifying the Health Burden",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "28_epi_metrics.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 28_epi_metrics.png")


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  DSM Final Project — Advanced Statistical Modelling")
    print("=" * 60)

    merged, districts = load_data()

    # 1. PCA
    pca, loadings, pca_df, evr, component_names = pca_factor_analysis(merged)

    # 2. Mediation
    med_results, boot_indirect = mediation_analysis(merged)

    # 3. Panel FE
    fe_df = panel_fixed_effects(merged)

    # 4. Spatial lag regression
    sl_df = spatial_lag_regression(merged)

    # 5. GWR-lite
    gwr_df = gwr_lite(merged)

    # 6. Epidemiological metrics
    epi_df = epidemiological_metrics(merged)

    # 7. Partial correlation + interactions
    r_raw, r_part, interaction_coeff = partial_correlation_and_interactions(merged)

    # Plots
    print("\n  Generating visualisations...")
    plot_pca(pca, loadings, pca_df, evr, component_names, merged)
    plot_mediation(med_results, boot_indirect)
    plot_panel_fe(fe_df)
    plot_gwr(gwr_df)
    plot_epi_metrics(epi_df)

    print("\n" + "=" * 60)
    print("  Advanced Statistical Modelling Complete!")
    print("=" * 60)
    print(f"  PCA: PC1+PC2 explain {evr[:2].sum()*100:.0f}% of pollution variance")
    print(f"  Mediation: {med_results['prop_mediated_pct']:.1f}% of PM2.5 effect mediated by urban%")
    print(f"  Panel FE within-R²: {fe_df['within_r2'].iloc[0]:.3f}")
    print(f"  Pearson r (raw): {r_raw:.4f}  →  Partial r (controlled): {r_part:.4f}")
    print(f"  Interaction (PM2.5×urban%): {interaction_coeff:+.5f}")
    print(f"  Figures saved to: {FIG_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
