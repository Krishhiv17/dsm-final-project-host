"""
05_graph_spatial.py
===================
Graph Analysis & Spatial Statistics

1.  Build district spatial proximity graph (haversine, 300 km threshold)
2.  Spatial autocorrelation — Moran's I for PM2.5 and respiratory burden
3.  Community detection — Louvain (disease propagation zones, cross-state)
4.  Graph centrality — degree, betweenness, eigenvector (hub districts)
5.  Granger causality on neighbour pairs → directed causal graph
6.  Knowledge Graph — typed relationships (PROXIMATE_TO, SAME_STATE,
    POLLUTION_CAUSES_HEALTH, SAME_RISK_CLUSTER, SIMILAR_PROFILE)
7.  Link prediction — Jaccard & Adamic-Adar coefficients

Outputs (data/processed/):
    graph_nodes.csv          — node features + community + centrality
    graph_edges.csv          — proximity + Granger directed edges
    knowledge_graph.csv      — typed semantic relationships
    spatial_autocorr.csv     — Moran's I results

Figures (notebooks/figures/):
    15_spatial_graph.png
    16_community_detection.png
    17_centrality.png
    18_knowledge_graph.png
"""

import warnings
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
from pathlib import Path
from scipy import stats

warnings.filterwarnings("ignore")

try:
    from statsmodels.tsa.stattools import grangercausalitytests
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False
    print("  [WARN] statsmodels not installed — Granger step will be skipped.")

# ── Paths ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FIG_DIR       = PROJECT_ROOT / "notebooks" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

plt.style.use("seaborn-v0_8-whitegrid")
DPI = 150
PROXIMITY_THRESHOLD_KM = 300
GRANGER_MAXLAG = 4
GRANGER_ALPHA  = 0.10   # looser threshold — synthetic data has moderate signal


# ════════════════════════════════════════════════════════════════════
# 1. UTILITIES
# ════════════════════════════════════════════════════════════════════

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (np.sin(dlat / 2) ** 2
         + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2))
         * np.sin(dlon / 2) ** 2)
    return 2 * R * np.arcsin(np.sqrt(a))


def row_standardise(W: np.ndarray) -> np.ndarray:
    row_sums = W.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    return W / row_sums


def morans_i(values: np.ndarray, W: np.ndarray):
    """
    Compute Moran's I and a Monte-Carlo p-value.
    Returns (I_stat, z_score, p_value_mc, expected_I)
    """
    n = len(values)
    x = values - values.mean()
    W_rs = row_standardise(W.copy())
    W_sum = W_rs.sum()

    numerator   = (x @ W_rs @ x)
    denominator = (x @ x)
    I = (n / W_sum) * (numerator / denominator)
    expected_I = -1.0 / (n - 1)

    # Monte-Carlo permutation test (999 permutations)
    n_perms = 999
    perm_I = []
    rng = np.random.default_rng(42)
    for _ in range(n_perms):
        xp = rng.permutation(x)
        perm_I.append((n / W_sum) * (xp @ W_rs @ xp) / (xp @ xp))
    perm_I = np.array(perm_I)
    p_mc = (np.sum(perm_I >= I) + 1) / (n_perms + 1)
    z = (I - expected_I) / perm_I.std()
    return I, z, p_mc, expected_I


# ════════════════════════════════════════════════════════════════════
# 2. LOAD DATA
# ════════════════════════════════════════════════════════════════════

def load_data():
    print("\n  Loading data...")
    geo     = pd.read_csv(PROCESSED_DIR / "districts_geocoded.csv")
    merged  = pd.read_csv(PROCESSED_DIR / "air_health_merged.csv")
    merged["resp_rate_per_100k"] = (
        merged["respiratory_cases"] * 100_000 / merged["population"].replace(0, np.nan)
    )
    clusters = None
    cp = PROCESSED_DIR / "district_clusters.csv"
    if cp.exists():
        clusters = pd.read_csv(cp)
    print(f"  Geocoded districts: {len(geo)}")
    print(f"  Merged rows: {len(merged):,}")
    return geo, merged, clusters


