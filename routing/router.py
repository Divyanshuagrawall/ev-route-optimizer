# routing/router.py

from config import (
    BATTERY_CAPACITY_KWH,
    SAFETY_BUFFER,
    MIN_SOC,
    MAX_CHARGING_STOPS
)
from routing.astar import astar
from routing.lpastar import LPAStar
from routing.energy_model import compute_path_energy


def get_nearest_node(G, lat, lon):
    """Snap a lat/lon coordinate to nearest graph node (works on any graph)."""
    best_node = None
    best_dist = float("inf")
    for node, data in G.nodes(data=True):
        nlat = data.get("y")
        nlon = data.get("x")
        if nlat is None or nlon is None:
            continue
        dist = (nlat - lat)**2 + (nlon - lon)**2
        if dist < best_dist:
            best_dist = dist
            best_node = node
    return best_node

def can_reach_direct(G, source, target, start_soc):
    """
    Check if vehicle can reach target directly with safety buffer.
    """
    from routing.astar import haversine
    dist_km    = haversine(G, source, target) * 1.3
    est_kwh    = (dist_km * 180) / 1000
    est_soc    = est_kwh / BATTERY_CAPACITY_KWH
    remaining  = start_soc - est_soc
    return remaining >= SAFETY_BUFFER


def find_best_charging_station(G, source, target, start_soc, snapped_stations):
    """
    Find the charging station that minimizes total path time.
    """
    from routing.astar import haversine

    best_station = None
    best_total   = float("inf")

    for station in snapped_stations:
        node = station["nearest_node"]

        # How much SoC needed to reach this station
        dist_to_station = haversine(G, source, node) * 1.3
        est_soc_needed  = (dist_to_station * 180 / 1000) / BATTERY_CAPACITY_KWH

        # Leave MIN_SOC buffer — check if reachable
        if start_soc - est_soc_needed < MIN_SOC * 0.5:
            continue

        # Total distance: source→station + station→target
        dist_to_target = haversine(G, node, target) * 1.3
        total_dist     = dist_to_station + dist_to_target

        if total_dist < best_total:
            best_total   = total_dist
            best_station = station

    # Last resort — pick closest station regardless
    if best_station is None:
        print("  Picking closest station as last resort...")
        best_station = min(
            snapped_stations,
            key=lambda s: haversine(G, source, s["nearest_node"])
        )

    return best_station


def plan_route(G, source_lat, source_lon,
               dest_lat, dest_lon,
               start_soc_pct, snapped_stations,
               hour=None, day=None):
    """
    Main routing function.

    Args:
        G               : road graph
        source_lat/lon  : start coordinates
        dest_lat/lon    : destination coordinates
        start_soc_pct   : battery % as integer (e.g. 80 for 80%)
        snapped_stations: list from charging_nodes.py
        hour/day        : for traffic-aware weights (optional)

    Returns:
        result dict with keys:
            path, total_time_min, total_kwh, total_soc_used,
            needs_charging, charging_stops, route_type
    """

    start_soc  = start_soc_pct / 100.0    # convert to fraction

    # Snap coordinates to graph nodes
    source = get_nearest_node(G, source_lat, source_lon)
    target = get_nearest_node(G, dest_lat, dest_lon)

    print(f"\n{'='*50}")
    print(f"Source node : {source}")
    print(f"Target node : {target}")
    print(f"Start SoC   : {start_soc_pct}%")
    print(f"{'='*50}\n")

    charging_node_ids = set(s["nearest_node"] for s in snapped_stations)

    # ── Decision: Direct or Via Charging ──────────────────────────────────
    if can_reach_direct(G, source, target, start_soc):
        print("✅ Battery sufficient — planning direct route...")
        route_type = "direct"

        path, total_time, total_kwh, _ = astar(
            G, source, target, start_soc,
            charging_nodes=charging_node_ids
        )
        charging_stops = []

    else:
        print("⚡ Battery insufficient — finding optimal charging stop...")
        route_type = "via_charging"

        best_station = find_best_charging_station(
            G, source, target, start_soc, snapped_stations
        )

        if best_station is None:
            print("❌ No reachable charging station found!")
            return None

        print(f"Best charging stop: {best_station['name']}")
        print(f"  Running A* source → station...")

        path, total_time, total_kwh, _ = astar(
            G, source, target, start_soc,
            charging_nodes=charging_node_ids,
            mandatory_waypoint=best_station["nearest_node"]
        )
        charging_stops = [best_station]

    if path is None:
        print("❌ No path found!")
        return None

    total_soc_used = (total_kwh / BATTERY_CAPACITY_KWH) * 100

    result = {
        "path"            : path,
        "total_time_min"  : round(total_time / 60, 1),
        "total_kwh"       : round(total_kwh, 3),
        "total_soc_used"  : round(total_soc_used, 1),
        "needs_charging"  : route_type == "via_charging",
        "charging_stops"  : charging_stops,
        "route_type"      : route_type,
        "source_node"     : source,
        "target_node"     : target,
        "lpa_instance"    : None    # filled if rerouting needed
    }

    # Store LPA* instance for potential rerouting
    # Initialize LPA* for rerouting using found path
    from routing.lpastar import LPAStar
    lpa = LPAStar(G, source, target, start_soc, charging_node_ids)
    lpa.g[source]   = 0.0
    lpa.rhs[source] = 0.0
    # Seed g-scores from A* result so LPA* doesn't recompute from scratch
    g_val = 0.0
    for i in range(len(path) - 1):
        u = path[i]
        v = path[i + 1]
        data   = G[u][v]
        time_w = data.get("time_weight", 60.0)
        g_val += time_w
        lpa.g[v]   = g_val
        lpa.rhs[v] = g_val
    result["lpa_instance"] = lpa

    print(f"\n── Route Summary ──────────────────────────")
    print(f"Type        : {route_type}")
    print(f"Nodes       : {len(path)}")
    print(f"Time        : {result['total_time_min']} min")
    print(f"Energy      : {result['total_kwh']} kWh")
    print(f"SoC used    : {result['total_soc_used']}%")
    if charging_stops:
        print(f"Charging at : {charging_stops[0]['name']}")
    print(f"───────────────────────────────────────────\n")

    return result


def reroute(result, new_node, new_soc_pct):
    """
    Trigger rerouting from a new position with updated SoC.
    If new_node is None, picks the middle of the current path.
    """
    path    = result["path"]
    new_soc = new_soc_pct / 100.0

    # If no node specified, pick mid-path node
    if new_node is None:
        mid_idx  = len(path) // 2
        new_node = path[mid_idx]
        print(f"  Auto-selected mid-path node: {new_node} (index {mid_idx}/{len(path)})")

    lpa = result.get("lpa_instance")
    if lpa is None:
        print("  No LPA* instance found — rerouting not available.")
        return result

    path, total_time, total_kwh = lpa.reroute(new_node, new_soc)

    if path is None:
        print("Rerouting failed.")
        return result

    result["path"]           = path
    result["total_time_min"] = round(total_time / 60, 1) if total_time else 0
    result["total_kwh"]      = round(total_kwh, 3) if total_kwh else 0
    result["route_type"]     = "rerouted"

    return result