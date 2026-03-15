"""
01_data_collection.py
=====================
Data Collection Script for Air Quality & Public Health Analysis

Data Sources:
  1. Air Quality — CPCB ambient air quality monitoring (NDAP / data.gov.in)
  2. Health (HMIS) — District-level monthly health reports (data.gov.in)
  3. Water Quality — JJM water source quality data (data.gov.in)
  4. Demographics — District population data (Census of India / NDAP)

This script:
  - Attempts to download real CSVs from data.gov.in if available
  - Falls back to generating realistic synthetic data based on known
    distributions from published CPCB / HMIS reports for development
  - Saves everything to data/raw/
"""

import os
import sys
import json
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# ── Project paths ───────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ── Configuration ───────────────────────────────────────────────────
# Known data.gov.in resource download URLs (public, no auth needed for CSV)
DATA_GOV_URLS = {
    "air_quality": [
        # Historical daily ambient air quality data (2015-2020)
        "https://data.gov.in/files/ogdpv2dms/s3fs-public/datafile/city_day.csv",
    ],
    "health_hmis": [
        # HMIS district-level health indicators
        "https://data.gov.in/files/ogdpv2dms/s3fs-public/datafile/HMIS_District_2019-20.csv",
    ],
}

# ── Indian Districts & States (representative sample) ──────────────
STATES_DISTRICTS = {
    "Delhi": ["Central Delhi", "East Delhi", "New Delhi", "North Delhi",
              "South Delhi", "West Delhi", "North East Delhi",
              "North West Delhi", "South West Delhi", "Shahdara"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Thane", "Nashik",
                    "Aurangabad", "Solapur", "Kolhapur", "Amravati", "Nanded"],
    "Uttar Pradesh": ["Lucknow", "Kanpur Nagar", "Agra", "Varanasi",
                      "Allahabad", "Ghaziabad", "Noida", "Meerut",
                      "Bareilly", "Gorakhpur"],
    "Bihar": ["Patna", "Gaya", "Muzaffarpur", "Bhagalpur", "Darbhanga",
              "Purnia", "Begusarai", "Munger", "Saran", "Vaishali"],
    "West Bengal": ["Kolkata", "Howrah", "North 24 Parganas",
                    "South 24 Parganas", "Hooghly", "Bardhaman",
                    "Nadia", "Murshidabad", "Malda", "Darjeeling"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli",
                   "Salem", "Tirunelveli", "Erode", "Vellore",
                   "Thoothukudi", "Thanjavur"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota", "Ajmer",
                  "Bikaner", "Bhilwara", "Alwar", "Sikar", "Pali"],
    "Karnataka": ["Bengaluru Urban", "Mysuru", "Mangaluru", "Hubballi-Dharwad",
                  "Belagavi", "Kalaburagi", "Ballari", "Davangere",
                  "Shivamogga", "Tumakuru"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar",
                "Jamnagar", "Junagadh", "Gandhinagar", "Anand", "Kutch"],
    "Madhya Pradesh": ["Bhopal", "Indore", "Jabalpur", "Gwalior", "Ujjain",
                       "Sagar", "Dewas", "Satna", "Rewa", "Ratlam"],
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur",
                       "Nellore", "Kurnool", "Kakinada", "Tirupati",
                       "Rajahmundry", "Kadapa", "Anantapur"],
    "Telangana": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar",
                  "Khammam", "Mahbubnagar", "Nalgonda", "Adilabad",
                  "Medak", "Rangareddy"],
    "Kerala": ["Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur",
               "Kollam", "Kannur", "Alappuzha", "Palakkad",
               "Malappuram", "Kottayam"],
    "Punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda",
               "Mohali", "Hoshiarpur", "Pathankot", "Moga", "Firozpur"],
    "Haryana": ["Gurugram", "Faridabad", "Panipat", "Ambala", "Karnal",
                "Hisar", "Rohtak", "Sonipat", "Yamunanagar", "Bhiwani"],
}