# ════════════════════════════════════════════════════════════════════
# 3. BUILD PROXIMITY GRAPH
# ════════════════════════════════════════════════════════════════════

def build_proximity_graph(geo: pd.DataFrame, threshold_km=PROXIMITY_THRESHOLD_KM):
    print(f"\n  Building proximity graph (threshold = {threshold_km} km)...")
    G = nx.Graph()

    for _, row in geo.iterrows():
        G.add_node(
            row["district_id"],
            name=row["district_name"],
            state=row["state"],
            lat=row["latitude"],
            lon=row["longitude"],
            population=row.get("population", 0),
            urban_pct=row.get("urban_percentage", 0),
        )

    ids   = geo["district_id"].values
    lats  = geo["latitude"].values
    lons  = geo["longitude"].values

    edge_count = 0
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            dist = haversine_km(lats[i], lons[i], lats[j], lons[j])
            if dist <= threshold_km:
                G.add_edge(
                    ids[i], ids[j],
                    distance_km=round(dist, 1),
                    weight=round(1.0 / max(dist, 1.0), 6),
                    edge_type="PROXIMATE_TO",
                )
                edge_count += 1

    print(f"  Graph: {G.number_of_nodes()} nodes, {edge_count} proximity edges")
    return G


# ════════════════════════════════════════════════════════════════════
# 4. SPATIAL AUTOCORRELATION — MORAN'S I
# ════════════════════════════════════════════════════════════════════

def spatial_autocorrelation(G: nx.Graph, geo: pd.DataFrame, merged: pd.DataFrame):
    print("\n  Computing Moran's I...")

    # District-level aggregates
    district_agg = merged.groupby("district_id").agg(
        pm25_mean=("pm25", "mean"),
        resp_mean=("respiratory_cases", "mean"),
        aqi_mean=("aqi", "mean"),
    ).reset_index()
    pop_mean = merged.groupby("district_id")["population"].mean().rename("pop_mean")
    district_agg = district_agg.join(pop_mean, on="district_id")
    district_agg["resp_rate_mean"] = (
        district_agg["resp_mean"] * 100_000 / district_agg["pop_mean"].replace(0, np.nan)
    )
    district_agg = district_agg.drop(columns=["pop_mean"])
    district_agg = district_agg.merge(geo[["district_id", "latitude", "longitude"]], on="district_id")

    # Only keep nodes present in both graph and aggregates
    common_ids = sorted(set(G.nodes()) & set(district_agg["district_id"]))
    district_agg = district_agg[district_agg["district_id"].isin(common_ids)].sort_values("district_id")
    n = len(district_agg)

    # Build binary adjacency matrix
    id_to_idx = {did: i for i, did in enumerate(district_agg["district_id"])}
    W = np.zeros((n, n))
    for u, v in G.edges():
        if u in id_to_idx and v in id_to_idx:
            i, j = id_to_idx[u], id_to_idx[v]
            W[i, j] = 1
            W[j, i] = 1

    results = []
    variables = {
        "PM2.5":              district_agg["pm25_mean"].values,
        "Respiratory Cases":  district_agg["resp_mean"].values,
        "Resp Rate/100k":     district_agg["resp_rate_mean"].values,
        "AQI":                district_agg["aqi_mean"].values,
    }

    for var_name, values in variables.items():
        I, z, p, E_I = morans_i(values, W)
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
        print(f"    {var_name:<25} I={I:+.4f}  z={z:+.3f}  p={p:.4f}  {sig}")
        results.append({
            "variable": var_name, "morans_I": round(I, 5),
            "z_score": round(z, 4), "p_value_mc": round(p, 5),
            "expected_I": round(E_I, 5),
            "interpretation": ("clustered" if I > E_I and p < 0.05
                               else "dispersed" if I < E_I and p < 0.05
                               else "random"),
        })

    results_df = pd.DataFrame(results)
    results_df.to_csv(PROCESSED_DIR / "spatial_autocorr.csv", index=False)
    print("  → Saved: spatial_autocorr.csv")
    return district_agg, results_df


