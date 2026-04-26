import pandas as pd
import numpy as np
from pathlib import Path
import os
import glob
import re

def clean_name(name):
    """Standardize district/city names for matching."""
    if pd.isna(name): return ""
    name = str(name).lower().strip()
    name = re.sub(r'[^a-z0-9\s]', '', name) # Remove special chars
    name = name.replace('district', '').replace('city', '').strip()
    # Handle common NDAP variations
    name = name.replace('visakhapatanam', 'visakhapatnam')
    name = name.replace('anantapuramu', 'anantapur')
    name = name.replace('spsr ', '').replace('potti sriramulu ', '')
    return name
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
NDAP_DIR = RAW_DIR / "v1"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

def find_ndap_files():
    """Detect which file is which in the v1 folder."""
    files = glob.glob(str(NDAP_DIR / "*.csv"))
    mapping = {"pollutants": [], "health": []}
    for f in files:
        try:
            df = pd.read_csv(f, nrows=1)
            cols = "".join(df.columns)
            if "ARI" in cols or "Pneumonia" in cols or "OPD" in cols:
                mapping["health"].append(f)
            elif "µg/m³" in cols or "Concentration" in cols:
                mapping["pollutants"].append(f)
            elif "Population" in cols and "Literate" in cols:
                mapping["census"] = f
            elif "pH" in cols and "Dissolved Oxygen" in cols:
                mapping["water"] = f
        except Exception:
            continue
    return mapping

def bridge_health(filepaths):
    print(f"  [BRIDGE] Merging {len(filepaths)} Real Health Files...")
    
    all_health = []
    for f in filepaths:
        df = pd.read_csv(f)
        rename_map = {}
        for col in df.columns:
            if "District" in col and "district" not in rename_map.values(): rename_map[col] = "district"
            if "State" in col and "state" not in rename_map.values(): rename_map[col] = "state"
            if "Year" in col and "year_month" not in rename_map.values(): rename_map[col] = "year_month"
            if ("Pneumonia" in col or "ARI" in col) and "respiratory_cases" not in rename_map.values():
                rename_map[col] = "respiratory_cases"
        
        df = df.rename(columns=rename_map)
        if isinstance(df["district"], pd.DataFrame): df["district"] = df["district"].iloc[:, 0]
        
        # Clean Year to YYYY-MM
        def parse_year_str(val):
            m = re.search(r"(\d{4})", str(val))
            return f"{m.group(1)}-01" if m else "2020-01"
        df["year_month"] = df["year_month"].apply(parse_year_str)
        
        all_health.append(df)
        
    df = pd.concat(all_health, ignore_index=True)
    
    # Map district to ID
    dist_df = pd.read_csv(RAW_DIR / "districts.csv")
    name_to_id = dict(zip(dist_df["district_name"].apply(clean_name), dist_df["district_id"]))
    df["district_id"] = df["district"].apply(clean_name).map(name_to_id)
    df = df.dropna(subset=["district_id"])
    
    # Ensure all expected columns exist
    for col in ["cardiovascular_cases", "diarrhoea_cases", "total_opd_visits"]:
        if col not in df.columns: df[col] = np.nan
    
    needed = ["state", "district", "district_id", "year_month", "respiratory_cases", 
              "cardiovascular_cases", "diarrhoea_cases", "total_opd_visits"]
    df = df[[c for c in needed if c in df.columns]]
    
    df.to_csv(RAW_DIR / "health_hmis_monthly.csv", index=False)
    print(f"    → Saved real combined health data: {len(df)} rows")

