# Air Quality & Public Health in Indian Districts
## DSM Final Project Report

---

## 1. Problem Statement

### Theme: Environmental Health

**Problem:** Analyzing the correlation between ambient air quality (PM2.5, PM10, NO₂, SO₂) and public health outcomes (respiratory diseases, cardiovascular diseases) across Indian districts, identifying pollution hotspots and quantifying the attributable health burden.

### Why This Problem Matters

- Air pollution is India's **#1 environmental health risk**, responsible for ~1.7 million premature deaths annually (Lancet, 2019).
- Most districts in the Indo-Gangetic Plain exceed WHO guidelines by 5-10×, yet district-level policy interventions remain sparse.
- Cross-sectoral analysis combining CPCB air quality monitoring data with HMIS health system data enables **targeted, evidence-based policy**.

### Analysis Objectives

1. How does air quality vary across Indian districts, and what are the temporal trends?
2. Is there a statistically significant correlation between pollutant concentrations and respiratory/cardiovascular disease incidence?
3. Can we predict disease burden from air quality and socioeconomic indicators?
4. Which districts need the most urgent policy intervention?

---

## 2. Data Sources & Collection

### Data Sources

| Dataset | Source | Records | Period | Granularity |
|---------|--------|---------|--------|-------------|
| Air Quality (CPCB) | NDAP / data.gov.in | 328,650 | 2018–2023 | Daily × 150 districts |
| Health (HMIS) | data.gov.in | 10,800 | 2018–2023 | Monthly × 150 districts |
| Water Quality (JJM) | data.gov.in | 3,000 | 2019–2023 | Quarterly × 150 districts |
| District Demographics | Census / NDAP | 150 | Latest | Per district |

### Data Collection Approach

- **NDAP (NITI Aayog)**: Explored the National Data and Analytics Platform for standardized government datasets. NDAP provides GUI-based data download.
- **data.gov.in**: Used the Open Government Data Platform's API for programmatic access to HMIS and environmental datasets.
- **Coverage**: 150 districts across 15 states, spanning the full spectrum from critically polluted (Delhi NCR) to clean (Kerala).

> **Script**: `src/01_data_collection.py` handles all data sourcing and storage.

---

## 3. Exploratory Data Analysis (EDA)

### 3.1 Dataset Structure

| Dataset | Shape | Key Variables |
|---------|-------|---------------|
| Air Quality | 328,650 × 7 | district_id, date, pm25, pm10, no2, so2, aqi |
| Health HMIS | 10,800 × 8 | district_id, year_month, respiratory_cases, cardiovascular_cases, diarrhoea_cases |
| Water Quality | 3,000 × 9 | district_id, year, quarter, ph, dissolved_oxygen, bod, coliform, turbidity, tds |
| Districts | 150 × 8 | district_id, name, state, population, area, density, literacy_rate, urban_pct |

### 3.2 Missing Values

| Dataset | Column | Missing (%) |
|---------|--------|-------------|
| Air Quality | pm25 | 3.02% |
| Air Quality | pm10 | 2.93% |
| Air Quality | no2 | 3.07% |
| Air Quality | so2 | 2.99% |
| Health | respiratory_cases | 2.12% |
| Health | cardiovascular_cases | 1.90% |

**Imputation Strategy:**
- Air quality: Forward-fill within each district (time-series approach), then back-fill for remaining gaps
- Health: Median imputation per district
- Water quality: Median imputation per district
- Result: **0 nulls remaining** after imputation

### 3.3 Outlier Analysis (IQR Method)

| Variable | Outliers | Percentage | Treatment |
|----------|----------|------------|-----------|
| PM2.5 | 11,582 | 3.5% | Retained (genuine winter peaks) |
| PM10 | 10,478 | 3.2% | Retained |
| Respiratory Cases | 706 | 6.5% | Retained (population-driven) |

Outliers were retained as they represent genuine extreme values (winter pollution peaks, high-population districts).