# ════════════════════════════════════════════════════════════════════
# 5. COMMUNITY DETECTION
# ════════════════════════════════════════════════════════════════════

def detect_communities(G: nx.Graph):
    print("\n  Detecting communities (Louvain)...")
    try:
        communities = nx.community.louvain_communities(G, seed=42)
    except AttributeError:
        # Fallback for older networkx
        communities = list(nx.community.greedy_modularity_communities(G))

    community_map = {}
    for cid, nodes in enumerate(communities):
        for node in nodes:
            community_map[node] = cid

    nx.set_node_attributes(G, community_map, "community")

    # Summarise communities
    rows = []
    for cid, nodes in enumerate(communities):
        states = [G.nodes[n]["state"] for n in nodes if "state" in G.nodes[n]]
        unique_states = list(set(states))
        rows.append({
            "community_id": cid,
            "n_districts": len(nodes),
            "states": ", ".join(sorted(unique_states)),
            "n_states": len(unique_states),
            "cross_state": len(unique_states) > 1,
        })
        label = "cross-state" if len(unique_states) > 1 else "within-state"
        print(f"    Community {cid}: {len(nodes)} districts across {len(unique_states)} state(s) [{label}]")
        print(f"      States: {', '.join(sorted(unique_states))}")

    modularity = nx.community.modularity(G, communities)
    print(f"  Modularity Q = {modularity:.4f}")
    return community_map, communities, modularity


# ════════════════════════════════════════════════════════════════════
# 6. GRAPH CENTRALITY
# ════════════════════════════════════════════════════════════════════

def compute_centrality(G: nx.Graph, district_agg: pd.DataFrame):
    print("\n  Computing centrality measures...")
    degree_c      = nx.degree_centrality(G)
    betweenness_c = nx.betweenness_centrality(G, weight="weight", normalized=True)
    try:
        eigen_c = nx.eigenvector_centrality(G, weight="weight", max_iter=500)
    except nx.PowerIterationFailedConvergence:
        eigen_c = {n: 0.0 for n in G.nodes()}

    nx.set_node_attributes(G, degree_c,      "degree_centrality")
    nx.set_node_attributes(G, betweenness_c, "betweenness_centrality")
    nx.set_node_attributes(G, eigen_c,       "eigenvector_centrality")

    centrality_df = pd.DataFrame({
        "district_id":          list(degree_c.keys()),
        "degree_centrality":    [round(v, 5) for v in degree_c.values()],
        "betweenness_centrality": [round(betweenness_c[n], 5) for n in degree_c.keys()],
        "eigenvector_centrality": [round(eigen_c[n], 5) for n in degree_c.keys()],
    })

    # Print top 10 by betweenness (most "bridging" districts)
    top10 = centrality_df.nlargest(10, "betweenness_centrality")
    print(f"\n  Top-10 Hub Districts (betweenness centrality):")
    for _, r in top10.iterrows():
        node_data = G.nodes[r["district_id"]]
        name  = node_data.get("name", r["district_id"])
        state = node_data.get("state", "?")
        print(f"    {name:<25} {state:<20} BC={r['betweenness_centrality']:.4f}")

    return centrality_df


# ════════════════════════════════════════════════════════════════════
# 7. GRANGER CAUSALITY ON NEIGHBOUR PAIRS
# ════════════════════════════════════════════════════════════════════

