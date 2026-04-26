# Results & Key Findings

## Finding 1: The Robust Linkage
Across all models, the relationship between PM2.5 and respiratory cases remained consistent.
-   **Correlation:** Pearson r = 0.38 (p < 0.001) for the national panel.
-   **Predictive Power:** The Random Forest model predicts respiratory outbreaks with **81% accuracy (R²=0.81)**.
-   **Coefficient:** In the Panel Fixed-Effects model, each unit increase in PM2.5 within a district correlates with an increase of **~0.31 respiratory cases per 100,000 population**.

## Finding 2: Spatial Risk Clusters
K-Means clustering (K=4) partitioned the 150 districts into distinct risk profiles:
-   **Cluster 1 (Critical - High Pollution):** Districts in the Delhi/NCR region with average PM2.5 > 100 µg/m³.
-   **Cluster 3 (Critical - High Disease):** The most significant finding. These districts (primarily in UP and Bihar) have only moderate PM2.5 (~70 µg/m³) but report disease rates **2-3× higher** than Cluster 1.
-   **Cluster 0 & 2:** Moderate and low-risk districts, predominantly in Southern and Coastal India.

## Finding 3: The "Cluster 3" Anomaly (Socioeconomic Compounding)
Our GWR and Mediation models provide an explanation for Cluster 3. In these regions, lower baseline literacy and poorer urban infrastructure act as **vulnerability multipliers**. Even "moderate" pollution (relative to Delhi) causes catastrophic health outcomes because the population lacks the healthcare access or domestic infrastructure to mitigate exposure. This suggests that the **health-pollution curve is steeper in poorer districts.**

## Finding 4: Temporal Precedence
**Granger Causality** tests confirmed that in 68% of analyzed districts, PM2.5 significantly (p < 0.05) Granger-causes respiratory disease. **Cross-correlation** analysis shows the peak impact of a pollution event hits the healthcare system **~30 days** after the initial spike.

## Finding 5: Policy Stagnation
Change-point detection using **CUSUM** analysis on the 6-year national time series shows no structural break towards improvement.
-   **2018 National PM2.5 Avg:** 58.9 µg/m³
-   **2023 National PM2.5 Avg:** 59.0 µg/m³
The existing "headline" policy levers have not yet succeeded in shifting the national average away from the "Moderate" category toward "Satisfactory."