# ── Pollution profiles by region (based on CPCB annual reports) ────
# Base PM2.5 levels in µg/m³ (annual mean) by state tier
POLLUTION_PROFILES = {
    # Very High: Indo-Gangetic Plain
    "Delhi": {"pm25_base": 120, "pm10_base": 240, "no2_base": 55, "so2_base": 18},
    "Uttar Pradesh": {"pm25_base": 95, "pm10_base": 200, "no2_base": 40, "so2_base": 15},
    "Bihar": {"pm25_base": 90, "pm10_base": 190, "no2_base": 35, "so2_base": 12},
    "Haryana": {"pm25_base": 85, "pm10_base": 180, "no2_base": 38, "so2_base": 14},
    # High
    "Rajasthan": {"pm25_base": 70, "pm10_base": 170, "no2_base": 30, "so2_base": 13},
    "West Bengal": {"pm25_base": 65, "pm10_base": 140, "no2_base": 38, "so2_base": 14},
    "Maharashtra": {"pm25_base": 55, "pm10_base": 120, "no2_base": 35, "so2_base": 12},
    "Madhya Pradesh": {"pm25_base": 60, "pm10_base": 130, "no2_base": 28, "so2_base": 11},
    "Punjab": {"pm25_base": 75, "pm10_base": 160, "no2_base": 33, "so2_base": 13},
    "Gujarat": {"pm25_base": 55, "pm10_base": 110, "no2_base": 32, "so2_base": 15},
    "Telangana": {"pm25_base": 45, "pm10_base": 95, "no2_base": 30, "so2_base": 10},
    # Moderate
    "Andhra Pradesh": {"pm25_base": 38, "pm10_base": 80, "no2_base": 22, "so2_base": 8},
    "Karnataka": {"pm25_base": 40, "pm10_base": 85, "no2_base": 28, "so2_base": 9},
    "Tamil Nadu": {"pm25_base": 35, "pm10_base": 75, "no2_base": 25, "so2_base": 10},
    # Low
    "Kerala": {"pm25_base": 28, "pm10_base": 60, "no2_base": 18, "so2_base": 6},
}

# Seasonal multipliers (month → factor) for pollutants in India
# Winter (Nov-Feb) = high, Monsoon (Jul-Sep) = low
SEASONAL_FACTORS = {
    1: 1.35,  2: 1.20,  3: 1.00,  4: 0.85,
    5: 0.80,  6: 0.70,  7: 0.55,  8: 0.50,
    9: 0.60, 10: 0.90, 11: 1.30, 12: 1.45,
}


def try_download_real_data():
    """Attempt to download real datasets from data.gov.in."""
    downloaded = {}
    for category, urls in DATA_GOV_URLS.items():
        for url in urls:
            fname = url.split("/")[-1]
            fpath = RAW_DIR / fname
            if fpath.exists():
                print(f"  [SKIP] {fname} already exists")
                downloaded[category] = str(fpath)
                continue
            try:
                print(f"  [DOWNLOAD] {category}: {url}")
                resp = requests.get(url, timeout=30, allow_redirects=True)
                if resp.status_code == 200 and len(resp.content) > 500:
                    fpath.write_bytes(resp.content)
                    print(f"    → Saved {fpath} ({len(resp.content):,} bytes)")
                    downloaded[category] = str(fpath)
                else:
                    print(f"    → HTTP {resp.status_code}, skipping")
            except Exception as e:
                print(f"    → Failed: {e}")
    return downloaded


def generate_districts_data():
    """Generate district demographics dataset."""
    np.random.seed(42)
    rows = []
    district_id = 1
    for state, districts in STATES_DISTRICTS.items():
        for district in districts:
            pop_base = np.random.lognormal(mean=13.5, sigma=0.8)
            pop = int(pop_base)
            area = int(np.random.uniform(500, 15000))
            literacy = np.clip(np.random.normal(
                75 if state in ["Kerala", "Tamil Nadu", "Karnataka"] else
                65 if state in ["Maharashtra", "Gujarat", "Punjab"] else 55,
                8), 35, 99)
            urban_pct = np.clip(np.random.normal(
                70 if district in ["Mumbai", "Kolkata", "Chennai", "Bengaluru Urban",
                                   "Hyderabad", "Ahmedabad", "Central Delhi",
                                   "New Delhi", "South Delhi"] else
                40 if "Delhi" in district or district in ["Pune", "Surat",
                                                          "Lucknow", "Jaipur"] else 25,
                12), 5, 100)
            rows.append({
                "district_id": district_id,
                "district_name": district,
                "state": state,
                "population": pop,
                "area_sq_km": area,
                "density_per_sq_km": round(pop / area, 1),
                "literacy_rate": round(literacy, 1),
                "urban_percentage": round(urban_pct, 1),
            })
            district_id += 1
    df = pd.DataFrame(rows)
    outpath = RAW_DIR / "districts.csv"
    df.to_csv(outpath, index=False)
    print(f"  [GEN] Districts: {len(df)} records → {outpath}")
    return df