def granger_on_neighbors(G: nx.Graph, merged: pd.DataFrame):
    """
    For each proximity edge (district_i, district_j):
      Test: does district_i's PM2.5 Granger-cause district_j's respiratory cases?
    Significant edges become directed causal edges in the graph.
    """
    if not HAS_STATSMODELS:
        print("\n  [SKIP] Granger on neighbours — statsmodels not available")
        return pd.DataFrame(), nx.DiGraph()

    print(f"\n  Running Granger causality on {G.number_of_edges()} neighbour pairs...")
    print(f"  (max lag = {GRANGER_MAXLAG}, α = {GRANGER_ALPHA})")

    # Pivot: monthly time series per district
    monthly_pm25 = (
        merged.groupby(["district_id", "year_month"])["pm25"]
        .mean().reset_index()
        .pivot(index="year_month", columns="district_id", values="pm25")
        .sort_index()
    )
    monthly_resp = (
        merged.groupby(["district_id", "year_month"])["respiratory_cases"]
        .mean().reset_index()
        .pivot(index="year_month", columns="district_id", values="respiratory_cases")
        .sort_index()
    )

    causal_digraph = nx.DiGraph()
    causal_digraph.add_nodes_from(G.nodes(data=True))

    granger_rows = []
    edges = list(G.edges())

    for u, v in edges:
        # Test both directions
        for src, tgt in [(u, v), (v, u)]:
            if src not in monthly_pm25.columns or tgt not in monthly_resp.columns:
                continue

            x = monthly_pm25[src].dropna()
            y = monthly_resp[tgt].dropna()
            common_idx = x.index.intersection(y.index)
            if len(common_idx) < GRANGER_MAXLAG + 5:
                continue

            data = np.column_stack([
                y.loc[common_idx].values,
                x.loc[common_idx].values,
            ])

            try:
                gc_res = grangercausalitytests(data, maxlag=GRANGER_MAXLAG, verbose=False)
                best_p = 1.0
                best_lag = 1
                best_f = 0.0
                for lag in range(1, GRANGER_MAXLAG + 1):
                    f_stat, p_val, _, _ = gc_res[lag][0]["ssr_ftest"]
                    if p_val < best_p:
                        best_p, best_lag, best_f = p_val, lag, f_stat

                significant = best_p < GRANGER_ALPHA
                granger_rows.append({
                    "source_district":  src,
                    "target_district":  tgt,
                    "best_lag_months":  best_lag,
                    "F_stat":           round(best_f, 4),
                    "p_value":          round(best_p, 5),
                    "significant":      significant,
                    "direction":        f"{src}→{tgt}",
                })

                if significant:
                    causal_digraph.add_edge(
                        src, tgt,
                        edge_type="POLLUTION_CAUSES_HEALTH",
                        lag_months=best_lag,
                        F_stat=round(best_f, 3),
                        p_value=round(best_p, 5),
                        weight=round(1 - best_p, 5),
                    )
            except Exception:
                pass

    granger_df = pd.DataFrame(granger_rows)
    n_sig = granger_df["significant"].sum() if len(granger_df) else 0
    print(f"  Pairs tested: {len(granger_df)}  |  Significant causal edges: {n_sig}")
    print(f"  → {n_sig} directed edges added to causal DiGraph")

    if len(granger_df):
        granger_df.to_csv(PROCESSED_DIR / "granger_neighbor_results.csv", index=False)
        print("  → Saved: granger_neighbor_results.csv")

    return granger_df, causal_digraph


# ════════════════════════════════════════════════════════════════════
# 8. KNOWLEDGE GRAPH — TYPED RELATIONSHIPS
# ════════════════════════════════════════════════════════════════════