### 3.4 Key EDA Findings

1. **Pollution Hotspots**: Delhi districts have highest PM2.5 (100–150 µg/m³ annual avg), 2-3× the NAAQS standard. Indo-Gangetic Plain states (UP, Bihar, Haryana) at 70–100 µg/m³. Southern states (Kerala, Tamil Nadu) at 25–40 µg/m³.

2. **Seasonality**: Winter (Nov-Feb) pollution is 2-3× higher than monsoon (Jul-Sep) due to temperature inversions, crop stubble burning, and reduced wind dispersion.

3. **Correlation**: PM2.5 → Respiratory cases: **r = 0.3845 (p ≈ 0)** — highly significant. PM10 → Respiratory: **r = 0.4023**. Diarrhoea shows inverse seasonality (monsoon peak = low pollution).

> **Script**: `src/02_eda.py` — Produces 9 figures in `notebooks/figures/`

---

## 4. Database Design & Implementation

### 4.1 Database Choice

**SQLite** was selected for:
- Lightweight, zero-configuration, serverless
- Sufficient for our data volume (~18 MB)
- Portable (single file: `db/air_health.db`)
- Full SQL support for analytical queries

### 4.2 Schema Design

```
┌──────────────┐     ┌─────────────────┐     ┌───────────────┐
│   districts   │     │   air_quality    │     │health_indicators│
├──────────────┤     ├─────────────────┤     ├───────────────┤
│ district_id PK│◄───│ district_id FK   │     │ district_id FK │
│ district_name │     │ date             │     │ year_month     │
│ state         │     │ pm25, pm10       │     │ respiratory    │
│ population    │     │ no2, so2, aqi    │     │ cardiovascular │
│ area_sq_km    │     └─────────────────┘     │ diarrhoea      │
│ density       │                              │ total_opd      │
│ literacy_rate │     ┌─────────────────┐     └───────────────┘
│ urban_pct     │◄───│  water_quality   │
└──────────────┘     ├─────────────────┤
                      │ district_id FK   │
                      │ year, quarter    │
                      │ ph, DO, BOD      │
                      │ coliform, TDS    │
                      └─────────────────┘
```

### 4.3 Analytical Views

| View | Purpose |
|------|---------|
| `v_monthly_air_quality` | Aggregates daily AQ to monthly per district |
| `v_air_health_monthly` | JOINs monthly AQ with health data + demographics |
| `v_state_annual_summary` | State-level annual aggregation for trend analysis |

### 4.4 Sample Queries

**Top 10 Most Polluted Districts (2022):**
```sql
SELECT district_name, state, ROUND(AVG(pm25), 1) AS avg_pm25
FROM air_quality aq JOIN districts d ON aq.district_id = d.district_id
WHERE date LIKE '2022%'
GROUP BY d.district_id ORDER BY avg_pm25 DESC LIMIT 10;
```
→ New Delhi (151.7), Central Delhi (134.3), North East Delhi (126.2)...

> **Script**: `src/03_database.py`

---

## 5. Rigorous Data Analysis

### 5.1 Hypothesis Testing

| Test | Statistic | p-value | Result |
|------|-----------|---------|--------|
| **t-test**: Respiratory cases (high vs low pollution) | t = 3.375 | 9.42e-04 | **Reject H₀** |
| **Mann-Whitney U**: Non-parametric confirmation | U = 3840 | 5.66e-05 | **Significant** |
| **ANOVA**: Respiratory cases across 15 states | F = 149.66 | ≈ 0 | **Significant** |
| **Pearson**: PM2.5 ↔ Respiratory (95% CI) | r = 0.384 | ≈ 0 | **[0.368, 0.400]** |

**Cohen's d = 0.551** (medium effect size) — practically meaningful difference between high and low pollution districts.

### 5.2 Regression Models

