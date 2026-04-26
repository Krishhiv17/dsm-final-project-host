# Data & Pipeline Architecture

## Data Sources: A Multi-Domain Synthesis
This study integrates three disparate datasets to form a unified spatiotemporal panel of 150 districts:
1.  **Air Quality (CPCB via NDAP/data.gov.in):** Daily records of PM2.5, PM10, NO₂, and SO₂ (~328,000 observations).
2.  **Public Health (HMIS):** Monthly records of respiratory, cardiovascular, and diarrhoeal cases (~10,800 observations).
3.  **District Demographics (Census 2011/NDAP):** Static variables including literacy rates, urbanisation percentages, population density, and area.
4.  **Water Quality (JJM):** Quarterly chemical and biological indicators as secondary controls.

## The Data Pipeline
The pipeline was engineered to handle large-scale, messy administrative data:
-   **Cleaning & Imputation:** Addressed missing values using regional-median interpolation and seasonal-trend decomposition for time-series continuity.
-   **Temporal Alignment:** Aggregated daily air quality readings into monthly averages to align with the granularity of HMIS health reporting.
-   **Spatial Geocoding:** Mapped districts to latitudes and longitudes to enable distance-based spatial graph construction and Geographically Weighted Regression (GWR).

## Feature Engineering
Key calculated metrics included:
-   **Pollutant Deciles:** Used for dose-response curves.
-   **Lagged Features:** 1–6 month lags of pollutants to test for delayed health responses.
-   **Spatial Lags:** Weighted averages of neighbouring districts' PM2.5 to account for transboundary pollution drift.
-   **Standardised Rates:** Converted raw case counts to "Cases per 100,000 population" to enable comparison across districts of varying sizes.