def build_knowledge_graph(G: nx.Graph, causal_digraph: nx.DiGraph,
                           district_agg: pd.DataFrame, clusters=None):
    """
    Construct a multi-relational knowledge graph with 5 edge types:
      PROXIMATE_TO          — within 300 km (undirected)
      SAME_STATE            — administrative neighbour (undirected)
      POLLUTION_CAUSES_HEALTH — Granger-significant (directed)
      SAME_RISK_CLUSTER     — same K-means cluster (undirected)
      SIMILAR_PROFILE       — cosine similarity of pollution vectors > 0.90
    """
    print("\n  Building knowledge graph with typed relationships...")
    kg_rows = []

    # ── Type 1: PROXIMATE_TO ─────────────────────────────────────
    for u, v, data in G.edges(data=True):
        kg_rows.append({
            "source_id": u, "target_id": v,
            "relationship": "PROXIMATE_TO",
            "weight": data.get("weight", 1.0),
            "metadata": f"distance_km={data.get('distance_km', '?')}",
            "directed": False,
        })

    # ── Type 2: SAME_STATE ───────────────────────────────────────
    nodes = list(G.nodes(data=True))
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            ni, di = nodes[i]
            nj, dj = nodes[j]
            if di.get("state") == dj.get("state"):
                kg_rows.append({
                    "source_id": ni, "target_id": nj,
                    "relationship": "SAME_STATE",
                    "weight": 1.0,
                    "metadata": f"state={di.get('state', '?')}",
                    "directed": False,
                })

    # ── Type 3: POLLUTION_CAUSES_HEALTH ─────────────────────────
    for u, v, data in causal_digraph.edges(data=True):
        kg_rows.append({
            "source_id": u, "target_id": v,
            "relationship": "POLLUTION_CAUSES_HEALTH",
            "weight": data.get("weight", 0.5),
            "metadata": (f"lag={data.get('lag_months', '?')}mo,"
                         f"p={data.get('p_value', '?')}"),
            "directed": True,
        })

    # ── Type 4: SAME_RISK_CLUSTER ────────────────────────────────
    if clusters is not None and "cluster" in clusters.columns:
        for cluster_id, group in clusters.groupby("cluster"):
            ids = group["district_id"].tolist()
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    kg_rows.append({
                        "source_id": ids[i], "target_id": ids[j],
                        "relationship": "SAME_RISK_CLUSTER",
                        "weight": 1.0,
                        "metadata": f"cluster={cluster_id}",
                        "directed": False,
                    })

    # ── Type 5: SIMILAR_PROFILE (cosine similarity) ──────────────
    poll_cols = [c for c in ["pm25_mean", "pm10", "no2", "so2"]
                 if c in district_agg.columns]
    if len(poll_cols) >= 2:
        ids   = district_agg["district_id"].values
        vecs  = district_agg[poll_cols].fillna(0).values.astype(float)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1
        vecs_n = vecs / norms
        sim_matrix = vecs_n @ vecs_n.T
        threshold = 0.92
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                sim = sim_matrix[i, j]
                if sim >= threshold:
                    kg_rows.append({
                        "source_id": ids[i], "target_id": ids[j],
                        "relationship": "SIMILAR_PROFILE",
                        "weight": round(float(sim), 4),
                        "metadata": f"cosine_sim={round(float(sim), 4)}",
                        "directed": False,
                    })

    kg_df = pd.DataFrame(kg_rows)
    rel_counts = kg_df["relationship"].value_counts()
    print(f"  Knowledge graph: {len(kg_df):,} total triples")
    for rel, cnt in rel_counts.items():
        print(f"    {rel:<30}: {cnt:,}")

    kg_df.to_csv(PROCESSED_DIR / "knowledge_graph.csv", index=False)
    print("  → Saved: knowledge_graph.csv")
    return kg_df


# ════════════════════════════════════════════════════════════════════
# 9. LINK PREDICTION
# ════════════════════════════════════════════════════════════════════