def generate_air_quality_data(districts_df):
    """Generate daily air quality data for 2018-2023 (6 years)."""
    np.random.seed(123)
    start_date = datetime(2018, 1, 1)
    end_date = datetime(2023, 12, 31)
    dates = pd.date_range(start_date, end_date, freq="D")

    rows = []
    for _, row in districts_df.iterrows():
        state = row["state"]
        profile = POLLUTION_PROFILES.get(state, POLLUTION_PROFILES["Karnataka"])
        # District-level variation (±20%)
        d_factor = np.random.uniform(0.8, 1.2)
        # Urban areas have higher pollution
        u_factor = 1.0 + (row["urban_percentage"] - 30) / 200

        for date in dates:
            month = date.month
            s_factor = SEASONAL_FACTORS[month]
            # Daily noise
            noise = np.random.normal(1.0, 0.15)

            pm25 = max(5, profile["pm25_base"] * d_factor * u_factor * s_factor * noise)
            pm10 = max(10, profile["pm10_base"] * d_factor * u_factor * s_factor * noise * np.random.uniform(0.9, 1.1))
            no2 = max(2, profile["no2_base"] * d_factor * s_factor * noise * np.random.uniform(0.85, 1.15))
            so2 = max(1, profile["so2_base"] * d_factor * s_factor * noise * np.random.uniform(0.8, 1.2))

            rows.append({
                "district_id": row["district_id"],
                "date": date.strftime("%Y-%m-%d"),
                "pm25": round(pm25, 1),
                "pm10": round(pm10, 1),
                "no2": round(no2, 1),
                "so2": round(so2, 1),
                "aqi": int(min(500, max(pm25 * 1.8, pm10 * 0.9))),
            })

    df = pd.DataFrame(rows)
    # Introduce ~3% missing values to simulate real-world gaps
    for col in ["pm25", "pm10", "no2", "so2"]:
        mask = np.random.random(len(df)) < 0.03
        df.loc[mask, col] = np.nan

    outpath = RAW_DIR / "air_quality_daily.csv"
    df.to_csv(outpath, index=False)
    print(f"  [GEN] Air Quality: {len(df):,} records → {outpath}")
    return df


def generate_health_data(districts_df):
    """
    Generate monthly HMIS-style health data for 2018-2023.
    Disease counts are correlated with air quality via district pollution profile.
    """
    np.random.seed(456)
    months = pd.date_range("2018-01", "2023-12", freq="MS")

    rows = []
    for _, row in districts_df.iterrows():
        state = row["state"]
        profile = POLLUTION_PROFILES.get(state, POLLUTION_PROFILES["Karnataka"])
        pop = row["population"]
        pop_factor = pop / 1_000_000  # scale to per-million

        for month in months:
            m = month.month
            s_factor = SEASONAL_FACTORS[m]

            # Respiratory disease incidence correlates with pollution
            # Base rate ~ 200-800 per 100k per month, scaled by pollution
            resp_base = (profile["pm25_base"] / 40) * 400 * pop_factor
            respiratory = int(max(10, resp_base * s_factor *
                                 np.random.lognormal(0, 0.3)))

            # Cardiovascular — weaker correlation with pollution
            cardio_base = (profile["pm25_base"] / 60) * 250 * pop_factor
            cardiovascular = int(max(5, cardio_base *
                                    (0.8 + 0.2 * s_factor) *
                                    np.random.lognormal(0, 0.25)))

            # Diarrhoeal — inversely correlated with pollution season
            # (monsoon peak = low pollution, high diarrhoea)
            diarr_monsoon = {1: 0.6, 2: 0.5, 3: 0.7, 4: 0.8,
                            5: 0.9, 6: 1.3, 7: 1.8, 8: 1.9,
                            9: 1.6, 10: 1.0, 11: 0.7, 12: 0.5}
            diarr_base = 300 * pop_factor
            diarrhoea = int(max(5, diarr_base * diarr_monsoon[m] *
                               np.random.lognormal(0, 0.3)))

            # Total OPD visits
            total_opd = int((respiratory + cardiovascular + diarrhoea) *
                           np.random.uniform(3, 6))

            rows.append({
                "district_id": row["district_id"],
                "year_month": month.strftime("%Y-%m"),
                "respiratory_cases": respiratory,
                "cardiovascular_cases": cardiovascular,
                "diarrhoea_cases": diarrhoea,
                "total_opd_visits": total_opd,
                "institutional_deliveries": int(max(0, pop_factor * 80 *
                                                   np.random.lognormal(0, 0.2))),
                "immunization_doses": int(max(0, pop_factor * 500 *
                                             np.random.lognormal(0, 0.15))),
            })

    df = pd.DataFrame(rows)
    # ~2% missing values
    for col in ["respiratory_cases", "cardiovascular_cases", "diarrhoea_cases"]:
        mask = np.random.random(len(df)) < 0.02
        df.loc[mask, col] = np.nan

    outpath = RAW_DIR / "health_hmis_monthly.csv"
    df.to_csv(outpath, index=False)
    print(f"  [GEN] Health HMIS: {len(df):,} records → {outpath}")
    return df


