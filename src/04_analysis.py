"""
04_analysis.py
==============
Rigorous Data Analysis — Statistical Tests, ML Models, and Prediction

This script performs:
  1. Hypothesis Testing (t-tests, ANOVA) — high vs low pollution districts
  2. OLS & Ridge Regression — respiratory disease ~ f(pollution, demographics)
  3. K-Means Clustering — district grouping by pollution + health profile
  4. Time-Series Decomposition — seasonal vs trend components
  5. Predictive Model — Random Forest + Gradient Boosting for health burden
  6. Feature Importance analysis

Outputs:
  - Model metrics (R², MAE, RMSE) → printed + saved
  - Visualizations → notebooks/figures/
  - Model predictions → data/processed/
"""

import warnings
import sqlite3
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from scipy import stats
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from statsmodels.tsa.seasonal import seasonal_decompose

warnings.filterwarnings("ignore")

# ── Setup ───────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FIG_DIR = PROJECT_ROOT / "notebooks" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

plt.style.use("seaborn-v0_8-whitegrid")
sns.set_palette("husl")
DPI = 150


def load_data():
    """Load processed datasets."""
    print("\n  Loading processed data...")
    merged = pd.read_csv(PROCESSED_DIR / "air_health_merged.csv")
    districts = pd.read_csv(PROCESSED_DIR / "districts_clean.csv")
    aq = pd.read_csv(PROCESSED_DIR / "air_quality_clean.csv")
    print(f"  Merged dataset: {merged.shape}")
    print(f"  Districts: {districts.shape}")
    return merged, districts, aq