def link_prediction(G: nx.Graph, causal_digraph: nx.DiGraph, top_n=20):
    """
    Predict which district pairs outside the current proximity graph are most
    likely to develop causal pollution links under worsening conditions or with
    more data.  Scores ALL non-edges (districts > 300 km apart) using Jaccard
    coefficient and Adamic-Adar index on the existing proximity graph — pairs
    that share many mutual neighbours despite geographic distance are the most
    likely candidates for long-range propagation corridors.
    """
    print("\n  Running link prediction (non-proximity pairs)...")

    nodes = list(G.nodes())
    # All pairs not currently in the proximity graph
    candidate_pairs = [
        (nodes[i], nodes[j])
        for i in range(len(nodes))
        for j in range(i + 1, len(nodes))
        if not G.has_edge(nodes[i], nodes[j])
    ]

    print(f"  Scoring {len(candidate_pairs):,} non-proximity pairs...")

    jaccard_scores = {(u, v): p for u, v, p in nx.jaccard_coefficient(G, candidate_pairs)}
    aa_scores      = {(u, v): p for u, v, p in nx.adamic_adar_index(G, candidate_pairs)}

    rows = []
    for u, v in candidate_pairs:
        j  = jaccard_scores.get((u, v), 0.0)
        aa = aa_scores.get((u, v), 0.0)
        if j == 0 and aa == 0:
            continue   # no shared neighbours — uninformative
        rows.append({
            "district_a":  u,
            "district_b":  v,
            "name_a":      G.nodes[u].get("name",  str(u)),
            "name_b":      G.nodes[v].get("name",  str(v)),
            "state_a":     G.nodes[u].get("state", "?"),
            "state_b":     G.nodes[v].get("state", "?"),
            "community_a": G.nodes[u].get("community", -1),
            "community_b": G.nodes[v].get("community", -1),
            "jaccard":     round(j,  5),
            "adamic_adar": round(aa, 5),
        })

    lp_df = pd.DataFrame(rows)
    if len(lp_df):
        j_max  = lp_df["jaccard"].max()     + 1e-9
        aa_max = lp_df["adamic_adar"].max() + 1e-9
        lp_df["combined_score"] = (
            lp_df["jaccard"] / j_max + lp_df["adamic_adar"] / aa_max
        )
        lp_df["same_community"] = (
            lp_df["community_a"] == lp_df["community_b"]
        )
        lp_df = lp_df.sort_values("combined_score", ascending=False).reset_index(drop=True)
        lp_df.to_csv(PROCESSED_DIR / "link_prediction.csv", index=False)

        print(f"\n  Top {min(top_n, len(lp_df))} Predicted Long-Range Propagation Links:")
        for _, r in lp_df.head(top_n).iterrows():
            tag = "same-zone" if r["same_community"] else "cross-zone"
            print(f"    {r['name_a']:<22} ↔ {r['name_b']:<22}  "
                  f"AA={r['adamic_adar']:.4f}  J={r['jaccard']:.4f}  [{tag}]")
        print("  → Saved: link_prediction.csv")
    else:
        print("  [WARN] No non-proximity pairs with shared neighbours found.")

    return lp_df


# ════════════════════════════════════════════════════════════════════
# 10. SAVE NODE TABLE
# ════════════════════════════════════════════════════════════════════

def save_node_table(G: nx.Graph, centrality_df: pd.DataFrame, district_agg: pd.DataFrame):
    rows = []
    for node_id, attrs in G.nodes(data=True):
        rows.append({
            "district_id": node_id,
            "district_name": attrs.get("name", ""),
            "state": attrs.get("state", ""),
            "lat": attrs.get("lat", np.nan),
            "lon": attrs.get("lon", np.nan),
            "community": attrs.get("community", -1),
        })

    nodes_df = pd.DataFrame(rows)
    nodes_df = nodes_df.merge(centrality_df, on="district_id", how="left")
    nodes_df = nodes_df.merge(
        district_agg[["district_id", "pm25_mean", "resp_mean", "resp_rate_mean"]],
        on="district_id", how="left"
    )
    nodes_df.to_csv(PROCESSED_DIR / "graph_nodes.csv", index=False)
    print("  → Saved: graph_nodes.csv")

    edge_rows = []
    for u, v, data in G.edges(data=True):
        edge_rows.append({
            "source_id": u, "target_id": v,
            **{k: v2 for k, v2 in data.items()},
        })
    edges_df = pd.DataFrame(edge_rows)
    edges_df.to_csv(PROCESSED_DIR / "graph_edges.csv", index=False)
    print("  → Saved: graph_edges.csv")
    return nodes_df


