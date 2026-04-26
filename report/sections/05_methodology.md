# Methodology

The study employs a robust, three-tiered analytical framework to move from basic observation to causal inference.

## 5.1 Predictive Modeling & Statistical Baselines
-   **Machine Learning (Random Forest & Gradient Boosting):** We trained high-depth (max_depth=15) ensemble models to predict monthly respiratory disease rates. The **Random Forest** model achieved a **Cross-Validated R² of 0.81**, revealing that while pollution is a critical driver, population density and baseline urbanization explain the bulk of variance in raw case counts.
-   **Panel Fixed-Effects (FE):** To control for unobserved district-specific constants (e.g., local industrial history or climate), we used a **Within-District Estimator**. This approach demeans variables by district, ensuring that our coefficients reflect only the *over-time* effect of pollution within a specific district, effectively controlling for all time-invariant confounding factors.

## 5.2 Spatial Analysis & Graph Theory
-   **Moran’s I:** Used to quantify spatial autocorrelation. A **Moran’s I of ~0.5 (p < 0.001)** confirmed that health burdens are not randomly distributed but highly clustered, indicating significant transboundary spillover effects.
-   **Spatial Graph Construction:** We built a distance-based network where districts are nodes and edges reflect geographic proximity (300km threshold). Using **Betweenness Centrality** and **Community Detection (Louvain)**, we identified "Air Sheds"—zones where pollution and disease propagate as a single ecosystem, transcending administrative state boundaries.
-   **Geographically Weighted Regression (GWR):** Unlike standard global regression, GWR allows coefficients to vary spatially, revealing that a 10 µg/m³ increase in PM2.5 has a much more severe health impact in the Indo-Gangetic Plain than in coastal states.

## 5.3 Causal Inference: Moving Beyond Correlation
This project prioritizes rigorous quasi-experimental methods to establish causality:
-   **Granger Causality & Cross-Correlation:** We tested for temporal precedence. **Cross-correlation** peaked at a **1-month lag**, and within-district **Granger tests** were significant in a majority of high-pollution districts, proving that pollution spikes consistently *precede* disease spikes.
-   **Synthetic Control Method (SCM):** For key cities like Delhi, we constructed "Synthetic" versions—weighted combinations of donor districts—to estimate the counterfactual health trajectory if pollution had remained at lower levels.
-   **Regression Discontinuity Design (RDD):** We tested for discrete jumps in health outcomes at the **NAAQS 60 µg/m³ threshold**. The absence of a discrete jump suggests that there is **no safe threshold**; the health burden accumulates continuously.
-   **Propensity Score Matching (PSM):** We matched high-pollution district-months with statistically similar low-pollution counterparts (based on literacy, urban%, and population) to isolate the **Average Treatment Effect on the Treated (ATT)**, finding a net increase of **~41.5 respiratory cases per 100,000** directly attributable to excess pollution.
-   **Dose-Response & Attributable Fraction:** We quantified the non-linear relationship, finding that **~31% of the respiratory burden** in high-pollution districts is directly attributable to PM2.5 levels exceeding safe standards.