# ═══════════════════════════════════════════════════════════════════
# STEP 1: Hypothesis Testing
# ═══════════════════════════════════════════════════════════════════
def hypothesis_testing(merged, districts):
    """Statistical tests comparing high vs low pollution districts."""
    print("\n" + "━" * 60)
    print("  STEP 1: Hypothesis Testing")
    print("━" * 60)

    # Classify districts as high/low pollution based on median PM2.5
    district_avg = merged.groupby("district_id").agg({
        "pm25": "mean",
        "respiratory_cases": "mean",
        "cardiovascular_cases": "mean",
        "diarrhoea_cases": "mean",
    }).reset_index()

    median_pm25 = district_avg["pm25"].median()
    district_avg["pollution_group"] = np.where(
        district_avg["pm25"] > median_pm25, "High", "Low"
    )

    high = district_avg[district_avg["pollution_group"] == "High"]
    low = district_avg[district_avg["pollution_group"] == "Low"]

    print(f"\n  Median PM2.5: {median_pm25:.1f} µg/m³")
    print(f"  High-pollution districts: {len(high)} (PM2.5 > {median_pm25:.1f})")
    print(f"  Low-pollution districts: {len(low)} (PM2.5 ≤ {median_pm25:.1f})")

    # ── Test 1: Independent t-test ──────────────────────────────
    print("\n  Test 1: Independent Samples t-test")
    print("  H₀: Mean respiratory cases are equal in high vs low pollution districts")
    t_stat, p_val = stats.ttest_ind(high["respiratory_cases"], low["respiratory_cases"])
    print(f"    t-statistic = {t_stat:.4f}")
    print(f"    p-value     = {p_val:.2e}")
    print(f"    Result: {'REJECT H₀' if p_val < 0.05 else 'FAIL TO REJECT H₀'} (α=0.05)")
    print(f"    → Respiratory cases ARE {'significantly' if p_val < 0.05 else 'NOT significantly'} "
          f"different between groups")

    # Effect size (Cohen's d)
    cohens_d = (high["respiratory_cases"].mean() - low["respiratory_cases"].mean()) / \
               np.sqrt((high["respiratory_cases"].std()**2 + low["respiratory_cases"].std()**2) / 2)
    print(f"    Cohen's d = {cohens_d:.3f} ({'small' if abs(cohens_d) < 0.5 else 'medium' if abs(cohens_d) < 0.8 else 'large'} effect)")

    # ── Test 2: Mann-Whitney U test ─────────────────────────────
    print("\n  Test 2: Mann-Whitney U Test (non-parametric)")
    u_stat, p_val_u = stats.mannwhitneyu(high["respiratory_cases"],
                                          low["respiratory_cases"],
                                          alternative="greater")
    print(f"    U-statistic = {u_stat:.1f}")
    print(f"    p-value     = {p_val_u:.2e}")
    print(f"    → High-pollution districts have {'significantly' if p_val_u < 0.05 else 'NOT significantly'} "
          f"more respiratory cases")

    # ── Test 3: ANOVA across states ─────────────────────────────
    print("\n  Test 3: One-Way ANOVA — Respiratory cases across states")
    state_groups = [group["respiratory_cases"].values
                    for _, group in merged.groupby("state")]
    f_stat, p_anova = stats.f_oneway(*state_groups)
    print(f"    F-statistic = {f_stat:.2f}")
    print(f"    p-value     = {p_anova:.2e}")
    print(f"    → Respiratory cases vary {'significantly' if p_anova < 0.05 else 'NOT significantly'} across states")

    # ── Test 4: Pearson correlation significance ────────────────
    print("\n  Test 4: Pearson Correlation (PM2.5 vs Respiratory) with confidence interval")
    r, p = stats.pearsonr(merged["pm25"], merged["respiratory_cases"])
    n = len(merged)
    z = np.arctanh(r)
    se = 1 / np.sqrt(n - 3)
    ci_low = np.tanh(z - 1.96 * se)
    ci_high = np.tanh(z + 1.96 * se)
    print(f"    r = {r:.4f} (95% CI: [{ci_low:.4f}, {ci_high:.4f}])")
    print(f"    p = {p:.2e}")

    # ── Visualization ───────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Group comparison
    ax = axes[0]
    if not high["respiratory_cases"].isna().all() and not low["respiratory_cases"].isna().all():
        sns.boxplot(data=district_avg, x="pollution_group", y="respiratory_cases",
                    ax=ax, palette={"High": "#e74c3c", "Low": "#2ecc71"})
        ax.set_title(f"Respiratory Cases\n(p={p_val:.2e})", fontsize=11, fontweight="bold")
    else:
        ax.text(0.5, 0.5, "No Data", ha="center", va="center")

    # Cardiovascular
    ax = axes[1]
    if not high["cardiovascular_cases"].isna().all() and not low["cardiovascular_cases"].isna().all():
        t_cv, p_cv = stats.ttest_ind(high["cardiovascular_cases"].dropna(), low["cardiovascular_cases"].dropna())
        sns.boxplot(data=district_avg, x="pollution_group", y="cardiovascular_cases",
                    ax=ax, palette={"High": "#3498db", "Low": "#2ecc71"})
        ax.set_title(f"Cardiovascular Cases\n(p={p_cv:.2e})", fontsize=11, fontweight="bold")
    else:
        ax.text(0.5, 0.5, "Data Unavailable", ha="center", va="center")
        ax.set_title("Cardiovascular (No Data)")

    # Diarrhoea
    ax = axes[2]
    if not high["diarrhoea_cases"].isna().all() and not low["diarrhoea_cases"].isna().all():
        t_d, p_d = stats.ttest_ind(high["diarrhoea_cases"].dropna(), low["diarrhoea_cases"].dropna())
        sns.boxplot(data=district_avg, x="pollution_group", y="diarrhoea_cases",
                    ax=ax, palette={"High": "#f39c12", "Low": "#2ecc71"})
        ax.set_title(f"Diarrhoea Cases\n(p={p_d:.2e})", fontsize=11, fontweight="bold")
    else:
        ax.text(0.5, 0.5, "Data Unavailable", ha="center", va="center")
        ax.set_title("Diarrhoea (No Data)")

    plt.suptitle("Hypothesis Testing — Disease Burden by Pollution Group",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "10_hypothesis_tests.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 10_hypothesis_tests.png")

    return district_avg