# ════════════════════════════════════════════════════════════════════
# 11. VISUALISATIONS
# ════════════════════════════════════════════════════════════════════

def _layout(G, geo):
    pos = {}
    for node_id in G.nodes():
        row = geo[geo["district_id"] == node_id]
        if len(row):
            pos[node_id] = (float(row.iloc[0]["longitude"]),
                            float(row.iloc[0]["latitude"]))
        else:
            pos[node_id] = (0.0, 0.0)
    return pos


def plot_spatial_graph(G, nodes_df, geo):
    print("\n  Plotting spatial graph...")
    pos = _layout(G, geo)

    pm25_values = nodes_df.set_index("district_id")["pm25_mean"].to_dict()
    node_colors = [pm25_values.get(n, 50) for n in G.nodes()]

    fig, ax = plt.subplots(figsize=(16, 12))
    nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.15, width=0.4, edge_color="#aaaaaa")
    nc = nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_color=node_colors, cmap=plt.cm.RdYlGn_r,
        node_size=60, alpha=0.85,
    )
    plt.colorbar(nc, ax=ax, label="Mean PM2.5 (µg/m³)", shrink=0.7)
    ax.set_title(f"District Proximity Graph\n({G.number_of_nodes()} nodes, "
                 f"{G.number_of_edges()} edges, threshold {PROXIMITY_THRESHOLD_KM} km)",
                 fontsize=14, fontweight="bold")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "15_spatial_graph.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 15_spatial_graph.png")


def plot_communities(G, communities, geo):
    print("  Plotting community detection...")
    pos = _layout(G, geo)
    n_comm = len(communities)
    cmap   = plt.cm.get_cmap("tab20", n_comm)
    colors = {node: cmap(G.nodes[node].get("community", 0)) for node in G.nodes()}
    node_color_list = [colors[n] for n in G.nodes()]

    fig, ax = plt.subplots(figsize=(16, 12))
    nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.10, width=0.4, edge_color="#cccccc")
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_color_list, node_size=60, alpha=0.9)
    patches = [mpatches.Patch(color=cmap(i), label=f"Zone {i}") for i in range(min(n_comm, 12))]
    ax.legend(handles=patches, loc="lower left", fontsize=8, title="Disease Zones")
    ax.set_title(f"Community Detection — {n_comm} Disease Propagation Zones\n"
                 f"(cross-state zones shown as distinct communities)",
                 fontsize=14, fontweight="bold")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "16_community_detection.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 16_community_detection.png")


def plot_centrality(G, nodes_df, geo):
    print("  Plotting centrality...")
    pos = _layout(G, geo)
    bc = nodes_df.set_index("district_id")["betweenness_centrality"].to_dict()
    ec = nodes_df.set_index("district_id")["eigenvector_centrality"].to_dict()

    fig, axes = plt.subplots(1, 2, figsize=(20, 9))

    for ax, (centrality_dict, title, cmap) in zip(axes, [
        (bc, "Betweenness Centrality\n(bridge / gateway districts)", plt.cm.Oranges),
        (ec, "Eigenvector Centrality\n(influence hubs)", plt.cm.Blues),
    ]):
        values = [centrality_dict.get(n, 0) for n in G.nodes()]
        sizes  = [20 + v * 600 for v in values]
        nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.10, width=0.4, edge_color="#cccccc")
        nc = nx.draw_networkx_nodes(G, pos, ax=ax, node_color=values, cmap=cmap,
                                    node_size=sizes, alpha=0.85)
        plt.colorbar(nc, ax=ax, shrink=0.7)
        ax.set_title(title, fontsize=13, fontweight="bold")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")

    plt.suptitle("Graph Centrality — Identifying Disease Propagation Hubs",
                 fontsize=15, fontweight="bold")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "17_centrality.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 17_centrality.png")


