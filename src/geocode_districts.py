"""
geocode_districts.py
====================
Adds latitude and longitude to our synthetic districts data
so we can plot them on a 3D map.
"""

import pandas as pd
import time
from geopy.geocoders import Nominatim
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DISTRICTS_FILE = PROCESSED_DIR / "districts_clean.csv"
OUT_FILE = PROCESSED_DIR / "districts_geocoded.csv"

def geocode_districts():
    print(f"Loading {DISTRICTS_FILE}...")
    df = pd.read_csv(DISTRICTS_FILE)
    
    # Initialize nominatim geocoder
    geolocator = Nominatim(user_agent="dsm_project_geocode")
    
    lats = []
    lons = []
    
    print("Geocoding districts (this might take a minute)...")
    for i, row in df.iterrows():
        # Add 'India' to help the geocoder
        query = f"{row['district_name']}, {row['state']}, India"
        try:
            # Add a small delay to respect Nominatim usage policy (1 request/sec)
            time.sleep(1)
            location = geolocator.geocode(query)
            
            if location:
                lats.append(location.latitude)
                lons.append(location.longitude)
                print(f"[{i+1}/{len(df)}] ✅ {query}")
            else:
                lats.append(None)
                lons.append(None)
                print(f"[{i+1}/{len(df)}] ❌ Could not find: {query}")
                
        except Exception as e:
            lats.append(None)
            lons.append(None)
            print(f"[{i+1}/{len(df)}] ⚠️ Error for {query}: {e}")
            
    df['latitude'] = lats
    df['longitude'] = lons
    
    # Fill any missing values with the state's center (rough fallback)
    missing = df['latitude'].isna().sum()
    if missing > 0:
        print(f"\nFilling {missing} missing coordinates with state averages...")
        state_avg = df.groupby('state')[['latitude', 'longitude']].transform('mean')
        df['latitude'].fillna(state_avg['latitude'], inplace=True)
        df['longitude'].fillna(state_avg['longitude'], inplace=True)
        
    # If there are stills NaNs (e.g. an entire state failed), fill with a default (center of India approx)
    df['latitude'].fillna(20.5937, inplace=True)
    df['longitude'].fillna(78.9629, inplace=True)
    
    df.to_csv(OUT_FILE, index=False)
    print(f"\nDone! Saved to {OUT_FILE}")

if __name__ == "__main__":
    geocode_districts()
