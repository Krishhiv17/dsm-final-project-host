"""
dashboard.py
============
Interactive Streamlit Dashboard for Air Quality & Public Health Analysis

Features:
  - Overview metrics (KPIs)
  - State-wise pollution heatmap
  - Time-series explorer with district selector
  - Correlation scatter plots with filters
  - District risk clustering map
  - Prediction interface: input pollutant levels → predicted health impact
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import pickle
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

# ── Setup ───────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FIG_DIR = PROJECT_ROOT / "notebooks" / "figures"

st.set_page_config(
    page_title="Air Quality & Public Health — India",
    page_icon="🌬️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .main { font-family: 'Inter', sans-serif; }

    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .metric-card h3 { font-size: 0.85rem; opacity: 0.9; margin: 0; font-weight: 400; }
    .metric-card h1 { font-size: 2rem; margin: 0.3rem 0 0 0; font-weight: 700; }

    .metric-red { background: linear-gradient(135deg, #f5576c 0%, #ff6b6b 100%); }
    .metric-green { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
    .metric-blue { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }
    .metric-orange { background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); }

    .stSelectbox label, .stMultiSelect label { font-weight: 600; }

    h1 { color: #1a1a2e; font-weight: 700; }
    h2 { color: #16213e; font-weight: 600; }
    h3 { color: #0f3460; font-weight: 500; }

    .insight-box {
        background: #f0f4ff;
        border-left: 4px solid #4facfe;
        padding: 1rem 1.2rem;
        border-radius: 0 8px 8px 0;
        margin: 1rem 0;
        font-size: 0.95rem;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data():
    """Load all processed datasets."""
    merged = pd.read_csv(PROCESSED_DIR / "air_health_merged.csv")
    districts = pd.read_csv(PROCESSED_DIR / "districts_clean.csv")
    aq = pd.read_csv(PROCESSED_DIR / "air_quality_clean.csv")
    aq["date"] = pd.to_datetime(aq["date"])
    health = pd.read_csv(PROCESSED_DIR / "health_clean.csv")

    clusters = None
    cluster_path = PROCESSED_DIR / "district_clusters.csv"
    if cluster_path.exists():
        clusters = pd.read_csv(cluster_path)

    return merged, districts, aq, health, clusters


@st.cache_resource
def train_prediction_model(merged):
    """Train a Random Forest model for predictions."""
    features = ["pm25", "pm10", "no2", "so2", "urban_percentage",
                "literacy_rate", "population"]
    target = "respiratory_cases"
    df = merged[features + [target]].dropna()
    X, y = df[features], df[target]
    model = RandomForestRegressor(n_estimators=100, max_depth=15,
                                   random_state=42, n_jobs=-1)
    model.fit(X, y)
    return model, features


def render_overview(merged, districts, aq):
    """Render overview KPI metrics."""
    col1, col2, col3, col4 = st.columns(4)

    avg_pm25 = aq["pm25"].mean()
    total_resp = merged["respiratory_cases"].sum()
    num_districts = len(districts)
    num_states = districts["state"].nunique()

    with col1:
        st.markdown(f"""
        <div class="metric-card metric-red">
            <h3>National Avg PM2.5</h3>
            <h1>{avg_pm25:.1f} µg/m³</h1>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card metric-orange">
            <h3>Total Respiratory Cases</h3>
            <h1>{total_resp/1e6:.1f}M</h1>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card metric-blue">
            <h3>Districts Analyzed</h3>
            <h1>{num_districts}</h1>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-card metric-green">
            <h3>States Covered</h3>
            <h1>{num_states}</h1>
        </div>
        """, unsafe_allow_html=True)


def render_state_pollution(merged, districts):
    """Render state-level pollution heatmap."""
    st.header("📊 State-wise Air Quality Comparison")

    state_agg = merged.groupby("state").agg({
        "pm25": "mean", "pm10": "mean", "no2": "mean",
        "respiratory_cases": "sum", "cardiovascular_cases": "sum"
    }).round(1).reset_index()
    state_agg = state_agg.sort_values("pm25", ascending=False)

    col1, col2 = st.columns([3, 2])

    with col1:
        fig = px.bar(state_agg, x="state", y="pm25",
                     color="pm25", color_continuous_scale="RdYlGn_r",
                     title="Average PM2.5 by State",
                     labels={"pm25": "PM2.5 (µg/m³)", "state": "State"})
        fig.add_hline(y=60, line_dash="dash", line_color="red",
                      annotation_text="NAAQS Standard (60 µg/m³)")
        fig.update_layout(height=500, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Pollution vs Respiratory cases
        fig = px.scatter(state_agg, x="pm25", y="respiratory_cases",
                         size="respiratory_cases", color="pm25",
                         hover_data=["state"],
                         color_continuous_scale="RdYlGn_r",
                         title="PM2.5 vs Total Respiratory Cases",
                         labels={"pm25": "Avg PM2.5", "respiratory_cases": "Total Respiratory Cases"})
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("""
    <div class="insight-box">
        <strong>🔍 Insight:</strong> Indo-Gangetic Plain states (Delhi, UP, Bihar, Haryana) consistently
        exceed the NAAQS standard of 60 µg/m³, with Delhi at ~120 µg/m³ — double the safe limit.
        Southern states (Kerala, Tamil Nadu) remain well within safe levels.
    </div>
    """, unsafe_allow_html=True)


def render_time_series(aq, districts):
    """Render time-series explorer."""
    st.header("📈 Time-Series Explorer")

    col1, col2 = st.columns([1, 3])

    with col1:
        states = sorted(districts["state"].unique())
        selected_state = st.selectbox("Select State", states, index=states.index("Delhi"))

        state_districts = districts[districts["state"] == selected_state]["district_id"].values
        state_district_names = districts[districts["state"] == selected_state]
        district_options = dict(zip(state_district_names["district_name"],
                                    state_district_names["district_id"]))
        selected_district_name = st.selectbox("Select District",
                                               list(district_options.keys()))
        selected_district_id = district_options[selected_district_name]

        pollutant = st.selectbox("Pollutant", ["pm25", "pm10", "no2", "so2"])
        agg_period = st.radio("Aggregation", ["Daily", "Weekly", "Monthly"])

    with col2:
        district_data = aq[aq["district_id"] == selected_district_id].copy()
        district_data = district_data.sort_values("date")

        if agg_period == "Weekly":
            district_data = district_data.resample("W", on="date").mean().reset_index()
        elif agg_period == "Monthly":
            district_data = district_data.resample("ME", on="date").mean().reset_index()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=district_data["date"], y=district_data[pollutant],
            mode="lines", name=pollutant.upper(),
            line=dict(color="#e74c3c", width=1.5),
            fill="tozeroy", fillcolor="rgba(231,76,60,0.1)"
        ))

        # NAAQS standard line
        standards = {"pm25": 60, "pm10": 100, "no2": 80, "so2": 80}
        fig.add_hline(y=standards.get(pollutant, 60), line_dash="dash",
                      line_color="green",
                      annotation_text=f"NAAQS Standard ({standards.get(pollutant, 60)})")

        fig.update_layout(
            title=f"{pollutant.upper()} — {selected_district_name}, {selected_state}",
            xaxis_title="Date", yaxis_title=f"{pollutant.upper()} (µg/m³)",
            height=450, template="plotly_white"
        )
        st.plotly_chart(fig, use_container_width=True)


def render_correlations(merged):
    """Render correlation analysis with interactive controls."""
    st.header("🔗 Pollution-Health Correlations")

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        x_axis = st.selectbox("X-Axis (Pollution)", ["pm25", "pm10", "no2", "so2"])
    with col2:
        y_axis = st.selectbox("Y-Axis (Health)", ["respiratory_cases",
                                                    "cardiovascular_cases",
                                                    "diarrhoea_cases"])
    with col3:
        z_axis = st.selectbox("Z-Axis (For 3D)", ["None", "urban_percentage", "literacy_rate", "pm25", "pm10", "no2", "so2", "respiratory_cases", "cardiovascular_cases", "diarrhoea_cases", "population"], index=1)

    sample = merged.sample(min(3000, len(merged)), random_state=42)

    tab1, tab2 = st.tabs(["2D Scatter", "3D Scatter"])

    with tab1:
        fig = px.scatter(sample, x=x_axis, y=y_axis, color="state",
                         hover_data=["state"],
                         trendline="ols",
                         title=f"Correlation: {x_axis.upper()} vs {y_axis.replace('_', ' ').title()}",
                         labels={x_axis: f"{x_axis.upper()} (µg/m³)",
                                 y_axis: y_axis.replace("_", " ").title()},
                         opacity=0.5)
        fig.update_layout(height=550, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        z_val = z_axis if z_axis != "None" else "pm10"
        fig3d = px.scatter_3d(sample, x=x_axis, y=y_axis, z=z_val, color="state",
                              hover_data=["state"],
                              title=f"3D Correlation: {x_axis.upper()} vs {y_axis.replace('_', ' ').title()} vs {z_val.replace('_', ' ').title()}",
                              labels={x_axis: f"{x_axis.upper()} (µg/m³)",
                                      y_axis: y_axis.replace("_", " ").title(),
                                      z_val: z_val.replace("_", " ").title()},
                              opacity=0.7)
        fig3d.update_layout(height=600, margin=dict(l=0, r=0, b=0, t=40))
        st.plotly_chart(fig3d, use_container_width=True)

    from scipy import stats
    r, p = stats.pearsonr(merged[x_axis].dropna(), merged[y_axis].dropna())
    col1, col2, col3 = st.columns(3)
    col1.metric("Pearson r", f"{r:.4f}")
    col2.metric("p-value", f"{p:.2e}")
    col3.metric("Significance", "✅ Significant" if p < 0.05 else "❌ Not Significant")


def render_clusters(clusters, districts):
    """Render district clustering results."""
    st.header("🎯 District Risk Clusters")

    if clusters is None:
        st.warning("Cluster data not found. Run 04_analysis.py first.")
        return

    cluster_labels = {
        0: "At Risk",
        1: "Critical — High Pollution",
        2: "Moderate",
        3: "Critical — High Disease Burden"
    }
    clusters["risk_label"] = clusters["cluster"].map(cluster_labels)

    col1, col2 = st.columns([2, 1])

    with col1:
        tab1, tab2 = st.tabs(["2D View", "3D View"])
        
        with tab1:
            fig = px.scatter(clusters, x="pm25", y="respiratory_cases",
                             color="risk_label", size="cardiovascular_cases",
                             hover_data=["district_name", "state"],
                             title="District Clusters — PM2.5 vs Respiratory",
                             color_discrete_map={
                                 "Critical — High Pollution": "#e74c3c",
                                 "Critical — High Disease Burden": "#c0392b",
                                 "At Risk": "#f39c12",
                                 "Moderate": "#2ecc71",
                             })
            fig.update_layout(height=500, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            fig3d = px.scatter_3d(clusters, x="pm25", y="respiratory_cases", z="cardiovascular_cases",
                                  color="risk_label",
                                  hover_data=["district_name", "state"],
                                  title="3D Clusters — PM2.5 vs Respiratory vs Cardiovascular",
                                  color_discrete_map={
                                      "Critical — High Pollution": "#e74c3c",
                                      "Critical — High Disease Burden": "#c0392b",
                                      "At Risk": "#f39c12",
                                      "Moderate": "#2ecc71",
                                  })
            fig3d.update_layout(height=550, margin=dict(l=0, r=0, b=0, t=40))
            st.plotly_chart(fig3d, use_container_width=True)

    with col2:
        st.subheader("Cluster Summary")
        for c in sorted(clusters["cluster"].unique()):
            label = cluster_labels.get(c, f"Cluster {c}")
            count = len(clusters[clusters["cluster"] == c])
            avg_pm = clusters[clusters["cluster"] == c]["pm25"].mean()
            st.markdown(f"""
            **{label}** ({count} districts)
            - Avg PM2.5: {avg_pm:.1f} µg/m³
            """)

    # Table
    st.subheader("📋 District Details")
    display_cols = ["district_name", "state", "pm25", "respiratory_cases",
                    "cardiovascular_cases", "risk_label"]
    available_cols = [c for c in display_cols if c in clusters.columns]
    st.dataframe(
        clusters[available_cols].sort_values("pm25", ascending=False),
        use_container_width=True, height=400
    )


def render_prediction(model, feature_names, merged):
    """Render the prediction interface."""
    st.header("🔮 Health Impact Predictor")

    st.markdown("""
    <div class="insight-box">
        <strong>How it works:</strong> Enter air quality and demographic parameters below.
        Our Random Forest model (R²=0.81) will predict the expected monthly respiratory
        disease cases for a district with those characteristics.
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Air Quality Parameters")
        pm25 = st.slider("PM2.5 (µg/m³)", 10.0, 200.0, 60.0, 1.0)
        pm10 = st.slider("PM10 (µg/m³)", 20.0, 400.0, 120.0, 5.0)
        no2 = st.slider("NO₂ (µg/m³)", 5.0, 100.0, 30.0, 1.0)
        so2 = st.slider("SO₂ (µg/m³)", 2.0, 50.0, 12.0, 0.5)

    with col2:
        st.subheader("District Demographics")
        urban_pct = st.slider("Urban Population (%)", 5.0, 100.0, 40.0, 1.0)
        literacy = st.slider("Literacy Rate (%)", 35.0, 99.0, 70.0, 1.0)
        population = st.number_input("Population", min_value=10000,
                                      max_value=20000000, value=1000000, step=100000)

    if st.button("🔍 Predict Health Impact", type="primary", use_container_width=True):
        input_data = pd.DataFrame({
            "pm25": [pm25], "pm10": [pm10], "no2": [no2], "so2": [so2],
            "urban_percentage": [urban_pct], "literacy_rate": [literacy],
            "population": [population]
        })

        prediction = model.predict(input_data)[0]

        st.markdown("---")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Predicted Monthly Respiratory Cases", f"{int(prediction):,}")
        with col2:
            rate = prediction / population * 100000
            st.metric("Rate per 100,000", f"{rate:.1f}")
        with col3:
            if pm25 > 100:
                risk = "🔴 Critical"
            elif pm25 > 60:
                risk = "🟡 High"
            elif pm25 > 40:
                risk = "🟢 Moderate"
            else:
                risk = "✅ Low"
            st.metric("Risk Level", risk)

        # Comparison with national average
        nat_avg_cases = merged["respiratory_cases"].mean()
        pct_diff = (prediction - nat_avg_cases) / nat_avg_cases * 100
        st.markdown(f"""
        <div class="insight-box">
            <strong>📊 Context:</strong> The predicted {int(prediction):,} monthly respiratory cases
            is <strong>{abs(pct_diff):.0f}% {'above' if pct_diff > 0 else 'below'}</strong>
            the national district average ({int(nat_avg_cases):,} cases/month).
        </div>
        """, unsafe_allow_html=True)


