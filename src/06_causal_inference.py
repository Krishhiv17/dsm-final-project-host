"""
06_causal_inference.py
======================
Causal Inference — Moving Beyond Correlation

1.  Within-district Granger causality  (PM2.5 → respiratory, all 150 districts)
2.  Optimal lag detection              (AIC / BIC + significance profile)
3.  VAR model (Vector Autoregression)  (national PM2.5 + respiratory jointly)
4.  Impulse Response Functions         (how does a PM2.5 shock propagate?)
5.  Dose-Response curve                (non-linear burden vs. exposure)
6.  Counterfactual analysis            (cases averted if PM2.5 ↓ 20/30/50%)
7.  Change-point detection             (CUSUM — structural breaks in PM2.5)
8.  Attributable Fraction              (% burden due to excess pollution)
9.  Difference-in-Differences sketch   (high- vs. low-pollution districts, seasonal)

Outputs (data/processed/):
    granger_within_district.csv
    var_forecast.csv
    dose_response.csv
    counterfactual.csv
    changepoint.csv
    attributable_fraction.csv

Figures (notebooks/figures/):
    19_granger_lag_heatmap.png
    20_var_impulse_response.png
    21_dose_response.png
    22_counterfactual.png
    23_changepoint.png
"""

import warnings
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

try:
    from statsmodels.tsa.stattools import grangercausalitytests, adfuller
    from statsmodels.tsa.api import VAR
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False
    print("  [WARN] statsmodels not installed — VAR/Granger steps will use fallbacks.")

# ── Paths ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FIG_DIR       = PROJECT_ROOT / "notebooks" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

plt.style.use("seaborn-v0_8-whitegrid")
DPI       = 150
MAXLAG    = 6
NAAQS_PM25 = 60.0  # µg/m³ standard


# ════════════════════════════════════════════════════════════════════
# LOAD DATA
# ════════════════════════════════════════════════════════════════════

def load_data():
    print("\n  Loading processed data...")
    merged    = pd.read_csv(PROCESSED_DIR / "air_health_merged.csv")
    districts = pd.read_csv(PROCESSED_DIR / "districts_clean.csv")
    merged["year_month"] = pd.to_datetime(merged["year_month"])
    merged["resp_rate_per_100k"] = (
        merged["respiratory_cases"] * 100_000 / merged["population"].replace(0, np.nan)
    )
    print(f"  Merged: {merged.shape}  |  Districts: {len(districts)}")
    return merged, districts


# ════════════════════════════════════════════════════════════════════
# 1. WITHIN-DISTRICT GRANGER CAUSALITY
# ════════════════════════════════════════════════════════════════════

def within_district_granger(merged: pd.DataFrame):
    """
    For each district, test: does PM2.5 Granger-cause respiratory_cases?
    Reports the optimal lag and significance.
    """
    print("\n  [1] Within-district Granger causality...")

    if not HAS_STATSMODELS:
        print("  [SKIP] statsmodels not available")
        return pd.DataFrame()

    results = []
    district_ids = merged["district_id"].unique()

    for did in district_ids:
        df_d = (merged[merged["district_id"] == did]
                .sort_values("year_month")[["pm25", "respiratory_cases"]]
                .dropna())

        if len(df_d) < MAXLAG + 5:
            continue

        # First-difference to induce stationarity
        df_diff = df_d.diff().dropna()
        data = df_diff[["respiratory_cases", "pm25"]].values

        best_p, best_f, best_lag = 1.0, 0.0, 1
        try:
            gc_res = grangercausalitytests(data, maxlag=MAXLAG, verbose=False)
            for lag in range(1, MAXLAG + 1):
                f, p, _, _ = gc_res[lag][0]["ssr_ftest"]
                if p < best_p:
                    best_p, best_f, best_lag = p, f, lag
        except Exception:
            pass

        results.append({
            "district_id": did,
            "best_lag_months": best_lag,
            "F_stat":     round(best_f, 4),
            "p_value":    round(best_p, 5),
            "significant_05": best_p < 0.05,
            "significant_10": best_p < 0.10,
        })

    df_res = pd.DataFrame(results)
    n_sig  = df_res["significant_05"].sum()
    pct    = n_sig / len(df_res) * 100
    print(f"  Districts with significant Granger causality (p<0.05): "
          f"{n_sig}/{len(df_res)} ({pct:.1f}%)")

    lag_dist = df_res["best_lag_months"].value_counts().sort_index()
    print("  Lag distribution (months):")
    for lag, cnt in lag_dist.items():
        print(f"    Lag {lag}: {cnt} districts")

    df_res.to_csv(PROCESSED_DIR / "granger_within_district.csv", index=False)
    print("  → Saved: granger_within_district.csv")
    return df_res


# ════════════════════════════════════════════════════════════════════
# 2. OPTIMAL LAG DETECTION — national series
# ════════════════════════════════════════════════════════════════════

def optimal_lag_detection(merged: pd.DataFrame):
    """
    Compute cross-correlation between national avg PM2.5 and respiratory cases
    at lags 0..12 months. Find peak lag — this is the empirical response time.
    """
    print("\n  [2] Optimal lag detection (cross-correlation)...")

    national = (merged.groupby("year_month")
                .agg(pm25_avg=("pm25", "mean"),
                     resp_avg=("respiratory_cases", "mean"))
                .sort_index().reset_index())

    pm25_s = (national["pm25_avg"] - national["pm25_avg"].mean()) / national["pm25_avg"].std()
    resp_s = (national["resp_avg"] - national["resp_avg"].mean()) / national["resp_avg"].std()

    lags = range(0, 13)
    xcorr = []
    for lag in lags:
        if lag == 0:
            r = float(np.corrcoef(pm25_s.values, resp_s.values)[0, 1])
        else:
            r = float(np.corrcoef(pm25_s.values[:-lag], resp_s.values[lag:])[0, 1])
        xcorr.append({"lag_months": lag, "cross_correlation": round(r, 5)})

    xcorr_df = pd.DataFrame(xcorr)
    peak_row  = xcorr_df.loc[xcorr_df["cross_correlation"].idxmax()]
    print(f"  Peak cross-correlation: r={peak_row['cross_correlation']:.4f} "
          f"at lag {int(peak_row['lag_months'])} month(s)")
    print(f"  Interpretation: respiratory burden peaks ~{int(peak_row['lag_months'])} "
          f"month(s) after a PM2.5 spike")
    return xcorr_df, int(peak_row["lag_months"])