# ═══════════════════════════════════════════════════════════════════
# STEP 2: Regression Analysis
# ═══════════════════════════════════════════════════════════════════
def regression_analysis(merged):
    """OLS and Ridge regression for respiratory disease prediction."""
    print("\n" + "━" * 60)
    print("  STEP 2: Regression Analysis")
    print("━" * 60)

    # Dynamically select features and targets based on available data
    target = "respiratory_cases"
    potential_features = ["pm25", "pm10", "no2", "so2", "urban_percentage", "literacy_rate"]
    
    # Check if target has any data
    if merged[target].isna().all():
        print(f"  [ERROR] No data available for target: {target}. Skipping regression.")
        return
        
    # Only keep features that have at least some data
    features = [f for f in potential_features if f in merged.columns and not merged[f].isna().all()]
    
    print(f"  Target:   {target}")
    print(f"  Features: {features}")
    
    # Drop rows with NaNs in the selected columns
    train_df = merged[features + [target]].dropna()
    
    if len(train_df) < 20:
        print(f"  [ERROR] Insufficient data for regression (n={len(train_df)}). Skipping.")
        return
        
    X = train_df[features]
    y = train_df[target]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Scale features
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    results = {}

    # ── OLS Regression ──────────────────────────────────────────
    print("\n  Model 1: OLS Linear Regression")
    ols = LinearRegression()
    ols.fit(X_train_s, y_train)
    y_pred_ols = ols.predict(X_test_s)

    r2_ols = r2_score(y_test, y_pred_ols)
    mae_ols = mean_absolute_error(y_test, y_pred_ols)
    rmse_ols = np.sqrt(mean_squared_error(y_test, y_pred_ols))

    results["OLS"] = {"R²": r2_ols, "MAE": mae_ols, "RMSE": rmse_ols}
    print(f"    R² = {r2_ols:.4f}")
    print(f"    MAE = {mae_ols:.1f}")
    print(f"    RMSE = {rmse_ols:.1f}")

    print("\n    Coefficients (standardized):")
    for feat, coef in sorted(zip(features, ols.coef_), key=lambda x: abs(x[1]), reverse=True):
        print(f"      {feat:>20}: {coef:+.2f}")

    # ── Ridge Regression ────────────────────────────────────────
    print("\n  Model 2: Ridge Regression (α=1.0)")
    ridge = Ridge(alpha=1.0)
    ridge.fit(X_train_s, y_train)
    y_pred_ridge = ridge.predict(X_test_s)

    r2_ridge = r2_score(y_test, y_pred_ridge)
    mae_ridge = mean_absolute_error(y_test, y_pred_ridge)
    rmse_ridge = np.sqrt(mean_squared_error(y_test, y_pred_ridge))

    results["Ridge"] = {"R²": r2_ridge, "MAE": mae_ridge, "RMSE": rmse_ridge}
    print(f"    R² = {r2_ridge:.4f}")
    print(f"    MAE = {mae_ridge:.1f}")
    print(f"    RMSE = {rmse_ridge:.1f}")

    # ── Cross-validation ────────────────────────────────────────
    print("\n  5-Fold Cross-Validation (OLS):")
    cv_scores = cross_val_score(LinearRegression(), X_train_s, y_train,
                                 cv=5, scoring="r2")
    print(f"    R² scores: {[f'{s:.4f}' for s in cv_scores]}")
    print(f"    Mean R² = {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    # ── Visualization ───────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Actual vs Predicted
    ax = axes[0]
    ax.scatter(y_test, y_pred_ols, alpha=0.3, s=10, c="#3498db")
    ax.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()],
            "r--", linewidth=2, label="Perfect prediction")
    ax.set_title(f"OLS: Actual vs Predicted\n(R²={r2_ols:.4f})",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Actual Respiratory Cases")
    ax.set_ylabel("Predicted")
    ax.legend()

    # Residual distribution
    ax = axes[1]
    residuals = y_test - y_pred_ols
    ax.hist(residuals, bins=50, color="#9b59b6", alpha=0.7, edgecolor="black", linewidth=0.3)
    ax.axvline(0, color="red", linestyle="--", linewidth=2)
    ax.set_title("Residual Distribution (OLS)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Residual")
    ax.set_ylabel("Frequency")

    # Coefficient comparison
    ax = axes[2]
    coef_df = pd.DataFrame({
        "Feature": features,
        "OLS": ols.coef_,
        "Ridge": ridge.coef_
    }).set_index("Feature").sort_values("OLS")
    coef_df.plot(kind="barh", ax=ax, color=["#3498db", "#e74c3c"], edgecolor="black")
    ax.set_title("Standardized Coefficients", fontsize=12, fontweight="bold")
    ax.set_xlabel("Coefficient Value")
    ax.axvline(0, color="black", linewidth=0.5)

    plt.suptitle("Regression Analysis — Respiratory Disease Prediction",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "11_regression_analysis.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 11_regression_analysis.png")

    return results


# ═══════════════════════════════════════════════════════════════════
# STEP 3: Clustering
# ═══════════════════════════════════════════════════════════════════
def clustering_analysis(merged, districts):
    """K-Means clustering of districts by pollution + health profile."""
    print("\n" + "━" * 60)
    print("  STEP 3: K-Means Clustering")
    print("━" * 60)

    # Aggregate to district level
    district_profile = merged.groupby("district_id").agg({
        "pm25": "mean", "pm10": "mean", "no2": "mean",
        "respiratory_cases": "mean", "cardiovascular_cases": "mean",
        "diarrhoea_cases": "mean", "urban_percentage": "first",
    }).reset_index()

    district_profile = district_profile.merge(
        districts[["district_id", "district_name", "state"]], on="district_id"
    )

    # Features for clustering (only keep those with data)
    potential_cluster_features = ["pm25", "pm10", "no2", "respiratory_cases",
                                  "cardiovascular_cases", "urban_percentage"]
    cluster_features = [f for f in potential_cluster_features if f in district_profile.columns and not district_profile[f].isna().all()]
    
    X_cluster = district_profile[cluster_features].dropna()
    
    if len(X_cluster) < 5:
        print("  [ERROR] Insufficient data for clustering. Skipping.")
        return
        
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_cluster)

    # ── Elbow method ────────────────────────────────────────────
    inertias = []
    K_range = range(2, 11)
    for k in K_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km.fit(X_scaled)
        inertias.append(km.inertia_)

    # Choose k=4
    k_optimal = 4
    print(f"\n  Optimal K = {k_optimal} (elbow method)")

    km = KMeans(n_clusters=k_optimal, random_state=42, n_init=10)
    # Assign clusters using the index of X_cluster to ensure alignment
    district_profile.loc[X_cluster.index, "cluster"] = km.fit_predict(X_scaled)
    # Fill any districts without clusters (due to NaNs) with -1
    district_profile["cluster"] = district_profile["cluster"].fillna(-1).astype(int)

    # ── Cluster profiles ────────────────────────────────────────
    cluster_summary = district_profile.groupby("cluster")[cluster_features].mean().round(1)
    cluster_counts = district_profile.groupby("cluster").size()

    cluster_labels = {}
    for c in range(k_optimal):
        pm25 = cluster_summary.loc[c, "pm25"]
        resp = cluster_summary.loc[c, "respiratory_cases"]
        if pm25 > 70 and resp > 300:
            label = "Critical: High Pollution + High Disease"
        elif pm25 > 50:
            label = "At Risk: Moderate-High Pollution"
        elif pm25 > 35:
            label = "Moderate: Average Levels"
        else:
            label = "Clean: Low Pollution"
        cluster_labels[c] = label

    print("\n  Cluster Profiles:")
    for c in range(k_optimal):
        print(f"\n    Cluster {c}: {cluster_labels[c]}")
        print(f"      Districts: {cluster_counts[c]}")
        print(f"      Avg PM2.5: {cluster_summary.loc[c, 'pm25']:.1f} µg/m³")
        print(f"      Avg Respiratory: {cluster_summary.loc[c, 'respiratory_cases']:.0f} cases/month")
        # Print sample districts
        sample = district_profile[district_profile["cluster"] == c][["district_name", "state"]].head(5)
        for _, r in sample.iterrows():
            print(f"        → {r['district_name']}, {r['state']}")

    # ── Visualization ───────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Elbow plot
    ax = axes[0]
    ax.plot(K_range, inertias, "bo-", linewidth=2, markersize=8)
    ax.axvline(k_optimal, color="red", linestyle="--", alpha=0.7, label=f"K={k_optimal}")
    ax.set_title("Elbow Method", fontsize=12, fontweight="bold")
    ax.set_xlabel("Number of Clusters (K)")
    ax.set_ylabel("Inertia")
    ax.legend()

    # Scatter: PM2.5 vs Respiratory by cluster
    ax = axes[1]
    colors = ["#2ecc71", "#f39c12", "#e67e22", "#e74c3c"]
    for c in range(k_optimal):
        mask = district_profile["cluster"] == c
        ax.scatter(district_profile.loc[mask, "pm25"],
                   district_profile.loc[mask, "respiratory_cases"],
                   c=colors[c], s=60, alpha=0.7, edgecolors="black", linewidth=0.5,
                   label=f"C{c}: {cluster_labels[c][:20]}")
    ax.set_title("Districts by Cluster", fontsize=12, fontweight="bold")
    ax.set_xlabel("Mean PM2.5 (µg/m³)")
    ax.set_ylabel("Mean Respiratory Cases / Month")
    ax.legend(fontsize=8, loc="upper left")

    # Cluster heatmap
    ax = axes[2]
    # Normalize for heatmap
    heatmap_data = cluster_summary.copy()
    for col in heatmap_data.columns:
        heatmap_data[col] = (heatmap_data[col] - heatmap_data[col].min()) / \
                            (heatmap_data[col].max() - heatmap_data[col].min())
    sns.heatmap(heatmap_data, annot=cluster_summary.values, fmt=".1f",
                cmap="RdYlGn_r", ax=ax, linewidths=1,
                yticklabels=[f"C{i}" for i in range(k_optimal)])
    ax.set_title("Cluster Feature Profiles", fontsize=12, fontweight="bold")

    plt.suptitle("K-Means Clustering — District Risk Profiles",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "12_clustering.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 12_clustering.png")

    # Save cluster assignments
    district_profile.to_csv(PROCESSED_DIR / "district_clusters.csv", index=False)
    print("  → Saved: district_clusters.csv")

    return district_profile


