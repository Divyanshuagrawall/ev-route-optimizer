# routing/astar.py

import math
import networkx as nx
from config import MIN_SOC, BATTERY_CAPACITY_KWH
from routing.energy_model import compute_edge_energy


def haversine(G, u, v):
    u_data = G.nodes[u]
    v_data = G.nodes[v]
    lat1 = math.radians(u_data["y"])
    lon1 = math.radians(u_data["x"])
    lat2 = math.radians(v_data["y"])
    lon2 = math.radians(v_data["x"])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371 * 2 * math.asin(math.sqrt(a))


def heuristic(G, node, goal, max_speed=50.0):
    dist_km = haversine(G, node, goal)
    return (dist_km / max_speed) * 3600


def astar(G, source, target, start_soc,
          charging_nodes=None, mandatory_waypoint=None,
          max_expansions=50000):

    if mandatory_waypoint:
        path1, t1, e1, cs1 = astar(
            G, source, mandatory_waypoint, start_soc,
            charging_nodes=charging_nodes
        )
        if path1 is None:
            return None, None, None, []

        soc_after = start_soc - (e1 / BATTERY_CAPACITY_KWH)
        soc_after = max(soc_after, 0.80)

        path2, t2, e2, cs2 = astar(
            G, mandatory_waypoint, target, soc_after,
            charging_nodes=charging_nodes
        )
        if path2 is None:
            return None, None, None, []

        return path1 + path2[1:], t1 + t2, e1 + e2, [mandatory_waypoint] + cs2

    # ── Use NetworkX built-in A* on time_weight ────────────────────────
    try:
        def h(u, v):
            return heuristic(G, u, v)

        path = nx.astar_path(
            G, source, target,
            heuristic=h,
            weight="time_weight"
        )

        # Calculate total time and energy along path
        total_time = 0.0
        total_kwh  = 0.0
        soc        = start_soc

        for i in range(len(path) - 1):
            u = path[i]
            v = path[i + 1]
            data = G[u][v] if G.is_multigraph() == False else G[u][v][list(G[u][v].keys())[0]]

            length_km      = data.get("length_km", data.get("length", 50) / 1000)
            speed_kmh      = data.get("speed", 30.0)
            time_weight    = data.get("time_weight", (length_km / speed_kmh) * 3600)
            elevation_gain = data.get("elevation_gain", 0.0)
            elevation_loss = data.get("elevation_loss", 0.0)

            _, edge_kwh, edge_soc_delta = compute_edge_energy(
                length_km, speed_kmh, elevation_gain, elevation_loss
            )

            total_time += time_weight
            total_kwh  += edge_kwh
            soc        -= edge_soc_delta

            # SoC check — abort if drops too low
            if soc < 0.0:
                print("  ⚠️ SoC dropped too low along path.")
                break

        return path, total_time, total_kwh, []

    except nx.NetworkXNoPath:
        print(f"  ❌ No path found between {source} and {target}")
        return None, None, None, []
    except Exception as e:
        print(f"  ❌ A* error: {e}")
        return None, None, None, []