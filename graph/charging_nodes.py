# graph/charging_nodes.py

import json
import osmnx as ox
from config import CHARGING_STATIONS_PATH

def load_charging_stations():
    """Load charging stations from JSON file."""
    with open(CHARGING_STATIONS_PATH, "r") as f:
        stations = json.load(f)
    print(f"Loaded {len(stations)} charging stations.")
    return stations


def snap_stations_to_graph(G, stations):
    """
    Find the nearest graph node for each charging station.
    Returns list of dicts with added field: nearest_node
    """
    snapped = []

    for station in stations:
        nearest_node = ox.distance.nearest_nodes(
            G,
            X=station["lon"],   # longitude = X
            Y=station["lat"]    # latitude  = Y
        )

        snapped.append({
            "name"         : station["name"],
            "lat"          : station["lat"],
            "lon"          : station["lon"],
            "charger_type" : station["charger_type"],
            "rate_kw"      : station["rate_kw"],
            "nearest_node" : nearest_node
        })

        print(f"  {station['name']} → node {nearest_node}")

    return snapped


def get_charging_node_ids(snapped_stations):
    """Return just the set of node IDs that are charging stations."""
    return set(s["nearest_node"] for s in snapped_stations)


def get_station_by_node(snapped_stations, node_id):
    """Look up station info by its graph node ID."""
    for s in snapped_stations:
        if s["nearest_node"] == node_id:
            return s
    return None


if __name__ == "__main__":
    from graph.map_loader import load_graph
    from graph.graph_builder import add_edge_weights

    G = load_graph()
    G = add_edge_weights(G)

    stations  = load_charging_stations()
    snapped   = snap_stations_to_graph(G, stations)

    print("\nSnapped stations:")
    for s in snapped:
        print(f"  {s['name']} → node {s['nearest_node']}")