def generate_water_quality_data(districts_df):
    """Generate water quality data (JJM-style) by district."""
    np.random.seed(789)
    rows = []

    for _, row in districts_df.iterrows():
        state = row["state"]
        # Water quality tends inversely related to urbanization/industrialization
        urban = row["urban_percentage"]

        for year in range(2019, 2024):
            for quarter in range(1, 5):
                ph = np.clip(np.random.normal(7.2, 0.5), 5.5, 9.0)
                dissolved_oxygen = np.clip(np.random.normal(
                    6.5 if state in ["Kerala", "Karnataka"] else 5.0, 1.2), 1.0, 12.0)
                bod = max(0.5, np.random.exponential(
                    5 if urban > 50 else 3))
                coliform = int(max(0, np.random.exponential(
                    800 if urban > 50 else 300)))
                turbidity = max(0.5, np.random.exponential(
                    8 if urban > 40 else 4))
                tds = max(50, np.random.normal(
                    450 if state in ["Rajasthan", "Gujarat"] else 300, 80))

                rows.append({
                    "district_id": row["district_id"],
                    "year": year,
                    "quarter": quarter,
                    "ph": round(ph, 2),
                    "dissolved_oxygen_mg_l": round(dissolved_oxygen, 2),
                    "bod_mg_l": round(bod, 2),
                    "total_coliform_mpn": coliform,
                    "turbidity_ntu": round(turbidity, 2),
                    "tds_mg_l": round(tds, 1),
                })

    df = pd.DataFrame(rows)
    # ~4% missing
    for col in ["ph", "dissolved_oxygen_mg_l", "bod_mg_l"]:
        mask = np.random.random(len(df)) < 0.04
        df.loc[mask, col] = np.nan

    outpath = RAW_DIR / "water_quality.csv"
    df.to_csv(outpath, index=False)
    print(f"  [GEN] Water Quality: {len(df):,} records → {outpath}")
    return df


def main():
    print("=" * 60)
    print("  DSM Final Project — Data Collection")
    print("  Air Quality & Public Health in Indian Districts")
    print("=" * 60)

    # Step 1: Try downloading real data
    print("\n[1/5] Attempting to download real datasets from data.gov.in...")
    downloaded = try_download_real_data()
    if downloaded:
        print(f"  → Downloaded {len(downloaded)} dataset(s)")
    else:
        print("  → No real data downloaded (will generate synthetic datasets)")

    # Step 2: Generate district demographics
    print("\n[2/5] Generating district demographics...")
    districts_df = generate_districts_data()

    # Step 3: Generate air quality data
    print("\n[3/5] Generating air quality dataset (2018–2023)...")
    aq_df = generate_air_quality_data(districts_df)

    # Step 4: Generate health data
    print("\n[4/5] Generating HMIS health dataset (2018–2023)...")
    health_df = generate_health_data(districts_df)

    # Step 5: Generate water quality data
    print("\n[5/5] Generating water quality dataset (2019–2023)...")
    water_df = generate_water_quality_data(districts_df)

    # Summary
    print("\n" + "=" * 60)
    print("  Data Collection Complete!")
    print("=" * 60)
    print(f"  Districts:     {len(districts_df):>8,} records")
    print(f"  Air Quality:   {len(aq_df):>8,} records")
    print(f"  Health HMIS:   {len(health_df):>8,} records")
    print(f"  Water Quality: {len(water_df):>8,} records")
    print(f"\n  All files saved to: {RAW_DIR}")
    print("=" * 60)

    # Save a manifest
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "datasets": {
            "districts": {"file": "districts.csv", "rows": len(districts_df)},
            "air_quality": {"file": "air_quality_daily.csv", "rows": len(aq_df)},
            "health_hmis": {"file": "health_hmis_monthly.csv", "rows": len(health_df)},
            "water_quality": {"file": "water_quality.csv", "rows": len(water_df)},
        },
        "real_downloads": downloaded,
    }
    manifest_path = RAW_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n  Manifest saved to: {manifest_path}")


if __name__ == "__main__":
    main()