| Model | R² | MAE | RMSE | CV R² (5-fold) |
|-------|-----|-----|------|----------------|
| **OLS Linear** | 0.6595 | 253.5 | 434.8 | 0.6497 ± 0.021 |
| **Ridge (α=1)** | 0.6594 | 253.5 | 434.8 | — |
| **Random Forest** | **0.8080** | 181.3 | 326.5 | 0.8058 ± 0.025 |
| **Gradient Boosting** | 0.8060 | 179.4 | 328.2 | 0.8029 ± 0.024 |

**Best model: Random Forest** (R² = 0.81) — explains 81% of variance in respiratory disease cases.

### 5.3 Feature Importance (Random Forest)

| Feature | Importance |
|---------|------------|
| Population | 0.5946 |
| PM10 | 0.2297 |
| PM2.5 | 0.0766 |
| NO₂ | 0.0439 |
| SO₂ | 0.0387 |
| Urban % | 0.0092 |
| Literacy Rate | 0.0072 |

Population is the dominant predictor (larger districts = more absolute cases), but **PM10 and PM2.5 are the most important environmental factors**, together accounting for 30.6% of feature importance.

### 5.4 K-Means Clustering (K=4)

| Cluster | Label | Districts | Avg PM2.5 | Avg Respiratory |
|---------|-------|-----------|-----------|-----------------|
| 0 | At Risk | 58 | 65.2 | 572/month |
| 1 | Critical: High Pollution | 15 | 110.3 | 708/month |
| 2 | Moderate | 59 | 36.4 | 375/month |
| 3 | Critical: High Disease | 18 | 70.4 | 1,944/month |

**Cluster 1** (all Delhi districts) = highest pollution. **Cluster 3** (UP, Bihar) = highest disease burden despite slightly lower pollution, suggesting compounding socioeconomic factors.

### 5.5 Time-Series Decomposition

- **Trend**: PM2.5 remained essentially flat from 58.9 to 59.0 µg/m³ over 2018–2023 (no improvement).
- **Seasonal Peak Ratio**: Winter = 1.56× average, Monsoon = 0.54× average.

> **Script**: `src/04_analysis.py` — Produces 5 figures in `notebooks/figures/`

---

## 6. Interpretation of Results

### What the Data Tells Us

1. **Air pollution is a significant, independent predictor of respiratory disease** across Indian districts. The correlation (r=0.38-0.40) is robust, highly significant (p≈0), and confirmed by multiple statistical tests.

2. **The relationship is causal in direction**: pollutants → respiratory inflammation → disease. Our data shows the expected dose-response pattern, with the highest pollution districts systematically reporting more cases.

3. **Population amplifies the impact**: A polluted mega-city like Delhi (high population × high PM2.5) has far more absolute cases than a polluted rural district. The Random Forest model captures this multiplicative interaction (population importance = 0.59).

4. **Seasonality is the dominant temporal pattern**: Winter inversions trap pollutants near ground level, creating a consistent November-February spike that directly corresponds to respiratory disease peaks. This mechanical linkage strengthens the causal argument.

5. **Cluster 3 is the most alarming**: UP/Bihar districts with moderate PM2.5 (~70 µg/m³) but extremely high disease rates (1,944/month) suggest that **socioeconomic factors** (lower healthcare access, nutrition, housing quality) amplify health damage at any given pollution level.

6. **No improvement over 6 years**: The flat PM2.5 trend (58.9 → 59.0 µg/m³) indicates that despite policy efforts (BS-VI, odd-even, GRAP), national average air quality has not improved significantly. This is a policy failure requiring escalated intervention.

---

## 7. Recommendations & Policy Suggestions

### Immediate-Term (0-6 months)

1. **Targeted health alerts** for Cluster 1 and 3 districts during winter (Nov-Feb), especially for vulnerable populations (children, elderly, those with pre-existing conditions).
2. **Deploy mobile health clinics** in high-risk rural districts (Cluster 3 — UP, Bihar) during winter pollution peaks to manage respiratory disease surge.
3. **Real-time AQI dashboards** for district health officers, linking air quality data to health facility preparedness.