# ════════════════════════════════════════════════════════════════════
# 3. VAR MODEL (national PM2.5 + respiratory)
# ════════════════════════════════════════════════════════════════════

def var_model(merged: pd.DataFrame, optimal_lag: int):
    """
    Fit a Vector Autoregression on national monthly [PM2.5, respiratory_cases].
    Compute Impulse Response Functions (IRF) and Forecast Error Variance Decomposition (FEVD).
    """
    print("\n  [3] VAR model (national time series)...")

    if not HAS_STATSMODELS:
        print("  [SKIP] statsmodels not available")
        return None, None

    national = (merged.groupby("year_month")
                .agg(pm25=("pm25", "mean"),
                     respiratory=("respiratory_cases", "mean"))
                .sort_index())

    # Stationarity check
    for col in ["pm25", "respiratory"]:
        adf_stat, adf_p, *_ = adfuller(national[col].dropna())
        status = "stationary" if adf_p < 0.05 else "non-stationary (differencing recommended)"
        print(f"    ADF [{col}]: stat={adf_stat:.3f}, p={adf_p:.4f} → {status}")

    # First-difference for stationarity
    national_d = national.diff().dropna()

    model  = VAR(national_d)
    max_ic = min(MAXLAG, len(national_d) // 5)
    res    = model.fit(maxlags=max_ic, ic="aic")

    print(f"\n  VAR selected lag order: {res.k_ar} (AIC)")
    print(f"  AIC = {res.aic:.2f}")

    # Granger causality test within VAR
    print("\n  VAR Granger causality (PM2.5 → respiratory):")
    try:
        gc_test = res.test_causality("respiratory", "pm25", kind="f")
        print(f"    F-stat = {gc_test.test_statistic:.4f}, "
              f"p = {gc_test.pvalue:.5f}, "
              f"{'SIGNIFICANT' if gc_test.pvalue < 0.05 else 'not significant'}")
    except Exception as e:
        print(f"    [Could not run VAR Granger test: {e}]")

    # Forecast
    lag_order = res.k_ar
    forecast  = res.forecast(national_d.values[-lag_order:], steps=12)
    forecast_df = pd.DataFrame(forecast, columns=["pm25_diff", "resp_diff"])
    forecast_df["month_ahead"] = range(1, 13)
    forecast_df.to_csv(PROCESSED_DIR / "var_forecast.csv", index=False)
    print("  → Saved: var_forecast.csv")

    return res, national_d


# ════════════════════════════════════════════════════════════════════
# 4. DOSE-RESPONSE CURVE
# ════════════════════════════════════════════════════════════════════

def dose_response_curve(merged: pd.DataFrame):
    """
    Bin PM2.5 into deciles. For each bin compute mean respiratory rate per 100k.
    Fit linear + log-linear regression to characterise the relationship shape.
    """
    print("\n  [4] Dose-response curve (PM2.5 → resp rate per 100k)...")

    df = merged[["pm25", "resp_rate_per_100k"]].dropna()

    df["pm25_bin"] = pd.qcut(df["pm25"], q=10, duplicates="drop")
    bin_stats = df.groupby("pm25_bin", observed=True)["resp_rate_per_100k"].agg(
        ["mean", "std", "count"]
    ).reset_index()
    bin_stats.columns = ["pm25_bin", "resp_rate_mean", "resp_rate_std", "n"]
    bin_stats["pm25_bin_center"] = bin_stats["pm25_bin"].apply(
        lambda b: (b.left + b.right) / 2
    ).astype(float)
    bin_stats["se"] = bin_stats["resp_rate_std"] / np.sqrt(bin_stats["n"])

    # Linear fit
    x = bin_stats["pm25_bin_center"].values
    y = bin_stats["resp_rate_mean"].values
    slope, intercept, r_lin, p_lin, _ = stats.linregress(x, y)

    # Log-linear fit
    log_x = np.log(x + 1)
    slope_l, intercept_l, r_log, p_log, _ = stats.linregress(log_x, y)

    print(f"  Linear fit:     slope={slope:.4f}, R={r_lin:.4f}, p={p_lin:.4e}")
    print(f"  Log-linear fit: slope={slope_l:.4f}, R={r_log:.4f}, p={p_log:.4e}")
    better = "log-linear" if abs(r_log) > abs(r_lin) else "linear"
    print(f"  Better fit: {better}")
    print(f"  Each +10 µg/m³ PM2.5 → +{slope * 10:.2f} additional cases per 100k")

    bin_stats["linear_fit"]     = slope * x + intercept
    bin_stats["loglinear_fit"]  = slope_l * np.log(x + 1) + intercept_l
    bin_stats.to_csv(PROCESSED_DIR / "dose_response.csv", index=False)
    print("  → Saved: dose_response.csv")
    return bin_stats, slope


# ════════════════════════════════════════════════════════════════════
# 5. COUNTERFACTUAL ANALYSIS
# ════════════════════════════════════════════════════════════════════

def counterfactual_analysis(merged: pd.DataFrame):
    """
    Train RF model. Predict respiratory burden under reduced PM2.5 scenarios.
    Quantify cases averted at population scale.
    """
    print("\n  [5] Counterfactual analysis...")

    features = ["pm25", "pm10", "no2", "so2", "urban_percentage", "literacy_rate", "population"]
    target   = "respiratory_cases"
    df = merged[features + [target]].dropna()

    X = df[features].values
    y = df[target].values

    model = RandomForestRegressor(n_estimators=200, max_depth=15, random_state=42, n_jobs=-1)
    model.fit(X, y)

    baseline_total = y.sum()
    baseline_mean  = y.mean()

    reductions = [0.10, 0.20, 0.30, 0.50]
    cf_rows = []

    pm25_idx = features.index("pm25")
    pm10_idx = features.index("pm10")
    no2_idx  = features.index("no2")

    for pct in reductions:
        X_cf = X.copy()
        X_cf[:, pm25_idx] = X[:, pm25_idx] * (1 - pct)
        X_cf[:, pm10_idx] = X[:, pm10_idx] * (1 - pct * 0.8)
        X_cf[:, no2_idx]  = X[:, no2_idx]  * (1 - pct * 0.5)

        y_cf    = model.predict(X_cf)
        averted = baseline_total - y_cf.sum()
        pct_red = averted / baseline_total * 100

        cf_rows.append({
            "pm25_reduction_pct":    int(pct * 100),
            "baseline_total_cases":  int(baseline_total),
            "counterfactual_total":  int(y_cf.sum()),
            "cases_averted":         int(averted),
            "percent_cases_reduced": round(pct_red, 2),
            "mean_case_reduction":   round(baseline_mean - y_cf.mean(), 1),
        })
        print(f"  PM2.5 −{int(pct*100)}%: {int(averted):,} cases averted "
              f"({pct_red:.1f}% reduction)")

    cf_df = pd.DataFrame(cf_rows)
    cf_df.to_csv(PROCESSED_DIR / "counterfactual.csv", index=False)
    print("  → Saved: counterfactual.csv")
    return cf_df


# ════════════════════════════════════════════════════════════════════
# 6. CHANGE-POINT DETECTION (CUSUM)
# ════════════════════════════════════════════════════════════════════

def change_point_detection(merged: pd.DataFrame):
    """
    Apply CUSUM to national monthly PM2.5 time series.
    Identify structural breaks — periods where pollution regime shifted.
    """
    print("\n  [6] Change-point detection (CUSUM)...")

    national = (merged.groupby("year_month")
                .agg(pm25=("pm25", "mean"))
                .sort_index().reset_index())

    series = national["pm25"].values
    mu     = series.mean()
    cusum  = np.cumsum(series - mu)
    cusum_pos = np.maximum(cusum, 0)
    cusum_neg = np.minimum(cusum, 0)

    # Detect change points as local extrema in CUSUM
    cp_candidates = []
    window = 6
    for i in range(window, len(cusum) - window):
        segment_before = cusum[max(0, i - window):i]
        segment_after  = cusum[i:min(len(cusum), i + window)]
        # Sign change in slope
        slope_before = np.polyfit(range(len(segment_before)), segment_before, 1)[0]
        slope_after  = np.polyfit(range(len(segment_after)),  segment_after,  1)[0]
        if slope_before * slope_after < 0:  # sign flip
            cp_candidates.append({
                "index": i,
                "year_month": str(national["year_month"].iloc[i])[:7],
                "pm25_at_cp": round(float(series[i]), 2),
                "cusum_value": round(float(cusum[i]), 2),
                "slope_before": round(float(slope_before), 4),
                "slope_after":  round(float(slope_after),  4),
                "direction": "increasing → decreasing" if slope_before > 0 else "decreasing → increasing",
            })

    # Prune: keep most prominent (largest |cusum| jumps)
    cp_df = pd.DataFrame(cp_candidates) if cp_candidates else pd.DataFrame()
    if len(cp_df):
        cp_df["prominence"] = np.abs(cp_df["cusum_value"])
        cp_df = cp_df.nlargest(5, "prominence").sort_values("index").reset_index(drop=True)
        print(f"  Found {len(cp_df)} prominent change points:")
        for _, r in cp_df.iterrows():
            print(f"    {r['year_month']}: PM2.5={r['pm25_at_cp']:.1f} — {r['direction']}")
        cp_df.to_csv(PROCESSED_DIR / "changepoint.csv", index=False)
        print("  → Saved: changepoint.csv")

    # Also save full CUSUM series
    national["cusum"] = cusum
    national["cusum_pos"] = cusum_pos
    national["cusum_neg"] = cusum_neg

    return national, cp_df if len(cp_df) else pd.DataFrame()


# ════════════════════════════════════════════════════════════════════
# 7. ATTRIBUTABLE FRACTION
# ════════════════════════════════════════════════════════════════════

def attributable_fraction(merged: pd.DataFrame):
    """
    Estimate the Population Attributable Fraction (PAF) of respiratory
    disease burden attributable to PM2.5 exceeding the NAAQS standard.

    PAF = (rate_exposed - rate_unexposed) / rate_total  × prevalence_exposed
    """
    print(f"\n  [7] Population Attributable Fraction (NAAQS threshold = {NAAQS_PM25} µg/m³)...")

    df = merged[["pm25", "resp_rate_per_100k", "respiratory_cases", "population"]].dropna()
    df["exposed"] = df["pm25"] > NAAQS_PM25

    # Rates
    rate_exp   = df[df["exposed"]]["resp_rate_per_100k"].mean()
    rate_unexp = df[~df["exposed"]]["resp_rate_per_100k"].mean()
    rate_total = df["resp_rate_per_100k"].mean()
    prev_exp   = df["exposed"].mean()

    RR = rate_exp / rate_unexp if rate_unexp > 0 else np.nan
    PAF = prev_exp * (RR - 1) / (prev_exp * (RR - 1) + 1) if not np.isnan(RR) else np.nan

    # Bootstrap CI for PAF
    rng = np.random.default_rng(42)
    paf_boot = []
    for _ in range(1000):
        idx = rng.integers(0, len(df), len(df))
        b = df.iloc[idx]
        re = b[b["exposed"]]["resp_rate_per_100k"].mean()
        ru = b[~b["exposed"]]["resp_rate_per_100k"].mean()
        pe = b["exposed"].mean()
        if ru > 0:
            rr_b = re / ru
            paf_b = pe * (rr_b - 1) / (pe * (rr_b - 1) + 1)
            paf_boot.append(paf_b)

    paf_ci = np.percentile(paf_boot, [2.5, 97.5]) if paf_boot else [np.nan, np.nan]

    print(f"  Exposed   (PM2.5 > {NAAQS_PM25}): {prev_exp*100:.1f}% of district-months")
    print(f"  Rate exposed:   {rate_exp:.1f} per 100k")
    print(f"  Rate unexposed: {rate_unexp:.1f} per 100k")
    print(f"  Relative Risk (RR):            {RR:.3f}")
    print(f"  Population Attributable Fraction: {PAF*100:.1f}%")
    print(f"  95% CI: [{paf_ci[0]*100:.1f}%, {paf_ci[1]*100:.1f}%]")
    print(f"  Interpretation: ~{PAF*100:.0f}% of respiratory burden attributable "
          f"to PM2.5 above the safe standard")

    af_row = {
        "metric": ["Relative Risk", "PAF (%)", "PAF CI lower (%)", "PAF CI upper (%)",
                   "Rate Exposed", "Rate Unexposed", "Prevalence Exposed (%)"],
        "value": [round(RR, 4), round(PAF * 100, 2), round(paf_ci[0] * 100, 2),
                  round(paf_ci[1] * 100, 2), round(rate_exp, 2),
                  round(rate_unexp, 2), round(prev_exp * 100, 2)],
    }
    af_df = pd.DataFrame(af_row)
    af_df.to_csv(PROCESSED_DIR / "attributable_fraction.csv", index=False)
    print("  → Saved: attributable_fraction.csv")
    return af_df, RR, PAF


# ════════════════════════════════════════════════════════════════════
# 8. DIFFERENCE-IN-DIFFERENCES (sketch)
# ════════════════════════════════════════════════════════════════════

def difference_in_differences(merged: pd.DataFrame):
    """
    Treat winter months (Nov-Feb, high pollution) as 'treatment' period
    and summer/monsoon (Jun-Sep) as 'control' period.
    Compare respiratory case changes between high-pollution vs. low-pollution districts.
    """
    print("\n  [8] Difference-in-Differences (seasonal treatment sketch)...")

    df = merged.copy()
    df["month"] = df["year_month"].dt.month
    df["winter"] = df["month"].isin([11, 12, 1, 2]).astype(int)

    district_avg_pm25 = df.groupby("district_id")["pm25"].mean()
    median_pm25 = district_avg_pm25.median()
    high_pm25_ids = district_avg_pm25[district_avg_pm25 > median_pm25].index
    df["high_pollution_district"] = df["district_id"].isin(high_pm25_ids).astype(int)

    # DiD: compare winter vs. summer, high vs. low pollution districts
    groups = df.groupby(["high_pollution_district", "winter"])["resp_rate_per_100k"].mean()

    try:
        baseline_low_summer  = groups.loc[(0, 0)]
        baseline_low_winter  = groups.loc[(0, 1)]
        baseline_high_summer = groups.loc[(1, 0)]
        baseline_high_winter = groups.loc[(1, 1)]

        did_estimate = (
            (baseline_high_winter - baseline_high_summer) -
            (baseline_low_winter  - baseline_low_summer)
        )

        print(f"  Low-pollution districts:   summer={baseline_low_summer:.1f}  "
              f"winter={baseline_low_winter:.1f}  Δ={baseline_low_winter-baseline_low_summer:.1f}")
        print(f"  High-pollution districts:  summer={baseline_high_summer:.1f}  "
              f"winter={baseline_high_winter:.1f}  Δ={baseline_high_winter-baseline_high_summer:.1f}")
        print(f"\n  DiD Estimate: {did_estimate:.2f} cases/100k")
        print(f"  Interpretation: pollution seasonality causes an additional "
              f"{did_estimate:.1f} respiratory cases per 100k over winter, "
              f"beyond the baseline seasonal effect")
    except KeyError as e:
        print(f"  [Could not compute DiD: {e}]")
        did_estimate = np.nan

    return did_estimate


# ════════════════════════════════════════════════════════════════════
# VISUALISATIONS
# ════════════════════════════════════════════════════════════════════

def plot_granger_lags(granger_df: pd.DataFrame, xcorr_df: pd.DataFrame, merged: pd.DataFrame):
    print("\n  Plotting Granger lag analysis...")
    fig, axes = plt.subplots(1, 3, figsize=(21, 6))

    # A: Distribution of optimal lags across districts
    ax = axes[0]
    if len(granger_df):
        lag_counts = granger_df["best_lag_months"].value_counts().sort_index()
        bars = ax.bar(lag_counts.index, lag_counts.values,
                      color=["#e74c3c" if i in granger_df[granger_df["significant_05"]]
                             ["best_lag_months"].values else "#aaaaaa"
                             for i in lag_counts.index],
                      edgecolor="black")
        ax.set_title("Optimal Granger Lag Distribution\n(red = significant at p<0.05)",
                     fontsize=12, fontweight="bold")
        ax.set_xlabel("Lag (months)")
        ax.set_ylabel("Number of Districts")
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)

    # B: Cross-correlation at different lags (national)
    ax = axes[1]
    ax.bar(xcorr_df["lag_months"], xcorr_df["cross_correlation"],
           color=["#e74c3c" if v > 0 else "#3498db" for v in xcorr_df["cross_correlation"]],
           edgecolor="black", alpha=0.8)
    peak = xcorr_df.loc[xcorr_df["cross_correlation"].idxmax()]
    ax.axvline(peak["lag_months"], color="black", linestyle="--", linewidth=1.5,
               label=f"Peak at lag {int(peak['lag_months'])}m")
    ax.set_title("Cross-Correlation: National PM2.5 → Respiratory\n(at different lags)",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Lag (months)")
    ax.set_ylabel("Cross-Correlation r")
    ax.legend()

    # C: P-value distribution across districts
    ax = axes[2]
    if len(granger_df):
        ax.hist(granger_df["p_value"], bins=20, color="#9b59b6",
                alpha=0.8, edgecolor="black")
        ax.axvline(0.05, color="red", linestyle="--", linewidth=1.5, label="α = 0.05")
        sig_frac = granger_df["significant_05"].mean() * 100
        ax.set_title(f"Granger p-value Distribution\n({sig_frac:.0f}% of districts significant)",
                     fontsize=12, fontweight="bold")
        ax.set_xlabel("p-value (PM2.5 → respiratory)")
        ax.set_ylabel("Count")
        ax.legend()

    plt.suptitle("Granger Causality — PM2.5 → Respiratory Disease (Within Districts)",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "19_granger_lag_heatmap.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 19_granger_lag_heatmap.png")


def plot_var_irf(var_result, national_d):
    print("  Plotting VAR impulse response...")
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    if var_result is None or national_d is None:
        for ax in axes:
            ax.text(0.5, 0.5, "VAR not available", ha="center", va="center",
                    transform=ax.transAxes)
        plt.tight_layout()
        plt.savefig(FIG_DIR / "20_var_impulse_response.png", dpi=DPI, bbox_inches="tight")
        plt.close()
        return

    try:
        irf = var_result.irf(12)
        periods = range(13)

        # IRF: PM2.5 shock → respiratory
        irf_vals = irf.irfs[:, 1, 0]  # resp response to pm25 shock
        ax = axes[0]
        ax.plot(periods, irf_vals, "o-", color="#e74c3c", linewidth=2, markersize=6)
        ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
        ax.fill_between(periods, irf_vals, alpha=0.15, color="#e74c3c")
        ax.set_title("IRF: PM2.5 Shock → Respiratory Cases\n(response over 12 months)",
                     fontsize=12, fontweight="bold")
        ax.set_xlabel("Months after shock")
        ax.set_ylabel("Response (standardised)")

        # FEVD: variance decomposition
        try:
            fevd = var_result.fevd(12)
            resp_fevd = fevd.decomp[1]  # respiratory equation
            ax = axes[1]
            months = range(1, 13)
            ax.stackplot(months,
                         resp_fevd[:, 0] * 100,
                         resp_fevd[:, 1] * 100,
                         labels=["Due to PM2.5", "Due to own lags"],
                         colors=["#e74c3c", "#3498db"], alpha=0.8)
            ax.set_title("Forecast Error Variance Decomposition\n(% of respiratory variance explained)",
                         fontsize=12, fontweight="bold")
            ax.set_xlabel("Forecast horizon (months)")
            ax.set_ylabel("% variance")
            ax.legend(loc="upper right")
        except Exception:
            axes[1].text(0.5, 0.5, "FEVD not available", ha="center", va="center",
                         transform=axes[1].transAxes)
    except Exception as e:
        for ax in axes:
            ax.text(0.5, 0.5, f"IRF error:\n{e}", ha="center", va="center",
                    transform=ax.transAxes, fontsize=9)

    plt.suptitle("VAR Model — Causal Dynamics of Pollution and Respiratory Disease",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "20_var_impulse_response.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 20_var_impulse_response.png")


def plot_dose_response(bin_stats: pd.DataFrame, slope: float):
    print("  Plotting dose-response curve...")
    fig, ax = plt.subplots(figsize=(12, 7))

    x = bin_stats["pm25_bin_center"].values
    y = bin_stats["resp_rate_mean"].values
    se = bin_stats["se"].values

    ax.errorbar(x, y, yerr=1.96 * se, fmt="o", color="#2c3e50",
                markersize=8, linewidth=1.5, capsize=5, label="Observed (mean ± 95% CI)")
    ax.plot(x, bin_stats["linear_fit"].values, "--",
            color="#e74c3c", linewidth=2, label="Linear fit")
    ax.plot(x, bin_stats["loglinear_fit"].values, "-",
            color="#3498db", linewidth=2, label="Log-linear fit")
    ax.axvline(NAAQS_PM25, color="green", linestyle=":", linewidth=2,
               label=f"NAAQS standard ({NAAQS_PM25} µg/m³)")
    ax.fill_betweenx([y.min() * 0.9, y.max() * 1.1], 0, NAAQS_PM25,
                     alpha=0.05, color="green", label="Safe zone")

    ax.set_title(f"Dose-Response: PM2.5 → Respiratory Rate\n"
                 f"(+10 µg/m³ PM2.5 ≈ +{slope*10:.1f} cases per 100k per month)",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("PM2.5 (µg/m³) — bin centre")
    ax.set_ylabel("Respiratory Cases per 100,000")
    ax.legend(fontsize=10)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "21_dose_response.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 21_dose_response.png")


def plot_counterfactual(cf_df: pd.DataFrame):
    print("  Plotting counterfactual scenarios...")
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # A: Cases averted
    ax = axes[0]
    colors = ["#f39c12", "#e67e22", "#e74c3c", "#c0392b"]
    bars = ax.bar(cf_df["pm25_reduction_pct"].astype(str) + "%",
                  cf_df["cases_averted"] / 1e6,
                  color=colors, edgecolor="black")
    for bar, row in zip(bars, cf_df.itertuples()):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.02,
                f"{row.percent_cases_reduced:.1f}%",
                ha="center", fontsize=11, fontweight="bold")
    ax.set_title("Cases Averted Under Counterfactual Scenarios\n(if PM2.5 reduced by X%)",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("PM2.5 Reduction Scenario")
    ax.set_ylabel("Respiratory Cases Averted (millions)")

    # B: Baseline vs counterfactual totals
    ax = axes[1]
    scenarios = ["Baseline"] + [f"−{r}%" for r in cf_df["pm25_reduction_pct"]]
    totals    = ([cf_df["baseline_total_cases"].iloc[0]]
                 + cf_df["counterfactual_total"].tolist())
    bar_colors = ["#95a5a6"] + colors
    ax.bar(scenarios, [t / 1e6 for t in totals], color=bar_colors, edgecolor="black")
    ax.set_title("Baseline vs. Counterfactual Total Respiratory Cases",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Scenario")
    ax.set_ylabel("Total Cases (millions)")
    ax.axhline(totals[0] / 1e6, color="red", linestyle="--", alpha=0.5, label="Baseline")
    ax.legend()

    plt.suptitle("Counterfactual Analysis — Policy Scenarios",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "22_counterfactual.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 22_counterfactual.png")


def plot_changepoint(national: pd.DataFrame, cp_df: pd.DataFrame):
    print("  Plotting change-point detection...")
    fig, axes = plt.subplots(2, 1, figsize=(16, 10), sharex=True)

    x = range(len(national))
    dates = national["year_month"].astype(str).str[:7]

    # Top: raw PM2.5 series
    ax = axes[0]
    ax.plot(x, national["pm25"].values, color="#e74c3c", linewidth=1.5, label="PM2.5")
    ax.axhline(national["pm25"].mean(), color="black", linestyle="--",
               alpha=0.5, label="Mean")
    if len(cp_df):
        for _, cp in cp_df.iterrows():
            ax.axvline(cp["index"], color="#9b59b6", linestyle=":",
                       linewidth=1.5, alpha=0.8)
    ax.set_title("National Monthly PM2.5 with Change Points",
                 fontsize=12, fontweight="bold")
    ax.set_ylabel("PM2.5 (µg/m³)")
    ax.legend()

    # Bottom: CUSUM
    ax = axes[1]
    cusum = national["cusum"].values
    ax.plot(x, cusum, color="#3498db", linewidth=1.5, label="CUSUM")
    ax.fill_between(x, cusum, 0, where=(cusum > 0),
                    alpha=0.2, color="#e74c3c", label="> mean")
    ax.fill_between(x, cusum, 0, where=(cusum < 0),
                    alpha=0.2, color="#2ecc71", label="< mean")
    ax.axhline(0, color="black", linewidth=0.8)
    if len(cp_df):
        for _, cp in cp_df.iterrows():
            ax.axvline(cp["index"], color="#9b59b6", linestyle=":",
                       linewidth=1.5, alpha=0.8, label=f"CP {cp['year_month']}")
    ax.set_title("CUSUM — Cumulative Sum of Deviations from Mean",
                 fontsize=12, fontweight="bold")
    ax.set_ylabel("CUSUM")
    ax.set_xlabel("Month")
    ax.legend(fontsize=8)

    tick_step = max(1, len(x) // 12)
    ax.set_xticks(x[::tick_step])
    ax.set_xticklabels(dates.iloc[::tick_step], rotation=45, ha="right")

    plt.suptitle("Change-Point Detection — Structural Breaks in Pollution Trends",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "23_changepoint.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 23_changepoint.png")


# ════════════════════════════════════════════════════════════════════
# 9. SYNTHETIC CONTROL METHOD
# ════════════════════════════════════════════════════════════════════

def synthetic_control(merged: pd.DataFrame, districts: pd.DataFrame):
    """
    Synthetic Control Method (SCM):
    Construct a weighted combination of clean 'donor' districts that
    best replicates the pre-period respiratory trajectory of the most
    polluted district.  The post-period gap is the causal effect of
    sustained excess pollution.

    Outputs:
        synthetic_control.csv  — treated / synthetic / gap per month
        synthetic_control_meta.csv — ATT, pre-RMSE, treated district
    """
    print("\n  [9] Synthetic Control Method...")

    from scipy.optimize import minimize

    panel = (merged.groupby(["district_id", "year_month"])
             .agg(resp_rate=("resp_rate_per_100k", "mean"),
                  pm25=("pm25", "mean"))
             .reset_index())

    avg_pm25 = panel.groupby("district_id")["pm25"].mean().sort_values(ascending=False)
    treated_id = int(avg_pm25.index[0])
    donor_ids  = list(avg_pm25.index[-30:].astype(int))

    pivot = (panel.pivot(index="year_month", columns="district_id", values="resp_rate")
             .sort_index().fillna(panel["resp_rate"].mean()))

    T   = len(pivot)
    T0  = T // 2     # pre/post split

    Y_treated   = pivot[treated_id].values
    Y_donors    = pivot[donor_ids].values   # T × n_donors

    Y_pre_t = Y_treated[:T0]
    Y_pre_d = Y_donors[:T0]

    n_donors = len(donor_ids)

    def loss(w):
        return float(np.sum((Y_pre_t - Y_pre_d @ w) ** 2))

    w0 = np.ones(n_donors) / n_donors
    res = minimize(
        loss, w0, method="SLSQP",
        bounds=[(0, 1)] * n_donors,
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
        options={"ftol": 1e-10, "maxiter": 2000},
    )
    w_opt = res.x

    Y_synthetic = Y_donors @ w_opt
    gap         = Y_treated - Y_synthetic

    pre_rmse  = float(np.sqrt(np.mean(gap[:T0] ** 2)))
    att       = float(gap[T0:].mean())

    times = pivot.index.astype(str).str[:7]
    out = pd.DataFrame({
        "year_month": times,
        "treated":   np.round(Y_treated,   3),
        "synthetic": np.round(Y_synthetic, 3),
        "gap":       np.round(gap,         3),
        "is_post":   [i >= T0 for i in range(T)],
    })
    out.to_csv(PROCESSED_DIR / "synthetic_control.csv", index=False)

    # district name for treated
    treated_name = (districts[districts["district_id"] == treated_id]["district_name"].iloc[0]
                    if len(districts[districts["district_id"] == treated_id]) else str(treated_id))

    meta = pd.DataFrame([{
        "treated_district_id": treated_id,
        "treated_district_name": treated_name,
        "n_donors": n_donors,
        "T0_months": T0,
        "pre_rmse": round(pre_rmse, 4),
        "att": round(att, 4),
        "att_pct_of_mean": round(att / Y_treated[T0:].mean() * 100, 2),
        "top_donor_id": int(donor_ids[w_opt.argmax()]),
        "top_donor_weight": round(float(w_opt.max()), 4),
    }])
    meta.to_csv(PROCESSED_DIR / "synthetic_control_meta.csv", index=False)

    print(f"  Treated district: {treated_name} (avg PM2.5: {avg_pm25.iloc[0]:.1f} µg/m³)")
    print(f"  Pre-period RMSE (balance quality): {pre_rmse:.3f}")
    print(f"  Post-period ATT: +{att:.2f} cases/100k ({meta['att_pct_of_mean'].iloc[0]:+.1f}% vs treated mean)")
    print("  → Saved: synthetic_control.csv, synthetic_control_meta.csv")
    return out, meta


# ════════════════════════════════════════════════════════════════════
# 10. REGRESSION DISCONTINUITY DESIGN
# ════════════════════════════════════════════════════════════════════

def regression_discontinuity(merged: pd.DataFrame):
    """
    RDD at the NAAQS PM2.5 standard (60 µg/m³).

    District-months just above vs just below 60 µg/m³ differ primarily
    in NAAQS compliance.  A discontinuity in respiratory outcomes at the
    cutoff — estimated with local linear regression — is a credible causal
    estimate of the marginal effect of crossing the threshold.

    Multiple bandwidths give a robustness table.

    Outputs:
        rdd_results.csv  — estimates by bandwidth
        rdd_scatter.csv  — binned scatter for visualization
    """
    print("\n  [10] Regression Discontinuity Design (cutoff = 60 µg/m³)...")

    try:
        import statsmodels.api as sm
    except ImportError:
        print("  [SKIP] statsmodels not available")
        return pd.DataFrame()

    CUTOFF = 60.0
    df = merged[["pm25", "resp_rate_per_100k"]].dropna().copy()
    df["running"] = df["pm25"] - CUTOFF
    df["above"]   = (df["running"] >= 0).astype(int)

    rdd_rows = []
    for bw in [10, 15, 20, 30, 40]:
        local = df[df["running"].abs() <= bw].copy()
        if len(local) < 40:
            continue
        local["interaction"] = local["above"] * local["running"]
        X = sm.add_constant(local[["above", "running", "interaction"]])
        model = sm.OLS(local["resp_rate_per_100k"], X).fit()
        ci = model.conf_int().loc["above"]
        rdd_rows.append({
            "bandwidth":    bw,
            "rdd_estimate": round(float(model.params["above"]),      4),
            "std_err":      round(float(model.bse["above"]),          4),
            "p_value":      round(float(model.pvalues["above"]),      5),
            "ci_lower":     round(float(ci[0]),                       4),
            "ci_upper":     round(float(ci[1]),                       4),
            "n_obs":        len(local),
        })
        print(f"  BW ±{bw:2d} µg/m³: LATE = {rdd_rows[-1]['rdd_estimate']:+.2f}  "
              f"SE={rdd_rows[-1]['std_err']:.2f}  p={rdd_rows[-1]['p_value']:.4f}  "
              f"n={len(local)}")

    rdd_df = pd.DataFrame(rdd_rows)
    rdd_df.to_csv(PROCESSED_DIR / "rdd_results.csv", index=False)

    # Binned scatter near cutoff (BW = 30) for visualization
    local30 = df[df["running"].abs() <= 30].copy()
    local30["bin"] = pd.cut(local30["running"], bins=30)
    scatter = (local30.groupby("bin", observed=True)["resp_rate_per_100k"]
               .mean().reset_index())
    scatter["running_center"] = scatter["bin"].apply(
        lambda b: (b.left + b.right) / 2).astype(float)
    scatter["above"] = (scatter["running_center"] >= 0).astype(int)
    scatter[["running_center", "resp_rate_per_100k", "above"]].to_csv(
        PROCESSED_DIR / "rdd_scatter.csv", index=False)

    print("  → Saved: rdd_results.csv, rdd_scatter.csv")
    return rdd_df


# ════════════════════════════════════════════════════════════════════
# 11. PROPENSITY SCORE MATCHING
# ════════════════════════════════════════════════════════════════════

def propensity_score_matching(merged: pd.DataFrame):
    """
    Propensity Score Matching (PSM):
    - Treatment: district-month with PM2.5 above the national median
    - Covariates: urban%, literacy, log-population, month (as sin/cos)
    - Logistic regression → propensity scores
    - 1:1 nearest-neighbour matching without replacement
    - ATT = mean(resp_treated_matched - resp_control_matched)
    - Covariate balance: Standardised Mean Difference (SMD) before/after

    Outputs:
        psm_summary.csv  — ATT + CI
        psm_balance.csv  — per-covariate SMD before/after
    """
    print("\n  [11] Propensity Score Matching...")

    from sklearn.linear_model import LogisticRegression
    from sklearn.neighbors import NearestNeighbors

    threshold = float(merged["pm25"].median())

    df = merged[["pm25", "resp_rate_per_100k", "urban_percentage",
                 "literacy_rate", "population", "year_month"]].dropna().copy()
    df = df.reset_index(drop=True)

    df["treated"]   = (df["pm25"] > threshold).astype(int)
    df["log_pop"]   = np.log1p(df["population"])
    df["month"]     = pd.to_datetime(df["year_month"]).dt.month
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

    covariates = ["urban_percentage", "literacy_rate", "log_pop",
                  "month_sin", "month_cos"]

    X_cov   = df[covariates].values
    y_treat = df["treated"].values

    lr = LogisticRegression(max_iter=500, C=1.0, random_state=42)
    lr.fit(X_cov, y_treat)
    ps = lr.predict_proba(X_cov)[:, 1]
    df["ps"] = ps

    t_mask = df["treated"] == 1
    c_mask = df["treated"] == 0
    t_idx  = df[t_mask].index.tolist()
    c_idx  = df[c_mask].index.tolist()

    ps_t = ps[t_mask]
    ps_c = ps[c_mask]

    nbrs = NearestNeighbors(n_neighbors=1, algorithm="ball_tree")
    nbrs.fit(ps_c.reshape(-1, 1))
    _, nn_idx = nbrs.kneighbors(ps_t.reshape(-1, 1))
    matched_c_idx = [c_idx[i] for i in nn_idx.flatten()]

    resp_t = df.loc[t_idx, "resp_rate_per_100k"].values
    resp_c = df.loc[matched_c_idx, "resp_rate_per_100k"].values
    diffs  = resp_t - resp_c
    n      = len(diffs)

    att    = float(diffs.mean())
    se_att = float(diffs.std() / np.sqrt(n))

    # SMD per covariate
    smd_rows = []
    for cov in covariates:
        t_all  = df.loc[t_idx, cov].values
        c_all  = df.loc[c_idx, cov].values
        c_mat  = df.loc[matched_c_idx, cov].values
        pool   = np.sqrt((t_all.var() + c_all.var()) / 2) + 1e-9
        smd_rows.append({
            "covariate":  cov,
            "smd_before": round(abs(t_all.mean() - c_all.mean()) / pool, 4),
            "smd_after":  round(abs(t_all.mean() - c_mat.mean()) / pool, 4),
        })
    balance_df = pd.DataFrame(smd_rows)
    avg_smd_before = balance_df["smd_before"].mean()
    avg_smd_after  = balance_df["smd_after"].mean()

    summary = pd.DataFrame([{
        "treatment_threshold_pm25": round(threshold, 2),
        "n_treated":                n,
        "n_control_pool":           len(c_idx),
        "att":                      round(att,    4),
        "att_se":                   round(se_att, 4),
        "att_ci_lower":             round(att - 1.96 * se_att, 4),
        "att_ci_upper":             round(att + 1.96 * se_att, 4),
        "mean_treated":             round(float(resp_t.mean()),  4),
        "mean_matched_control":     round(float(resp_c.mean()), 4),
        "avg_smd_before":           round(avg_smd_before, 4),
        "avg_smd_after":            round(avg_smd_after,  4),
    }])

    summary.to_csv(PROCESSED_DIR / "psm_summary.csv",  index=False)
    balance_df.to_csv(PROCESSED_DIR / "psm_balance.csv", index=False)

    print(f"  Threshold: {threshold:.1f} µg/m³  |  n_matched: {n}")
    print(f"  ATT: {att:+.2f} cases/100k  (95% CI: [{att-1.96*se_att:.2f}, {att+1.96*se_att:.2f}])")
    print(f"  Avg SMD before: {avg_smd_before:.3f} → after: {avg_smd_after:.3f}")
    print("  → Saved: psm_summary.csv, psm_balance.csv")
    return summary, balance_df


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  DSM Final Project — Causal Inference")
    print("=" * 60)

    merged, districts = load_data()

    # 1. Within-district Granger
    granger_df = within_district_granger(merged)

    # 2. Optimal lag (cross-correlation)
    xcorr_df, optimal_lag = optimal_lag_detection(merged)

    # 3. VAR model
    var_result, national_d = var_model(merged, optimal_lag)

    # 4. Dose-response
    bin_stats, slope = dose_response_curve(merged)

    # 5. Counterfactual
    cf_df = counterfactual_analysis(merged)

    # 6. Change-point
    national_cusum, cp_df = change_point_detection(merged)

    # 7. Attributable fraction
    af_df, RR, PAF = attributable_fraction(merged)

    # 8. DiD
    did = difference_in_differences(merged)

    # 9. Synthetic Control Method
    sc_df, sc_meta = synthetic_control(merged, districts)

    # 10. Regression Discontinuity Design
    rdd_df = regression_discontinuity(merged)

    # 11. Propensity Score Matching
    psm_summary, psm_balance = propensity_score_matching(merged)

    # Plots
    print("\n  Generating visualisations...")
    plot_granger_lags(granger_df, xcorr_df, merged)
    plot_var_irf(var_result, national_d)
    plot_dose_response(bin_stats, slope)
    plot_counterfactual(cf_df)
    plot_changepoint(national_cusum, cp_df)

    print("\n" + "=" * 60)
    print("  Causal Inference Complete!")
    print("=" * 60)
    if len(granger_df):
        pct_sig = granger_df["significant_05"].mean() * 100
        print(f"  Districts with PM2.5→resp Granger causality: {pct_sig:.0f}%")
    print(f"  Peak cross-correlation lag: {optimal_lag} month(s)")
    print(f"  Relative Risk (PM2.5 > NAAQS): {RR:.3f}")
    print(f"  Population Attributable Fraction: {PAF*100:.1f}%")
    print(f"  DiD estimate (winter vs summer effect): {did:.2f} cases/100k")
    if len(sc_meta):
        print(f"  SCM ATT (most polluted district): {sc_meta['att'].iloc[0]:+.2f} cases/100k")
    if len(rdd_df):
        main_rdd = rdd_df[rdd_df["bandwidth"] == 20].iloc[0] if 20 in rdd_df["bandwidth"].values else rdd_df.iloc[0]
        print(f"  RDD LATE (BW±20): {main_rdd['rdd_estimate']:+.2f} cases/100k  p={main_rdd['p_value']:.4f}")
    if len(psm_summary):
        print(f"  PSM ATT: {psm_summary['att'].iloc[0]:+.2f} cases/100k")
    print(f"  Figures saved to: {FIG_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
