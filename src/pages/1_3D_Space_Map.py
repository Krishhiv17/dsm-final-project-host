import streamlit as st
import pandas as pd
import pydeck as pdk
from pathlib import Path
import json

# Setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

st.set_page_config(page_title="3D Pollution Data", page_icon="🌌", layout="wide")

# Custom dark theme styling
st.markdown("""
<style>
    .stApp {
        background-color: #0c0e15;
        color: #e2e8f0;
    }
    h1, h2, h3 { color: #38bdf8 !important; }
    .stSelectbox label, .stSlider label { color: #94a3b8 !important; }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    geo_file = PROCESSED_DIR / "districts_geocoded.csv"
    if not geo_file.exists():
        st.error("Please run the geocoding script first!")
        return pd.DataFrame()
        
    merged = pd.read_csv(PROCESSED_DIR / "air_health_merged.csv")
    districts = pd.read_csv(geo_file)
    
    # Merge coords back in
    df = merged.merge(districts[['district_id', 'latitude', 'longitude', 'district_name']], on='district_id')
    
    # For mapping, we'll aggregate to district level means
    map_data = df.groupby(['district_id', 'district_name', 'state', 'latitude', 'longitude']).agg({
        'pm25': 'mean',
        'pm10': 'mean',
        'respiratory_cases': 'mean',
        'diarrhoea_cases': 'mean'
    }).reset_index()
    
    # Normalize values for plotting (scale 0-1)
    map_data['pm25_norm'] = (map_data['pm25'] - map_data['pm25'].min()) / (map_data['pm25'].max() - map_data['pm25'].min())
    
    # Calculate colors based on PM2.5 (Blue -> Purple -> Red)
    def calculate_color(val_norm):
        if val_norm < 0.3:
            return [16, 185, 129, 200]  # Green/Cyan
        elif val_norm < 0.6:
            return [168, 85, 247, 200]  # Purple
        else:
            return [239, 68, 68, 200]   # Red
            
    map_data['color'] = map_data['pm25_norm'].apply(calculate_color)
    return map_data

st.title("🌌 Immersive 3D District Analytics")

df = load_data()

if not df.empty:
    col1, col2 = st.columns([1, 4])
    
    with col1:
        st.markdown("### Controls")
        st.markdown("Adjust the 3D map representation.")
        
        # What represents the height of the hex bin?
        elevation_metric = st.selectbox(
            "Elevation represents:",
            ["respiratory_cases", "pm25", "pm10", "diarrhoea_cases"]
        )
        
        # Elevation scale
        elevation_scale = st.slider("Tower Height Scale", min_value=1, max_value=5000, value=1500)
        radius_scale = st.slider("Hexagon Radius (meters)", min_value=5000, max_value=50000, value=25000)
        
        # Map Style Select
        map_theme = st.selectbox(
            "Map Theme:",
            ["dark", "light", "road", "satellite"],
            index=0
        )
        
        st.markdown("""
        **How to navigate:**
        - **Left Click + Drag**: Pan
        - **Right Click + Drag**: Tilt & Rotate (3D)
        - **Scroll**: Zoom
        
        *Colors represent PM2.5 concentrations (Green=Low, Red=High).*
        """)

    with col2:
        # Initial view state (centered broadly over India)
        view_state = pdk.ViewState(
            longitude=78.9629,
            latitude=20.5937,
            zoom=4,
            pitch=45,
            bearing=15
        )
        
        # Hexagon layer
        layer = pdk.Layer(
            "ColumnLayer",
            data=df,
            get_position=["longitude", "latitude"],
            get_elevation=elevation_metric,
            elevation_scale=elevation_scale,
            radius=radius_scale,
            get_fill_color="color",
            pickable=True,
            auto_highlight=True,
        )
        
        # Tooltip
        tooltip = {
            "html": "<b>{district_name}, {state}</b><br/>"
                    "Avg PM2.5: {pm25} µg/m³<br/>"
                    "Avg Respiratory Cases: {respiratory_cases}<br/>",
            "style": {"background": "#1e293b", "color": "white", "font-family": "Inter", "z-index": "10000"}
        }

        # Render map
        r = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip=tooltip,
            map_style=map_theme
        )
        
        st.pydeck_chart(r, use_container_width=True)