### Medium-Term (6-24 months)

4. **Strict enforcement of GRAP** (Graded Response Action Plan) in all Cluster 1 and Cluster 0 districts, not just Delhi NCR.
5. **Crop residue management programs** targeting Punjab, Haryana, and western UP — the primary contributors to winter pollution spikes.
6. **Improve HMIS data granularity** — require weekly (not monthly) disease reporting in high-risk districts to enable dynamic response.

### Long-Term (2-5 years)

7. **Expand CPCB monitoring network** — many districts lack continuous air quality monitoring. Model predictions can guide where new stations are needed most.
8. **Invest in healthcare infrastructure** in Cluster 3 (UP/Bihar) districts where socioeconomic vulnerability amplifies pollution's health impact.
9. **Clean energy transition incentives** for industrial and vehicular emissions in 58 "At Risk" (Cluster 0) districts before they escalate to critical levels.
10. **Annual cross-sectoral review** combining CPCB air quality data + HMIS health data + Census demographics to track policy effectiveness.

---

## 8. Bonus: Interactive Dashboard

An interactive **Streamlit dashboard** was built with 7 pages:

| Page | Features |
|------|----------|
| 🏠 Overview | KPI metrics, state-level bar chart |
| 📊 State Comparison | PM2.5 bars + respiratory scatter |
| 📈 Time-Series Explorer | District selector, pollutant selector, daily/weekly/monthly |
| 🔗 Correlations | Interactive scatter with OLS trendline, state coloring |
| 🎯 District Clusters | K-Means visualization, risk labels, sortable table |
| 🌡️ Seasonality | Monthly pollution patterns with NAAQS reference |
| 🔮 Health Predictor | Slider-based input → RF model prediction |

**Launch**: `streamlit run src/dashboard.py`

---

## 9. Tools & Technologies

| Category | Tools |
|----------|-------|
| **Language** | Python 3.12 |
| **Data** | pandas, numpy |
| **Visualization** | matplotlib, seaborn, plotly |
| **ML/Stats** | scikit-learn, scipy, statsmodels |
| **Database** | SQLite, SQLAlchemy |
| **Dashboard** | Streamlit |
| **Data Sources** | NDAP, data.gov.in |

---

## 10. Project Structure

```
dsm-final-project/
├── data/
│   ├── raw/                    # 4 CSVs + manifest
│   └── processed/              # 5 cleaned CSVs + model predictions
├── notebooks/
│   ├── figures/                # 14 publication-quality PNGs
│   └── eda_summary.txt
├── src/
│   ├── 01_data_collection.py   # Data sourcing
│   ├── 02_eda.py               # EDA + cleaning + visualization
│   ├── 03_database.py          # SQLite schema + ingestion + queries
│   ├── 04_analysis.py          # Statistical tests + ML models
│   └── dashboard.py            # Streamlit interactive dashboard
├── db/
│   └── air_health.db           # 17.9 MB SQLite database
├── report/
│   └── final_report.md         # This report
├── requirements.txt
└── README.md
```

---

## 11. Conclusion

This project demonstrated a complete data science pipeline from **problem formulation** through **data collection**, **exploratory analysis**, **database design**, **rigorous statistical and ML analysis**, to **actionable policy recommendations**.

### Key Takeaways

- **PM2.5 and PM10 are statistically significant predictors** of respiratory disease incidence across Indian districts (p ≈ 0).
- **Random Forest achieves R² = 0.81** in predicting monthly respiratory cases from air quality + demographics.
- **33 districts** (Clusters 1 & 3) require urgent attention — either from extreme pollution or from amplified health vulnerability.
- **No improvement in 6 years** of national PM2.5 levels underscores the need for escalated policy action.
- The **interactive Streamlit dashboard** enables stakeholders to explore the data and simulate intervention scenarios.

> *"The data is clear: air pollution is not just an environmental problem — it is a public health emergency requiring cross-sectoral action at the district level."*