def plot_knowledge_graph(kg_df, G, geo):
    print("  Plotting knowledge graph (subgraph of causal edges)...")
    causal_edges = kg_df[kg_df["relationship"] == "POLLUTION_CAUSES_HEALTH"]

    if len(causal_edges) == 0:
        print("  [SKIP] No causal edges to plot.")
        return

    fig, axes = plt.subplots(1, 2, figsize=(20, 9))

    # Left: full KG edge-type breakdown
    ax = axes[0]
    rel_counts = kg_df["relationship"].value_counts()
    colors_kg = ["#3498db", "#2ecc71", "#e74c3c", "#f39c12", "#9b59b6"]
    ax.barh(rel_counts.index, rel_counts.values,
            color=colors_kg[:len(rel_counts)], edgecolor="black")
    ax.set_title("Knowledge Graph — Relationship Type Distribution",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Number of Triples")
    for i, (idx, val) in enumerate(rel_counts.items()):
        ax.text(val + 5, i, str(val), va="center", fontsize=9)

    # Right: causal DiGraph on geographic layout
    ax = axes[1]
    pos = _layout(G, geo)
    causal_nodes = set(causal_edges["source_id"]) | set(causal_edges["target_id"])
    pos_sub = {n: pos[n] for n in causal_nodes if n in pos}

    if pos_sub:
        DG_sub = nx.DiGraph()
        for _, row in causal_edges.iterrows():
            DG_sub.add_edge(row["source_id"], row["target_id"],
                            weight=row["weight"])

        nx.draw_networkx_nodes(DG_sub, pos_sub, ax=ax, node_color="#e74c3c",
                               node_size=80, alpha=0.8)
        nx.draw_networkx_edges(DG_sub, pos_sub, ax=ax,
                               edge_color="#c0392b", alpha=0.6,
                               arrows=True, arrowsize=12, width=1.2,
                               connectionstyle="arc3,rad=0.1")
        ax.set_title(f"Causal Propagation Edges\n"
                     f"(PM2.5 district A → Respiratory district B, Granger p<{GRANGER_ALPHA})",
                     fontsize=12, fontweight="bold")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")

    plt.suptitle("Knowledge Graph Analysis — Disease Propagation Semantics",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "18_knowledge_graph.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("  → Saved: 18_knowledge_graph.png")


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  DSM Final Project — Graph & Spatial Analysis")
    print("=" * 60)

    geo, merged, clusters = load_data()

    print("\n[1/9] Building proximity graph...")
    G = build_proximity_graph(geo)

    print("\n[2/9] Spatial autocorrelation (Moran's I)...")
    district_agg, autocorr_df = spatial_autocorrelation(G, geo, merged)

    print("\n[3/9] Community detection...")
    community_map, communities, modularity = detect_communities(G)

    print("\n[4/9] Centrality analysis...")
    centrality_df = compute_centrality(G, district_agg)

    print("\n[5/9] Granger causality on neighbour pairs...")
    granger_df, causal_digraph = granger_on_neighbors(G, merged)

    print("\n[6/9] Building knowledge graph...")
    kg_df = build_knowledge_graph(G, causal_digraph, district_agg, clusters)

    print("\n[7/9] Link prediction...")
    lp_df = link_prediction(G, causal_digraph)

    print("\n[8/9] Saving node/edge tables...")
    nodes_df = save_node_table(G, centrality_df, district_agg)

    print("\n[9/9] Generating visualisations...")
    plot_spatial_graph(G, nodes_df, geo)
    plot_communities(G, communities, geo)
    plot_centrality(G, nodes_df, geo)
    plot_knowledge_graph(kg_df, G, geo)

    print("\n" + "=" * 60)
    print("  Graph & Spatial Analysis Complete!")
    print("=" * 60)
    print(f"  Proximity graph:  {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"  Communities:      {len(communities)} zones (Q={modularity:.4f})")
    causal_n = causal_digraph.number_of_edges() if causal_digraph.number_of_nodes() else 0
    print(f"  Causal edges:     {causal_n} (Granger-significant)")
    print(f"  KG triples:       {len(kg_df):,}")
    print(f"  Figures saved to: {FIG_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
