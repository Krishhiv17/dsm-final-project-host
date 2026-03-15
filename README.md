# Air Quality & Public Health in Indian Districts

**DSM Final Project** — Analyzing the relationship between ambient air quality (PM2.5, PM10, NO₂, SO₂) and public health outcomes (respiratory & cardiovascular diseases) across Indian districts.

## Quick Start

```bash
pip install -r requirements.txt
python src/01_data_collection.py
python src/03_database.py
streamlit run src/dashboard.py
```

## Project Structure

```
data/raw/          → Downloaded CSVs from NDAP & data.gov.in
data/processed/    → Cleaned, merged datasets
notebooks/         → Jupyter notebooks for EDA & analysis
src/               → Python scripts (collection, database, dashboard)
db/                → SQLite database (air_health.db)
report/            → Final report
```

## Data Sources

| Dataset | Source | Format |
|---------|--------|--------|
| Air Quality (CPCB stations) | NDAP / data.gov.in | CSV |
| Health Indicators (HMIS) | data.gov.in | CSV |
| Water Quality (JJM) | data.gov.in | CSV |
| District Demographics | Census / NDAP | CSV |