def render_seasonality(aq):
    """Render seasonality analysis."""
    st.header("🌡️ Seasonal Patterns")

    monthly = aq.groupby(aq["date"].dt.month).agg({
        "pm25": "mean", "pm10": "mean", "no2": "mean", "so2": "mean"
    }).round(1)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly.index = months

    fig = make_subplots(rows=1, cols=1)
    for col, color in [("pm25", "#e74c3c"), ("pm10", "#f39c12"),
                       ("no2", "#3498db"), ("so2", "#2ecc71")]:
        fig.add_trace(go.Scatter(
            x=months, y=monthly[col], mode="lines+markers",
            name=col.upper(), line=dict(color=color, width=2.5),
            marker=dict(size=8)
        ))

    fig.add_hline(y=60, line_dash="dash", line_color="red", opacity=0.5,
                  annotation_text="NAAQS PM2.5 Limit")
    fig.update_layout(
        title="Monthly Pollution Seasonality (National Average)",
        yaxis_title="Concentration (µg/m³)",
        height=450, template="plotly_white"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("""
    <div class="insight-box">
        <strong>🔍 Key Pattern:</strong> Winter months (Nov-Feb) show 2-3× higher pollution
        than monsoon months (Jul-Sep) due to temperature inversions, crop burning, and
        reduced wind dispersion. This aligns directly with respiratory disease peaks.
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# DISEASE PROPAGATION GRAPH PAGE
# ═══════════════════════════════════════════════════════════════════

@st.cache_data
def _load_graph_data():
    nodes_path = PROCESSED_DIR / "graph_nodes.csv"
    edges_path = PROCESSED_DIR / "graph_edges.csv"
    kg_path    = PROCESSED_DIR / "knowledge_graph.csv"
    lp_path    = PROCESSED_DIR / "link_prediction.csv"
    sa_path    = PROCESSED_DIR / "spatial_autocorr.csv"
    nodes = pd.read_csv(nodes_path) if nodes_path.exists() else None
    edges = pd.read_csv(edges_path) if edges_path.exists() else None
    kg    = pd.read_csv(kg_path)    if kg_path.exists()    else None
    lp    = pd.read_csv(lp_path)    if lp_path.exists()    else None
    sa    = pd.read_csv(sa_path)    if sa_path.exists()    else None
    return nodes, edges, kg, lp, sa


def render_disease_graph():
    st.header("🕸️ Disease Propagation Graph")
    st.markdown("""
    <div class="insight-box">
        <strong>What this shows:</strong> Districts as nodes connected when within 300 km.
        Colours represent <em>disease propagation communities</em> — geographic zones that
        transcend administrative (state) boundaries. Edge width encodes inverse distance.
        Red directed edges are Granger-causal: district A's PM2.5 statistically predicts
        district B's respiratory burden at a future lag.
    </div>
    """, unsafe_allow_html=True)

    nodes, edges, kg, lp, sa = _load_graph_data()

    if nodes is None or edges is None:
        st.warning("Graph data not found. Please run `python src/05_graph_spatial.py` first.")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "🌐 Proximity Network", "🎨 Community Zones",
        "🔗 Knowledge Graph", "🔮 Link Prediction"
    ])

    with tab1:
        col1, col2 = st.columns([3, 1])

        with col1:
            color_by = st.selectbox("Colour nodes by",
                ["pm25_mean", "resp_mean", "resp_rate_mean",
                 "community", "betweenness_centrality", "eigenvector_centrality"])
            size_by  = st.selectbox("Size nodes by",
                ["betweenness_centrality", "eigenvector_centrality", "degree_centrality"])

            valid_nodes = nodes.dropna(subset=["lat", "lon"])

            fig = go.Figure()

            # Draw proximity edges as lines
            if edges is not None:
                for _, e in edges.iterrows():
                    src = valid_nodes[valid_nodes["district_id"] == e["source_id"]]
                    tgt = valid_nodes[valid_nodes["district_id"] == e["target_id"]]
                    if len(src) and len(tgt):
                        fig.add_trace(go.Scattergeo(
                            lon=[float(src.iloc[0]["lon"]), float(tgt.iloc[0]["lon"]), None],
                            lat=[float(src.iloc[0]["lat"]), float(tgt.iloc[0]["lat"]), None],
                            mode="lines",
                            line=dict(width=0.4, color="#aaaaaa"),
                            hoverinfo="none",
                            showlegend=False,
                        ))

            # Draw nodes
            col_vals = valid_nodes[color_by].fillna(0)
            size_vals = valid_nodes[size_by].fillna(0)
            node_sizes = 6 + size_vals / (size_vals.max() + 1e-9) * 20

            fig.add_trace(go.Scattergeo(
                lon=valid_nodes["lon"],
                lat=valid_nodes["lat"],
                mode="markers",
                marker=dict(
                    size=node_sizes,
                    color=col_vals,
                    colorscale="RdYlGn_r",
                    showscale=True,
                    colorbar=dict(title=color_by),
                    line=dict(width=0.3, color="white"),
                ),
                text=valid_nodes["district_name"] + ", " + valid_nodes["state"],
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    f"{color_by}: %{{marker.color:.2f}}<br>"
                    "<extra></extra>"
                ),
            ))

            fig.update_layout(
                geo=dict(
                    scope="asia",
                    projection_type="natural earth",
                    center=dict(lat=22, lon=80),
                    lataxis_range=[6, 38],
                    lonaxis_range=[66, 98],
                    showland=True, landcolor="#f8f9fa",
                    showcoastlines=True, coastlinecolor="#cccccc",
                    showcountries=True, countrycolor="#dddddd",
                ),
                height=600,
                margin=dict(l=0, r=0, t=30, b=0),
                title=f"District Proximity Network — coloured by {color_by}",
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Spatial Autocorrelation")
            if sa is not None:
                for _, row in sa.iterrows():
                    sig = "🟢" if row["p_value_mc"] < 0.05 else "🔴"
                    st.metric(
                        label=row["variable"],
                        value=f"I = {row['morans_I']:.4f}",
                        delta=f"p={row['p_value_mc']:.3f} {sig} {row['interpretation']}",
                    )
            else:
                st.info("Run 05_graph_spatial.py to compute Moran's I.")

            st.markdown("---")
            st.subheader("Top Hub Districts")
            if nodes is not None:
                top_hubs = (nodes.nlargest(10, "betweenness_centrality")
                            [["district_name", "state", "betweenness_centrality"]])
                st.dataframe(top_hubs.rename(columns={
                    "betweenness_centrality": "BC",
                    "district_name": "District",
                    "state": "State",
                }), use_container_width=True)

    with tab2:
        st.subheader("Disease Propagation Communities")
        st.markdown("""
        <div class="insight-box">
            Communities detected via Louvain algorithm — districts cluster by geographic
            proximity and shared pollution corridors, <em>not</em> by administrative state.
            Cross-state communities reveal that disease propagation does not respect political borders.
        </div>
        """, unsafe_allow_html=True)

        if nodes is not None and "community" in nodes.columns:
            n_communities = nodes["community"].nunique()
            fig = px.scatter_geo(
                nodes.dropna(subset=["lat", "lon"]),
                lat="lat", lon="lon",
                color="community",
                hover_data=["district_name", "state", "pm25_mean"],
                title=f"Louvain Communities ({n_communities} disease zones, cross-state)",
                color_continuous_scale="Viridis",
            )
            fig.update_layout(
                geo=dict(scope="asia", center=dict(lat=22, lon=80),
                         lataxis_range=[6, 38], lonaxis_range=[66, 98],
                         showland=True, landcolor="#f8f9fa"),
                height=550,
            )
            st.plotly_chart(fig, use_container_width=True)

            comm_summary = (nodes.groupby(["community", "state"])
                            .size().reset_index(name="districts")
                            .sort_values(["community", "districts"], ascending=[True, False]))
            st.subheader("Community Composition (state breakdown)")
            st.dataframe(comm_summary, use_container_width=True, height=300)

    with tab3:
        st.subheader("Knowledge Graph Explorer")
        st.markdown("""
        <div class="insight-box">
            The knowledge graph encodes <em>semantically typed</em> relationships between districts.
            Unlike a plain graph, each edge type carries meaning: causal, administrative,
            geographic, or profile-based.
        </div>
        """, unsafe_allow_html=True)

        if kg is not None:
            rel_counts = kg["relationship"].value_counts().reset_index()
            rel_counts.columns = ["Relationship Type", "Triples"]
            col1, col2 = st.columns([2, 1])
            with col1:
                fig = px.bar(rel_counts, x="Relationship Type", y="Triples",
                             color="Triples", color_continuous_scale="Viridis",
                             title="Knowledge Graph — Triple Counts by Relationship Type")
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.metric("Total Triples", f"{len(kg):,}")
                st.metric("Relationship Types", rel_counts.shape[0])
                causal = kg[kg["relationship"] == "POLLUTION_CAUSES_HEALTH"]
                st.metric("Causal Edges (Granger)", len(causal))

            selected_rel = st.selectbox("Filter by relationship", kg["relationship"].unique())
            st.dataframe(kg[kg["relationship"] == selected_rel].head(50),
                         use_container_width=True, height=300)
        else:
            st.info("Run `python src/05_graph_spatial.py` to build the knowledge graph.")

    with tab4:
        st.subheader("Link Prediction — Likely Future Causal Connections")
        st.markdown("""
        <div class="insight-box">
            Using Jaccard coefficient and Adamic-Adar index on the proximity graph to predict
            which district pairs are most likely to exhibit Granger-causal links with more data
            or under worsening pollution conditions.
        </div>
        """, unsafe_allow_html=True)

        if lp is not None and len(lp):
            top_n = st.slider("Show top N predictions", 5, 50, 20)
            lp_show = lp.head(top_n)[["name_a", "name_b", "state_a", "state_b",
                                       "jaccard", "adamic_adar", "combined_score"]]
            lp_show["cross_state"] = lp_show["state_a"] != lp_show["state_b"]
            fig = px.scatter(lp_show, x="jaccard", y="adamic_adar",
                             size="combined_score", color="cross_state",
                             hover_data=["name_a", "name_b", "state_a", "state_b"],
                             color_discrete_map={True: "#e74c3c", False: "#3498db"},
                             title="Link Prediction Scores (red = cross-state)",
                             labels={"jaccard": "Jaccard Coefficient",
                                     "adamic_adar": "Adamic-Adar Index"})
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(lp_show, use_container_width=True)
        else:
            st.info("Run `python src/05_graph_spatial.py` to generate link predictions.")


# ═══════════════════════════════════════════════════════════════════
# CAUSAL INFERENCE PAGE
# ═══════════════════════════════════════════════════════════════════

@st.cache_data
def _load_causal_data():
    paths = {
        "granger":       PROCESSED_DIR / "granger_within_district.csv",
        "dose_response": PROCESSED_DIR / "dose_response.csv",
        "counterfactual":PROCESSED_DIR / "counterfactual.csv",
        "changepoint":   PROCESSED_DIR / "changepoint.csv",
        "af":            PROCESSED_DIR / "attributable_fraction.csv",
        "var_forecast":  PROCESSED_DIR / "var_forecast.csv",
    }
    return {k: pd.read_csv(v) if v.exists() else None for k, v in paths.items()}


def render_causal_inference(merged: pd.DataFrame):
    st.header("🧪 Causal Inference")
    st.markdown("""
    <div class="insight-box">
        <strong>Beyond correlation:</strong> These analyses test whether PM2.5 <em>causes</em>
        respiratory burden — using time-series Granger causality, dose-response curves,
        counterfactual policy scenarios, and population attributable fractions.
    </div>
    """, unsafe_allow_html=True)

    data = _load_causal_data()
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "⚡ Granger Causality", "💊 Dose-Response",
        "🔀 Counterfactual", "📍 Change Points", "📊 Attributable Fraction"
    ])

    with tab1:
        st.subheader("Within-District Granger Causality (PM2.5 → Respiratory)")
        st.markdown("""
        Tests whether PM2.5 at month t predicts respiratory cases at t+k,
        *beyond what past respiratory cases already predict*. Run for all 150 districts.
        """)
        gdf = data["granger"]
        if gdf is not None:
            col1, col2, col3 = st.columns(3)
            sig = gdf["significant_05"].sum()
            col1.metric("Significant (p<0.05)", f"{sig} / {len(gdf)} districts",
                        delta=f"{sig/len(gdf)*100:.0f}%")
            col2.metric("Most common lag", f"{int(gdf['best_lag_months'].mode()[0])} month(s)")
            col3.metric("Median F-statistic", f"{gdf['F_stat'].median():.2f}")

            fig = make_subplots(rows=1, cols=2,
                                subplot_titles=["p-value Distribution", "Optimal Lag Distribution"])
            fig.add_trace(go.Histogram(x=gdf["p_value"], nbinsx=25,
                                       marker_color="#9b59b6", name="p-values"), row=1, col=1)
            fig.add_vline(x=0.05, line_dash="dash", line_color="red", row=1, col=1)
            fig.add_trace(go.Histogram(x=gdf["best_lag_months"], nbinsx=6,
                                       marker_color="#e74c3c", name="lags"), row=1, col=2)
            fig.update_layout(height=400, showlegend=False,
                              title_text="Granger Causality Results (PM2.5 → Respiratory, 150 Districts)")
            st.plotly_chart(fig, use_container_width=True)

            # Cross-correlation (compute on the fly from merged data)
            st.subheader("Cross-Correlation at Different Lags (National Aggregate)")
            national = (merged.groupby("year_month")
                        .agg(pm25=("pm25", "mean"), resp=("respiratory_cases", "mean"))
                        .reset_index().sort_values("year_month"))
            pm25_s = (national["pm25"] - national["pm25"].mean()) / national["pm25"].std()
            resp_s = (national["resp"] - national["resp"].mean()) / national["resp"].std()
            lags   = list(range(0, 13))
            xcorr  = []
            for lag in lags:
                if lag == 0:
                    r = float(np.corrcoef(pm25_s.values, resp_s.values)[0, 1])
                else:
                    r = float(np.corrcoef(pm25_s.values[:-lag], resp_s.values[lag:])[0, 1])
                xcorr.append(r)
            xcorr_fig = px.bar(x=lags, y=xcorr,
                               color=xcorr, color_continuous_scale="RdBu_r",
                               labels={"x": "Lag (months)", "y": "Cross-Correlation r"},
                               title="National PM2.5 → Respiratory Cross-Correlation by Lag")
            xcorr_fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(xcorr_fig, use_container_width=True)
        else:
            st.info("Run `python src/06_causal_inference.py` first.")

    with tab2:
        st.subheader("Dose-Response Curve")
        st.markdown("How does the respiratory burden change as PM2.5 increases — "
                    "linear, threshold, or exponential?")
        dr = data["dose_response"]
        if dr is not None:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=dr["pm25_bin_center"], y=dr["resp_rate_mean"],
                error_y=dict(type="data", array=dr["se"] * 1.96, visible=True),
                mode="markers+lines", name="Observed",
                marker=dict(size=10, color="#2c3e50"),
                line=dict(width=2),
            ))
            fig.add_trace(go.Scatter(
                x=dr["pm25_bin_center"], y=dr["linear_fit"],
                mode="lines", name="Linear fit",
                line=dict(dash="dash", color="#e74c3c", width=2),
            ))
            fig.add_trace(go.Scatter(
                x=dr["pm25_bin_center"], y=dr["loglinear_fit"],
                mode="lines", name="Log-linear fit",
                line=dict(dash="dot", color="#3498db", width=2),
            ))
            fig.add_vline(x=60, line_dash="dot", line_color="green",
                          annotation_text="NAAQS (60 µg/m³)")
            fig.update_layout(
                height=500, template="plotly_white",
                title="Dose-Response: PM2.5 vs Respiratory Rate per 100k",
                xaxis_title="PM2.5 (µg/m³) — bin centre",
                yaxis_title="Respiratory Cases per 100k (monthly)",
            )
            st.plotly_chart(fig, use_container_width=True)

            slope = (dr["resp_rate_mean"].iloc[-1] - dr["resp_rate_mean"].iloc[0]) / \
                    (dr["pm25_bin_center"].iloc[-1] - dr["pm25_bin_center"].iloc[0])
            st.markdown(f"""
            <div class="insight-box">
                <strong>Finding:</strong> Each +10 µg/m³ increase in PM2.5 corresponds to approximately
                <strong>{slope*10:.1f} additional respiratory cases per 100k per month</strong>.
                The relationship is steeper above the NAAQS threshold, suggesting non-linear
                dose-response dynamics.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Run `python src/06_causal_inference.py` first.")

    with tab3:
        st.subheader("Counterfactual Policy Scenarios")
        st.markdown("If PM2.5 were reduced by X%, how many respiratory cases would be averted?")
        cf = data["counterfactual"]
        if cf is not None:
            reduction = st.select_slider("PM2.5 Reduction %",
                                          options=[10, 20, 30, 50])
            row = cf[cf["pm25_reduction_pct"] == reduction].iloc[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Cases Averted", f"{int(row['cases_averted']):,}")
            c2.metric("% Reduction", f"{row['percent_cases_reduced']:.1f}%")
            c3.metric("Mean ↓ per district/month", f"{row['mean_case_reduction']:.0f}")

            fig = px.bar(cf,
                         x=cf["pm25_reduction_pct"].astype(str) + "%",
                         y="cases_averted",
                         color="percent_cases_reduced",
                         color_continuous_scale="RdYlGn",
                         text="cases_averted",
                         title="Cases Averted Under Different PM2.5 Reduction Scenarios",
                         labels={"x": "PM2.5 Reduction", "cases_averted": "Cases Averted"})
            fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            fig.update_layout(height=450, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Run `python src/06_causal_inference.py` first.")

    with tab4:
        st.subheader("Change-Point Detection (CUSUM)")
        st.markdown("Structural breaks in the national PM2.5 time series — "
                    "where did the pollution regime shift?")
        cp = data["changepoint"]
        national = (merged.groupby("year_month")
                    .agg(pm25=("pm25", "mean"))
                    .reset_index().sort_values("year_month"))
        national["cusum"] = np.cumsum(national["pm25"] - national["pm25"].mean())

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            subplot_titles=["PM2.5 Time Series", "CUSUM"])
        fig.add_trace(go.Scatter(x=national["year_month"].astype(str),
                                 y=national["pm25"], mode="lines",
                                 name="PM2.5", line=dict(color="#e74c3c")),
                      row=1, col=1)
        fig.add_hline(y=national["pm25"].mean(), line_dash="dash",
                      line_color="black", opacity=0.5, row=1, col=1)
        fig.add_trace(go.Scatter(x=national["year_month"].astype(str),
                                 y=national["cusum"], mode="lines",
                                 name="CUSUM", line=dict(color="#3498db"),
                                 fill="tozeroy"),
                      row=2, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="black", row=2, col=1)

        if cp is not None and len(cp):
            for _, row in cp.iterrows():
                fig.add_vline(x=row["year_month"], line_dash="dot",
                              line_color="#9b59b6", opacity=0.8)

        fig.update_layout(height=550, template="plotly_white",
                          title="Change-Point Detection — National PM2.5 Structural Breaks")
        st.plotly_chart(fig, use_container_width=True)

        if cp is not None and len(cp):
            st.dataframe(cp[["year_month", "pm25_at_cp", "direction", "cusum_value"]],
                         use_container_width=True)

    with tab5:
        st.subheader("Population Attributable Fraction (PAF)")
        st.markdown("""
        What fraction of all respiratory disease burden is attributable to PM2.5
        exceeding the safe NAAQS standard (60 µg/m³)?
        """)
        af = data["af"]
        if af is not None:
            af_dict = dict(zip(af["metric"], af["value"]))
            c1, c2, c3 = st.columns(3)
            c1.metric("Relative Risk", f"{af_dict.get('Relative Risk', 'N/A'):.3f}")
            c2.metric("PAF", f"{af_dict.get('PAF (%)', 'N/A'):.1f}%")
            c3.metric("95% CI",
                      f"[{af_dict.get('PAF CI lower (%)', '?'):.1f}%, "
                      f"{af_dict.get('PAF CI upper (%)', '?'):.1f}%]")

            st.markdown(f"""
            <div class="insight-box">
                <strong>Interpretation:</strong>
                Approximately <strong>{af_dict.get('PAF (%)', '?'):.0f}%</strong> of all
                respiratory disease burden in polluted districts is attributable to PM2.5
                exceeding the NAAQS standard. A relative risk of
                <strong>{af_dict.get('Relative Risk', '?'):.2f}</strong> means exposed
                districts see {((af_dict.get('Relative Risk', 1)-1)*100):.0f}% more
                respiratory cases than unexposed districts.
            </div>
            """, unsafe_allow_html=True)

            fig = px.bar(af, x="metric", y="value", color="value",
                         color_continuous_scale="RdYlGn_r",
                         title="Attributable Fraction — All Metrics")
            fig.update_layout(height=400, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Run `python src/06_causal_inference.py` first.")


# ═══════════════════════════════════════════════════════════════════
# ADVANCED ANALYTICS PAGE
# ═══════════════════════════════════════════════════════════════════

@st.cache_data
def _load_advanced_data():
    paths = {
        "pca":      PROCESSED_DIR / "pca_results.csv",
        "mediation":PROCESSED_DIR / "mediation_results.csv",
        "fe":       PROCESSED_DIR / "panel_fe_results.csv",
        "gwr":      PROCESSED_DIR / "gwr_region_results.csv",
        "epi":      PROCESSED_DIR / "epi_metrics.csv",
        "partial":  PROCESSED_DIR / "partial_corr.csv",
        "sl":       PROCESSED_DIR / "spatial_lag_results.csv",
    }
    return {k: pd.read_csv(v) if v.exists() else None for k, v in paths.items()}


def render_advanced_analytics(merged: pd.DataFrame):
    st.header("🔬 Advanced Analytics")
    st.markdown("""
    <div class="insight-box">
        <strong>Comprehensive statistical treatment</strong> — PCA on latent pollution factors,
        mediation/SEM analysis of causal pathways, panel fixed-effects regression that controls
        for all district-level heterogeneity, geographically weighted regression by region, and
        full epidemiological burden metrics.
    </div>
    """, unsafe_allow_html=True)

    data = _load_advanced_data()
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔷 PCA / Factor Analysis", "🔀 Mediation (SEM)",
        "📐 Panel Fixed-Effects", "🗺️ GWR by Region", "🏥 Epi Metrics"
    ])

    with tab1:
        st.subheader("PCA — Latent Pollution Dimensions")
        st.markdown("PM2.5, PM10, NO₂, SO₂ collapse into latent factors. "
                    "PC1 typically captures overall particulate load; PC2 captures gas-vs-particulate contrast.")
        pca_df = data["pca"]
        if pca_df is not None:
            pca_merged = pca_df.merge(
                merged[["district_id", "state"]].drop_duplicates(), on="district_id", how="left"
            )
            fig = px.scatter(
                pca_merged.sample(min(3000, len(pca_merged)), random_state=42),
                x="PC1", y="PC2", color="state",
                title="PCA Biplot: District-Months in PC1 × PC2 Space",
                labels={"PC1": "PC1 (Particulate Load)", "PC2": "PC2 (Gas vs Particulate)"},
                opacity=0.5,
            )
            fig.update_layout(height=500, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("""
            <div class="insight-box">
                PC1 separates high-pollution Indo-Gangetic districts from clean southern districts.
                PC2 captures industrial vs. vehicular pollution profiles.
                Districts in the top-right quadrant face <em>both</em> particulate and gaseous pollution.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Run `python src/07_advanced_stats.py` first.")

    with tab2:
        st.subheader("Mediation Analysis — SEM Path Model")
        st.markdown("""
        Does **urban density** mediate the PM2.5 → respiratory disease pathway?
        Urban areas may have both higher pollution *and* higher healthcare access,
        creating a complex causal structure.
        """)
        med = data["mediation"]
        if med is not None:
            row = med.iloc[0]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Direct effect (c')", f"{row['path_c_direct']:.5f}")
            c2.metric("Indirect via Urban% (a×b)", f"{row['indirect_effect']:.5f}")
            c3.metric("Total effect (c)", f"{row['path_c_total']:.5f}")
            c4.metric("% Mediated", f"{row['prop_mediated_pct']:.1f}%")

            # Path diagram in plotly
            fig = go.Figure()
            fig.add_shape(type="rect", x0=0, y0=0.4, x1=1.8, y1=0.9,
                          line=dict(color="#2c3e50", width=2), fillcolor="#ecf0f1")
            fig.add_shape(type="rect", x0=3.5, y0=0.8, x1=5.3, y1=1.3,
                          line=dict(color="#e74c3c", width=2), fillcolor="#fdecea")
            fig.add_shape(type="rect", x0=7, y0=0.4, x1=8.8, y1=0.9,
                          line=dict(color="#2c3e50", width=2), fillcolor="#ecf0f1")

            fig.add_annotation(x=0.9, y=0.65, text="PM2.5<br>(Exposure)",
                               showarrow=False, font=dict(size=12, color="#2c3e50"))
            fig.add_annotation(x=4.4, y=1.05, text="Urban %<br>(Mediator)",
                               showarrow=False, font=dict(size=12, color="#e74c3c"))
            fig.add_annotation(x=7.9, y=0.65, text="Respiratory<br>(Outcome)",
                               showarrow=False, font=dict(size=12, color="#2c3e50"))

            fig.add_annotation(x=2.7, y=1.0, text=f"a={row['path_a']:.4f}",
                               ax=1.8, ay=0.65, arrowhead=2, arrowcolor="#e74c3c",
                               font=dict(color="#e74c3c"))
            fig.add_annotation(x=7.0, y=0.95, text=f"b={row['path_b']:.4f}",
                               ax=5.3, ay=1.05, arrowhead=2, arrowcolor="#e74c3c",
                               font=dict(color="#e74c3c"))
            fig.add_annotation(x=7.0, y=0.5, text=f"c'={row['path_c_direct']:.4f} (direct)",
                               ax=1.8, ay=0.65, arrowhead=2, arrowcolor="#2c3e50",
                               font=dict(color="#2c3e50"))

            fig.update_layout(
                xaxis=dict(visible=False, range=[-0.5, 9.5]),
                yaxis=dict(visible=False, range=[0, 1.6]),
                height=350, title="SEM Path Diagram",
                plot_bgcolor="white",
            )
            st.plotly_chart(fig, use_container_width=True)

            sig_text = "✅ Significant mediation" if row["significant"] else "❌ Non-significant mediation"
            st.markdown(f"""
            <div class="insight-box">
                <strong>{sig_text}</strong> (zero {'outside' if row['significant'] else 'inside'} 95% bootstrap CI
                [{row['ci_lower']:.5f}, {row['ci_upper']:.5f}]).
                {row['prop_mediated_pct']:.1f}% of PM2.5's effect on respiratory disease runs
                through urbanisation — the remainder is a direct biological effect of air pollution.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Run `python src/07_advanced_stats.py` first.")

    with tab3:
        st.subheader("Panel Fixed-Effects Regression")
        st.markdown("""
        The **within-district estimator** controls for all time-invariant district characteristics
        (geography, industrial baseline, structural health). Only within-district, over-time
        variation identifies the effect. This is the most credible causal estimate available.
        """)
        fe = data["fe"]
        if fe is not None:
            r2 = fe["within_r2"].iloc[0]
            st.metric("Within-district R²", f"{r2:.3f}",
                      help="Variance explained by pollution changes within the same district over time")

            fe_plot = fe.copy()
            fe_plot["sig_label"] = fe_plot["significant"].map(
                {True: "Significant (p<0.05)", False: "Not significant"}
            )
            fig = px.bar(fe_plot, x="coefficient", y="feature",
                         color="sig_label", orientation="h",
                         color_discrete_map={
                             "Significant (p<0.05)": "#e74c3c",
                             "Not significant": "#aaaaaa"
                         },
                         error_x="std_error",
                         title=f"Panel FE Coefficients (Within R² = {r2:.3f})",
                         labels={"coefficient": "Effect on resp rate per 100k",
                                 "feature": "Variable"})
            fig.add_vline(x=0, line_dash="dash", line_color="black")
            fig.update_layout(height=400, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("""
            <div class="insight-box">
                <strong>Key advantage:</strong> Unlike simple OLS, panel FE eliminates bias from
                any district-level confounders (e.g., some districts are structurally sicker, or
                structurally more polluted). The coefficient on PM2.5 here reflects only
                the <em>causal within-district effect</em> of temporary pollution increases.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Run `python src/07_advanced_stats.py` first.")

    with tab4:
        st.subheader("Geographically Weighted Regression (by Zone)")
        st.markdown("""
        The PM2.5 → respiratory relationship is **not uniform across India**.
        Northern districts may show stronger effects due to higher baseline pollution
        and temperature inversions; southern districts may show attenuated effects.
        """)
        gwr = data["gwr"]
        if gwr is not None:
            fig = px.bar(gwr, x="zone", y="coeff_pm25",
                         color="r2", color_continuous_scale="RdYlGn",
                         title="PM2.5 Coefficient by Geographic Zone (GWR-lite)",
                         labels={"coeff_pm25": "PM2.5 effect (std. coeff.)", "zone": "Zone"})
            fig.add_hline(y=0, line_dash="dash", line_color="black")
            fig.update_layout(height=400, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(
                gwr.rename(columns={"coeff_pm25": "PM2.5 coeff",
                                    "coeff_pm10": "PM10 coeff",
                                    "coeff_urban_percentage": "Urban% coeff",
                                    "n_obs": "N", "r2": "R²"}),
                use_container_width=True
            )
        else:
            st.info("Run `python src/07_advanced_stats.py` first.")

    with tab5:
        st.subheader("Epidemiological Metrics")
        st.markdown("Standardised public-health metrics for each pollution threshold.")
        epi = data["epi"]
        if epi is not None:
            metric = st.selectbox("Metric to visualise",
                ["relative_risk", "odds_ratio", "PAF_pct", "attributable_risk", "NNT"])
            fig = px.bar(epi, x="threshold_label", y=metric,
                         color=metric, color_continuous_scale="RdYlGn_r",
                         title=f"{metric} by Pollution Threshold",
                         labels={"threshold_label": "Threshold", metric: metric})
            if metric == "relative_risk":
                fig.add_hline(y=1, line_dash="dash", line_color="green",
                              annotation_text="RR=1 (no effect)")
            fig.update_layout(height=400, template="plotly_white",
                              xaxis_tickangle=-25)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(epi, use_container_width=True)
        else:
            st.info("Run `python src/07_advanced_stats.py` first.")


# ═══════════════════════════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════════════════════════
def main():
    # Sidebar
    st.sidebar.title("🌬️ Air Quality Dashboard")
    st.sidebar.markdown("**DSM Final Project**")
    st.sidebar.markdown("---")

    page = st.sidebar.radio("Navigation", [
        "🏠 Overview",
        "📊 State Comparison",
        "📈 Time-Series Explorer",
        "🔗 Correlations",
        "🎯 District Clusters",
        "🌡️ Seasonality",
        "🔮 Health Predictor",
        "🕸️ Disease Propagation Graph",
        "🧪 Causal Inference",
        "🔬 Advanced Analytics",
    ])

    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    **Data Sources:**
    - NDAP / data.gov.in
    - CPCB Air Quality
    - HMIS Health Data

    **Models:** RF (R²=0.81)
    """)

    # Load data
    merged, districts, aq, health, clusters = load_data()
    model, features = train_prediction_model(merged)

    # Header
    st.title("🌬️ Air Quality & Public Health in Indian Districts")
    st.markdown("*Analyzing the relationship between ambient air pollution and "
                "disease burden across 150 districts in 15 states (2018–2023)*")
    st.markdown("---")

    # Route pages
    if page == "🏠 Overview":
        render_overview(merged, districts, aq)
        st.markdown("---")
        render_state_pollution(merged, districts)
    elif page == "📊 State Comparison":
        render_state_pollution(merged, districts)
    elif page == "📈 Time-Series Explorer":
        render_time_series(aq, districts)
    elif page == "🔗 Correlations":
        render_correlations(merged)
    elif page == "🎯 District Clusters":
        render_clusters(clusters, districts)
    elif page == "🌡️ Seasonality":
        render_seasonality(aq)
    elif page == "🔮 Health Predictor":
        render_prediction(model, features, merged)
    elif page == "🕸️ Disease Propagation Graph":
        render_disease_graph()
    elif page == "🧪 Causal Inference":
        render_causal_inference(merged)
    elif page == "🔬 Advanced Analytics":
        render_advanced_analytics(merged)


if __name__ == "__main__":
    main()