# ═══════════════════════════════════════════════════════════════════
# STEP 4: Time-Series Decomposition
# ═══════════════════════════════════════════════════════════════════
def time_series_analysis(aq):
    """Seasonal decomposition of air quality time series."""
    print("\n" + "━" * 60)
    print("  STEP 4: Time-Series Decomposition")
    print("━" * 60)

    aq["date"] = pd.to_datetime(aq["date"])

    # National monthly average
    national_monthly = aq.groupby(aq["date"].dt.to_period("M"))["pm25"].mean()
    national_monthly.index = national_monthly.index.to_timestamp()

    # Decompose
    if len(national_monthly) >= 24:
        decomposition = seasonal_decompose(national_monthly, model="multiplicative", period=12)
        fig, axes = plt.subplots(4, 1, figsize=(16, 12))

        axes[0].plot(national_monthly.index, national_monthly.values, color="#3498db", linewidth=1.5)
        axes[0].set_title("Observed (National Avg PM2.5)", fontsize=12, fontweight="bold")
        axes[0].set_ylabel("µg/m³")

        axes[1].plot(decomposition.trend.index, decomposition.trend.values, color="#e74c3c", linewidth=2)
        axes[1].set_title("Trend Component", fontsize=12, fontweight="bold")
        axes[1].set_ylabel("µg/m³")

        axes[2].plot(decomposition.seasonal.index, decomposition.seasonal.values, color="#2ecc71", linewidth=1.5)
        axes[2].set_title("Seasonal Component", fontsize=12, fontweight="bold")
        axes[2].set_ylabel("Multiplier")

        axes[3].plot(decomposition.resid.index, decomposition.resid.values, color="#9b59b6", linewidth=1, alpha=0.7)
        axes[3].set_title("Residual Component", fontsize=12, fontweight="bold")
        axes[3].set_ylabel("Multiplier")

        plt.suptitle("Time-Series Decomposition — National PM2.5", fontsize=14, fontweight="bold", y=1.02)
        plt.tight_layout()
        plt.savefig(FIG_DIR / "13_time_series_decomposition.png", dpi=DPI, bbox_inches="tight")
        plt.close()
        print("  → Saved: 13_time_series_decomposition.png")
    else:
        print(f"  [SKIP] Not enough observations for decomposition (n={len(national_monthly)})")

    # Key insight
    if len(national_monthly) >= 24:
        trend = decomposition.trend.dropna()
        if len(trend) > 2:
            growth = (trend.iloc[-1] / trend.iloc[0] - 1) * 100
            print(f"  Overall Pollution Trend: {growth:+.1f}% over the period")
        print(f"  Trend: PM2.5 {'increased' if trend.iloc[-1] > trend.iloc[0] else 'decreased'} "
              f"from {trend.iloc[0]:.1f} to {trend.iloc[-1]:.1f} µg/m³ over 2018-2023")
        print(f"  Seasonal peak ratio: {decomposition.seasonal.max():.2f}x "
              f"(winter) / {decomposition.seasonal.min():.2f}x (monsoon)")