def bridge_air(pollutant_files):
    print(f"  [BRIDGE] Merging {len(pollutant_files)} Real Pollutant Files...")
    
    merged_df = None
    
    for f in pollutant_files:
        df = pd.read_csv(f)
        rename_map = {}
        target_col = None
        for col in df.columns:
            col_lower = col.lower()
            if "city" in col_lower: rename_map[col] = "district"
            if "year" in col_lower: rename_map[col] = "date"
            
            # Match PM2.5
            if ("pm2.5" in col_lower or "25 micro grams" in col_lower) and "annual" in col_lower:
                rename_map[col] = "pm25"
                target_col = "pm25"
            # Match NO2
            elif ("no2" in col_lower or "nitrogen dioxide" in col_lower) and "annual" in col_lower:
                rename_map[col] = "no2"
                target_col = "no2"
            # Match PM10
            elif ("pm10" in col_lower or "10 micro grams" in col_lower) and "annual" in col_lower:
                rename_map[col] = "pm10"
                target_col = "pm10"
            # Match SO2
            elif ("so2" in col_lower or "sulphur dioxide" in col_lower) and "annual" in col_lower:
                rename_map[col] = "so2"
                target_col = "so2"

        df = df.rename(columns=rename_map)
        
        # Clean Date
        def parse_year(val):
            import re
            m = re.search(r"\d{4}", str(val))
            return f"{m.group(0)}-01-01" if m else "2020-01-01"
        
        df["date"] = df["date"].apply(parse_year)
        cols_to_keep = ["district", "date", target_col] if target_col else ["district", "date"]
        df = df[[c for c in cols_to_keep if c in df.columns]].dropna()
        
        if "district" not in df.columns:
            continue

        if merged_df is None:
            merged_df = df
        else:
            merged_df = pd.merge(merged_df, df, on=["district", "date"], how="outer")

    if merged_df is not None:
        # Load the district map we just created
        dist_df = pd.read_csv(RAW_DIR / "districts.csv")
        name_to_id = dict(zip(dist_df["district_name"].apply(clean_name), dist_df["district_id"]))
        
        merged_df["district_id"] = merged_df["district"].apply(clean_name).map(name_to_id)
        
        # Drop rows where we couldn't map the district (unknown cities)
        merged_df = merged_df.dropna(subset=["district_id"])
        
        for col in ["pm10", "no2", "so2"]:
            if col not in merged_df.columns:
                merged_df[col] = np.nan
        if "pm25" in merged_df.columns:
            merged_df["aqi"] = merged_df["pm25"].fillna(0) * 1.5 # Proxy AQI
        else:
            merged_df["aqi"] = np.nan
        merged_df.to_csv(RAW_DIR / "air_quality_daily.csv", index=False)
        print(f"    → Saved real air quality data: {len(merged_df)} rows mapped to districts")

def bridge_census(filepath):
    print(f"  [BRIDGE] Processing Real Census Data: {os.path.basename(filepath)}")
    # Use a chunked or subset read if it's too large, but 279MB is manageable for pandas
    df = pd.read_csv(filepath)
    
    # NDAP Census often has 'District', 'State', 'Population', 'Literate Population'
    rename_map = {
        'Population (UOM:Number), Scaling Factor:1': 'population',
        'Literate Population (UOM:Number), Scaling Factor:1': 'literate_pop',
        'Working Population (UOM:Number), Scaling Factor:1': 'working_pop',
        'District': 'district_name',
        'State': 'state'
    }
    
    df = df.rename(columns=rename_map)
    
    # Convert columns to numeric, coerced errors to NaN then 0
    for col in ["population", "literate_pop", "working_pop"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    
    # Calculate Urban Percentage
    # Group by state, district, and residence type
    urban_df = df.groupby(["state", "district_name", "Residence Type"])["population"].sum().unstack(fill_value=0)
    if "Urban" in urban_df.columns:
        urban_df["urban_percentage"] = (urban_df["Urban"] / (urban_df.get("Rural", 0) + urban_df["Urban"]) * 100).round(1)
    else:
        urban_df["urban_percentage"] = 0.0
        
    # Basic cleaning
    agg_df = df.groupby(["state", "district_name"]).agg({
        "population": "sum",
        "literate_pop": "sum",
        "working_pop": "sum"
    }).reset_index()
    
    agg_df = pd.merge(agg_df, urban_df[["urban_percentage"]], on=["state", "district_name"], how="left")
    
    agg_df["literacy_rate"] = (agg_df["literate_pop"] / agg_df["population"] * 100).round(1)
    agg_df["district_id"] = range(1, len(agg_df) + 1)
    
    # Save as the raw districts file
    agg_df.to_csv(RAW_DIR / "districts.csv", index=False)
    print(f"    → Saved real census/district data: {len(agg_df)} districts")

def main():
    print("="*60)
    print(" NDAP BRIDGE: Migrating from Synthetic to Real Data")
    print("="*60)
    
    mapping = find_ndap_files()
    
    if "census" in mapping:
        bridge_census(mapping["census"])
    
    if mapping.get("health"):
        bridge_health(mapping["health"])
    
    if mapping.get("pollutants"):
        bridge_air(mapping["pollutants"])
        
    print("\n[SUCCESS] Pipeline is now connected to Real NDAP Data.")
    print("="*60)


if __name__ == "__main__":
    main()
