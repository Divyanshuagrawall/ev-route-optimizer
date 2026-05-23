# graph/map_loader.py

import osmnx as ox
import pickle
import os
from config import GRAPH_SAVE_PATH

# Jaipur city centre coordinates (Hawa Mahal area)
JAIPUR_CENTER_LAT = 26.9124
JAIPUR_CENTER_LON = 75.7873
RADIUS_METERS = 3000  # 3 km radius

def download_and_save_graph():
    """Download Jaipur city centre road network and save to disk."""
    print("Downloading Jaipur city centre road network (5km radius)...")

    G = ox.graph_from_point(
        (JAIPUR_CENTER_LAT, JAIPUR_CENTER_LON),
        dist=RADIUS_METERS,
        network_type="drive"
    )

    os.makedirs("data", exist_ok=True)
    with open(GRAPH_SAVE_PATH, "wb") as f:
        pickle.dump(G, f)

    print(f"Graph saved to {GRAPH_SAVE_PATH}")
    print(f"Nodes: {len(G.nodes)}, Edges: {len(G.edges)}")
    return G


def load_graph():
    """Load graph from disk if exists, else download it."""
    if os.path.exists(GRAPH_SAVE_PATH):
        print("Loading saved graph from disk...")
        with open(GRAPH_SAVE_PATH, "rb") as f:
            G = pickle.load(f)
        print(f"Graph loaded. Nodes: {len(G.nodes)}, Edges: {len(G.edges)}")
        return G
    else:
        return download_and_save_graph()


if __name__ == "__main__":
    G = load_graph()