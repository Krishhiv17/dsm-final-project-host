"""Disease propagation graph endpoints."""
from fastapi import APIRouter, Query
from typing import Optional
from ..services.data_loader import all_data, df_to_records

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/nodes")
def nodes():
    d = all_data()
    return df_to_records(d["graph_nodes"])


@router.get("/edges")
def edges(limit: int = Query(2000, le=5000)):
    d = all_data()
    edges_df = d["graph_edges"]
    if edges_df is None:
        return []
    return df_to_records(edges_df.head(limit))


@router.get("/communities")
def communities():
    """Aggregated community summary (cross-state composition)."""
    d = all_data()
    nodes_df = d["graph_nodes"]
    if nodes_df is None or "community" not in nodes_df.columns:
        return []
    summary = (
        nodes_df.groupby("community")
        .agg(n_districts=("district_id", "count"),
             states=("state", lambda s: ", ".join(sorted(set(s)))),
             n_states=("state", "nunique"),
             avg_pm25=("pm25_mean", "mean"),
             avg_resp_rate=("resp_rate_mean", "mean"))
        .round(2).reset_index()
    )
    summary["cross_state"] = summary["n_states"] > 1
    return df_to_records(summary)


@router.get("/spatial-autocorr")
def spatial_autocorr():
    return df_to_records(all_data()["spatial_autocorr"])


@router.get("/knowledge")
def knowledge_graph(relationship: Optional[str] = None, limit: int = Query(500, le=5000)):
    d = all_data()
    kg = d["knowledge_graph"]
    nodes = d["graph_nodes"]
    if kg is None:
        return {"counts": [], "triples": []}
    counts = kg["relationship"].value_counts().reset_index()
    counts.columns = ["relationship", "count"]

    df = kg
    if relationship:
        df = df[df["relationship"] == relationship]

    # Sample across all relationship types so the table isn't dominated by one
    if relationship is None:
        per_rel = max(1, limit // max(1, df["relationship"].nunique()))
        df = (df.groupby("relationship", group_keys=False)
              .apply(lambda g: g.head(per_rel))
              .reset_index(drop=True))

    df = df.head(limit).copy()

    # Resolve district names for source/target IDs
    if nodes is not None and "district_id" in nodes.columns:
        name_map = dict(zip(nodes["district_id"], nodes["district_name"]))
        state_map = dict(zip(nodes["district_id"], nodes["state"]))
        df["subject"] = df["source_id"].map(name_map).fillna(df["source_id"].astype(str))
        df["object"]  = df["target_id"].map(name_map).fillna(df["target_id"].astype(str))
        df["subject_state"] = df["source_id"].map(state_map)
        df["object_state"]  = df["target_id"].map(state_map)

    return {
        "counts":  df_to_records(counts),
        "triples": df_to_records(df),
    }


@router.get("/link-prediction")
def link_prediction(top_n: int = Query(50, le=200)):
    d = all_data()
    lp = d["link_prediction"]
    if lp is None:
        return []
    return df_to_records(lp.head(top_n))


@router.get("/centrality-top")
def centrality_top(metric: str = "betweenness_centrality", top_n: int = 15):
    d = all_data()
    nodes_df = d["graph_nodes"]
    if nodes_df is None or metric not in nodes_df.columns:
        return []
    return df_to_records(nodes_df.nlargest(top_n, metric)[
        ["district_id", "district_name", "state", metric]
    ])
