# graph/graph_builder.py

import numpy as np
from config import DEFAULT_SPEEDS, DEFAULT_SPEED_FALLBACK

def get_road_type(edge_data):
    """Extract road type string from edge data."""
    highway = edge_data.get("highway", "unclassified")
    if isinstance(highway, list):
        highway = highway[0]
    return str(highway)


def get_maxspeed(edge_data):
    """Extract max speed from edge data, fallback to road type default."""
    road_type = get_road_type(edge_data)
    maxspeed = edge_data.get("maxspeed", None)

    if maxspeed is None:
        return DEFAULT_SPEEDS.get(road_type, DEFAULT_SPEED_FALLBACK)

    if isinstance(maxspeed, list):
        maxspeed = maxspeed[0]

    try:
        return float(str(maxspeed).replace("mph", "").replace("km/h", "").strip())
    except:
        return DEFAULT_SPEEDS.get(road_type, DEFAULT_SPEED_FALLBACK)


def get_lanes(edge_data):
    """Extract number of lanes, default to 1."""
    lanes = edge_data.get("lanes", 1)
    if isinstance(lanes, list):
        lanes = lanes[0]
    try:
        return int(lanes)
    except:
        return 1


def add_edge_weights(G, predicted_speeds=None):
    """
    Add the following attributes to every edge:
    - road_type     : string
    - maxspeed      : float (km/h)
    - lanes         : int
    - speed         : float (km/h) — predicted or default
    - time_weight   : float (seconds) — used by Dijkstra
    - length_km     : float (km)
    - elevation_gain: float (meters, 0 if no elevation data)
    - elevation_loss: float (meters, 0 if no elevation data)
    """
    for u, v, k, data in G.edges(keys=True, data=True):

        road_type = get_road_type(data)
        maxspeed  = get_maxspeed(data)
        lanes     = get_lanes(data)
        length_m  = data.get("length", 50)        # meters, default 50m
        length_km = length_m / 1000.0

        # Speed — use ML prediction if available, else maxspeed
        if predicted_speeds and (u, v, k) in predicted_speeds:
            speed = predicted_speeds[(u, v, k)]
        else:
            speed = maxspeed

        speed = max(speed, 5.0)                   # never below 5 km/h

        # Time weight in seconds
        time_weight = (length_km / speed) * 3600

        # Elevation gain/loss from grade
        grade = data.get("grade", 0.0)
        if grade is None:
            grade = 0.0
        elevation_change = grade * length_m       # meters
        elevation_gain = max(elevation_change, 0)
        elevation_loss = max(-elevation_change, 0)

        # Write back to edge
        G[u][v][k]["road_type"]      = road_type
        G[u][v][k]["maxspeed"]       = maxspeed
        G[u][v][k]["lanes"]          = lanes
        G[u][v][k]["speed"]          = speed
        G[u][v][k]["time_weight"]    = time_weight
        G[u][v][k]["length_km"]      = length_km
        G[u][v][k]["elevation_gain"] = elevation_gain
        G[u][v][k]["elevation_loss"] = elevation_loss

    print(f"Edge weights added to {G.number_of_edges()} edges.")
    return G


if __name__ == "__main__":
    from graph.map_loader import load_graph
    G = load_graph()
    G = add_edge_weights(G)
    print("Sample edge data:")
    sample = list(G.edges(data=True))[0]
    print(sample)