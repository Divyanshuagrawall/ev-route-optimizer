# routing/astar.py

import math
import heapq
from config import BATTERY_CAPACITY_KWH
from routing.energy_model import compute_edge_energy


# ── Geometry helpers ──────────────────────────────────────────────────────────

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


# ── Edge data helper (handles OSMnx MultiDiGraph) ────────────────────────────

def _get_edge_data(G, u, v):
    """
    OSMnx returns a MultiDiGraph, so G[u][v] is a dict of {key: edge_data}.
    We pick the parallel edge with the lowest time_weight.
    """
    edges = G[u][v]
    return min(edges.values(), key=lambda d: d.get("time_weight", math.inf))


# ── Core A* search ────────────────────────────────────────────────────────────

def _astar_core(G, source, target, max_expansions=50000):
    """
    Heap-based A* on G using time_weight as edge cost.
    Returns the node path as a list, or None if no path exists.

    Closed set (visited) ensures each node is finalized at most once —
    once we pop a node from the heap with the best known g_score, we
    never need to revisit it. This is correct because time_weight >= 0
    (non-negative edge weights), so the first time a node is popped it
    is guaranteed to be via the optimal path.

    Open set entries: (f_score, tie_breaker, node)
    tie_breaker is a monotonic counter so heapq never tries to compare
    node IDs directly when f scores are equal.
    """
    g_score   = {source: 0.0}
    came_from = {}
    visited   = set()          # closed set
    counter   = 0

    h0 = heuristic(G, source, target)
    open_set = [(h0, counter, source)]

    expansions = 0

    while open_set:
        f_current, _, current = heapq.heappop(open_set)

        # Node already finalized via a cheaper path — skip stale entry
        if current in visited:
            continue

        visited.add(current)

        # Goal check after finalization
        if current == target:
            path = []
            node = target
            while node in came_from:
                path.append(node)
                node = came_from[node]
            path.append(source)
            path.reverse()
            return path

        expansions += 1
        if expansions > max_expansions:
            print(f"  ⚠️  A* hit expansion limit ({max_expansions}). No path returned.")
            return None

        for neighbor in G.successors(current):
            if neighbor in visited:
                continue                       # already finalized, skip

            edge_data   = _get_edge_data(G, current, neighbor)
            time_w      = edge_data.get("time_weight", 60.0)
            tentative_g = g_score[current] + time_w

            if tentative_g < g_score.get(neighbor, math.inf):
                came_from[neighbor] = current
                g_score[neighbor]   = tentative_g
                counter            += 1
                f = tentative_g + heuristic(G, neighbor, target)
                heapq.heappush(open_set, (f, counter, neighbor))

    return None


# ── Energy simulation (separate from search) ──────────────────────────────────

def _simulate_energy(G, path, start_soc):
    """
    Walk a path and compute total travel time, total energy consumed,
    and final SoC. Completely independent of how the path was found.

    Returns: (total_time_seconds, total_kwh, final_soc)
    """
    total_time = 0.0
    total_kwh  = 0.0
    soc        = start_soc

    for i in range(len(path) - 1):
        u    = path[i]
        v    = path[i + 1]
        data = _get_edge_data(G, u, v)

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

        if soc < 0.0:
            print("  ⚠️  SoC dropped too low along path.")
            break

    return total_time, total_kwh, soc


# ── Public interface ──────────────────────────────────────────────────────────

def astar(G, source, target, start_soc,
          charging_nodes=None, mandatory_waypoint=None,
          max_expansions=50000):

    # ── Mandatory waypoint: split into two sub-problems ──────────────────
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

    # ── Search ───────────────────────────────────────────────────────────
    path = _astar_core(G, source, target, max_expansions=max_expansions)

    if path is None:
        print(f"  ❌ No path found between {source} and {target}")
        return None, None, None, []

    # ── Evaluate ─────────────────────────────────────────────────────────
    total_time, total_kwh, _ = _simulate_energy(G, path, start_soc)

    return path, total_time, total_kwh, []