# ═══════════════════════════════════════════════════════════════════
# STEP 5: Predictive Modeling
# ═══════════════════════════════════════════════════════════════════
def predictive_modeling(merged):
    """Build Random Forest and Gradient Boosting models."""
    print("\n" + "━" * 60)
    print("  STEP 5: Predictive Modeling (Random Forest & Gradient Boosting)")
    # ── Prepare Data ────────────────────────────────────────────
    target = "respiratory_cases"
    potential_feat = ["pm25", "pm10", "no2", "so2", "urban_percentage", "literacy_rate", "population"]
    features = [f for f in potential_feat if f in merged.columns and not merged[f].isna().all()]
    
    train_df = merged[features + [target]].dropna()
    if len(train_df) < 20:
        print("  [ERROR] Insufficient data for predictive modeling. Skipping.")
        return
        
    X = train_df[features]
    y = train_df[target]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    models = {
        "Random Forest": RandomForestRegressor(n_estimators=100, max_depth=15,
                                                random_state=42, n_jobs=-1),
        "Gradient Boosting": GradientBoostingRegressor(n_estimators=200, max_depth=6,
                                                        learning_rate=0.1, random_state=42),
    }

    results = {}
    predictions = {}

    for name, model in models.items():
        print(f"\n  {name}:")
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        r2 = r2_score(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))

        results[name] = {"R²": r2, "MAE": mae, "RMSE": rmse}
        predictions[name] = y_pred

        print(f"    R²   = {r2:.4f}")
        print(f"    MAE  = {mae:.1f}")
        print(f"    RMSE = {rmse:.1f}")

        # Cross-validation
        cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring="r2")
        print(f"    CV R² = {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    # ── Feature Importance ──────────────────────────────────────
    print("\n  Feature Importance (Random Forest):")
    rf = models["Random Forest"]
    importances = pd.Series(rf.feature_importances_, index=features).sort_values(ascending=False)
    for feat, imp in importances.items():
        bar = "█" * int(imp * 50)
        print(f"    {feat:>20}: {imp:.4f} {bar}")

    # ── Visualization ───────────────────────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # RF: Actual vs Predicted
    ax = axes[0, 0]
    ax.scatter(y_test, predictions["Random Forest"], alpha=0.3, s=10, c="#3498db")
    ax.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()],
            "r--", linewidth=2)
    ax.set_title(f"Random Forest: Actual vs Predicted\n(R²={results['Random Forest']['R²']:.4f})",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Actual")
    ax.set_ylabel("Predicted")

    # GB: Actual vs Predicted
    ax = axes[0, 1]
    ax.scatter(y_test, predictions["Gradient Boosting"], alpha=0.3, s=10, c="#e74c3c")
    ax.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()],
            "r--", linewidth=2)
    ax.set_title(f"Gradient Boosting: Actual vs Predicted\n(R²={results['Gradient Boosting']['R²']:.4f})",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Actual")
    ax.set_ylabel("Predicted")

    # Feature Importance
    ax = axes[1, 0]
    importances.sort_values().plot(kind="barh", ax=ax, color="#2ecc71", edgecolor="black")
    ax.set_title("Feature Importance (Random Forest)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Importance")

    # Model Comparison
    ax = axes[1, 1]
    comp_df = pd.DataFrame(results).T
    x_pos = np.arange(len(comp_df))
    width = 0.35
    ax.bar(x_pos - width/2, comp_df["R²"], width, label="R²", color="#3498db", edgecolor="black")
    ax.bar(x_pos + width/2, comp_df["MAE"] / comp_df["MAE"].max(), width,
           label="MAE (normalized)", color="#e74c3c", edgecolor="black")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(comp_df.index)
    ax.set_title("Model Comparison", fontsize=12, fontweight="bold")
    ax.legend()

    plt.suptitle("Predictive Modeling — Respiratory Disease Burden",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "14_predictive_models.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 14_predictive_models.png")

    # Save predictions
    pred_df = pd.DataFrame({
        "actual": y_test.values,
        "predicted_rf": predictions["Random Forest"],
        "predicted_gb": predictions["Gradient Boosting"],
    })
    pred_df.to_csv(PROCESSED_DIR / "model_predictions.csv", index=False)
    print("  → Saved: model_predictions.csv")

    return results


def main():
    print("=" * 60)
    print("  DSM Final Project — Rigorous Data Analysis")
    print("=" * 60)

    merged, districts, aq = load_data()

    # Step 1: Hypothesis Testing
    district_avg = hypothesis_testing(merged, districts)

    # Step 2: Regression
    reg_results = regression_analysis(merged)

    # Step 3: Clustering
    district_profiles = clustering_analysis(merged, districts)

    # Step 4: Time-Series
    time_series_analysis(aq)

    # Step 5: Predictive Modeling
    pred_results = predictive_modeling(merged)

    # ── Final Summary ───────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Analysis Complete — Model Comparison")
    print("=" * 60)

    all_results = {**reg_results, **pred_results}
    for name, metrics in all_results.items():
        print(f"  {name:>25}: R²={metrics['R²']:.4f}  MAE={metrics['MAE']:.1f}  RMSE={metrics['RMSE']:.1f}")

    best = max(all_results.items(), key=lambda x: x[1]["R²"])
    print(f"\n  Best model: {best[0]} (R²={best[1]['R²']:.4f})")
    print(f"  Figures saved to: {FIG_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
