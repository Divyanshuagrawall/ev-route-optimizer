# api.py

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import networkx as nx
import math
import os

from graph.map_loader import load_graph
from graph.graph_builder import add_edge_weights
from graph.charging_nodes import load_charging_stations, snap_stations_to_graph
from routing.speed_estimator import estimate_edge_speeds, get_current_hour_and_day
from routing.router import plan_route, reroute

app = FastAPI(title="EV Route Optimizer")

# ── Global state ───────────────────────────────────────────────────────────
G            = None
snapped      = None
lpa_instance = None   # LPA* instance for the current active route

LOCATIONS = {
    "badi_chaupar"  : (26.9230, 75.8268),
    "hawa_mahal"    : (26.9239, 75.8267),
    "albert_hall"   : (26.9118, 75.8195),
    "sindhi_camp"   : (26.9233, 75.8006),
    "jaipur_station": (26.9185, 75.7882),
    "ajmer_road"    : (26.9100, 75.7800),
    "chandpol_bazar": (26.9220, 75.8070),
}


@app.on_event("startup")
async def startup():
    global G, snapped

    print("Loading graph...")
    raw_G = load_graph()

    hour, day = get_current_hour_and_day()
    estimated = estimate_edge_speeds(raw_G, hour, day)
    raw_G     = add_edge_weights(raw_G, estimated)

    stations = load_charging_stations()
    snapped  = snap_stations_to_graph(raw_G, stations)

    # Convert to DiGraph
    simple_G = nx.DiGraph()
    for u, v, data in raw_G.edges(data=True):
        w = data.get("time_weight", 60.0)
        if not simple_G.has_edge(u, v) or simple_G[u][v]["time_weight"] > w:
            simple_G.add_edge(u, v, **data)
    for node, data in raw_G.nodes(data=True):
        simple_G.nodes[node].update(data)
    G = simple_G

    print(f"Ready! Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")


# ── Request models ─────────────────────────────────────────────────────────
class RouteRequest(BaseModel):
    source     : str
    destination: str
    soc        : int
    hour       : int = None

class IncidentRequest(BaseModel):
    lat: float
    lon: float


# ── Helpers ────────────────────────────────────────────────────────────────
def _build_response(result, source_name, dest_name):
    """Convert a route result dict into the JSON shape the frontend expects."""
    path_coords = []
    for node in result["path"]:
        if node in G.nodes:
            d = G.nodes[node]
            if d.get("y") and d.get("x"):
                path_coords.append([d["y"], d["x"]])

    charging_stops = [
        {"name": s["name"], "lat": s["lat"], "lon": s["lon"],
         "charger_type": s["charger_type"], "rate_kw": s["rate_kw"]}
        for s in result["charging_stops"]
    ]
    all_stations = [
        {"name": s["name"], "lat": s["lat"], "lon": s["lon"],
         "charger_type": s["charger_type"], "rate_kw": s["rate_kw"]}
        for s in snapped
    ]
    src_lat, src_lon = LOCATIONS[source_name]
    dst_lat, dst_lon = LOCATIONS[dest_name]

    return {
        "route_type"    : result["route_type"],
        "total_time_min": result["total_time_min"],
        "total_kwh"     : result["total_kwh"],
        "total_soc_used": result["total_soc_used"],
        "path_coords"   : path_coords,
        "charging_stops": charging_stops,
        "all_stations"  : all_stations,
        "source"        : {"lat": src_lat, "lon": src_lon, "name": source_name},
        "destination"   : {"lat": dst_lat, "lon": dst_lon, "name": dest_name},
    }

def _find_nearest_edge(lat, lon):
    """
    Find the nearest edge in G to a clicked lat/lon.
    Returns (u, v) of the closest edge.
    """
    best_u, best_v = None, None
    best_dist      = math.inf

    for u, v in G.edges():
        u_data = G.nodes[u]
        v_data = G.nodes[v]
        # Midpoint of edge
        mid_lat = (u_data.get("y", 0) + v_data.get("y", 0)) / 2
        mid_lon = (u_data.get("x", 0) + v_data.get("x", 0)) / 2
        dist    = (mid_lat - lat) ** 2 + (mid_lon - lon) ** 2
        if dist < best_dist:
            best_dist = dist
            best_u, best_v = u, v

    return best_u, best_v


# ── Endpoints ──────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()

@app.get("/locations")
async def get_locations():
    return {"locations": list(LOCATIONS.keys())}


@app.post("/route")
async def get_route(req: RouteRequest):
    global lpa_instance

    if req.source not in LOCATIONS:
        return JSONResponse({"error": f"Unknown source: {req.source}"}, status_code=400)
    if req.destination not in LOCATIONS:
        return JSONResponse({"error": f"Unknown destination: {req.destination}"}, status_code=400)

    source_lat, source_lon = LOCATIONS[req.source]
    dest_lat,   dest_lon   = LOCATIONS[req.destination]

    hour, day = get_current_hour_and_day()
    if req.hour is not None:
        hour = req.hour

    result = plan_route(
        G,
        source_lat=source_lat, source_lon=source_lon,
        dest_lat=dest_lat,     dest_lon=dest_lon,
        start_soc_pct=req.soc,
        snapped_stations=snapped,
        hour=hour, day=day
    )

    if result is None:
        return JSONResponse({"error": "No route found"}, status_code=404)

    # Store LPA* instance globally for incident rerouting
    lpa_instance = result.get("lpa_instance")

    return _build_response(result, req.source, req.destination)


@app.post("/incident")
async def report_incident(req: IncidentRequest):
    """
    Called when user clicks the map to report a road closure or accident.
    Finds the nearest edge, closes it in LPA*, returns rerouted path.
    """
    global lpa_instance

    if lpa_instance is None:
        return JSONResponse(
            {"error": "No active route. Plan a route first."},
            status_code=400
        )

    # Find nearest edge to clicked point
    u, v = _find_nearest_edge(req.lat, req.lon)
    if u is None:
        return JSONResponse({"error": "Could not find nearby road."}, status_code=400)

    print(f"Incident reported at ({req.lat:.4f}, {req.lon:.4f}) → closing edge {u}→{v}")

    # LPA* incremental update — only recomputes affected nodes
    path, total_time, total_kwh = lpa_instance.close_edge(u, v)

    if path is None:
        return JSONResponse(
            {"error": "No alternative route found after road closure."},
            status_code=404
        )

    # Build path coordinates
    path_coords = []
    for node in path:
        if node in G.nodes:
            d = G.nodes[node]
            if d.get("y") and d.get("x"):
                path_coords.append([d["y"], d["x"]])

    total_soc_used = round((total_kwh / 30.2) * 100, 1) if total_kwh else 0

    # Mark the closed edge on map
    u_data = G.nodes[u]
    v_data = G.nodes[v]

    return {
        "route_type"    : "rerouted",
        "total_time_min": round(total_time / 60, 1) if total_time and total_time != math.inf else 0,
        "total_kwh"     : round(total_kwh, 3) if total_kwh else 0,
        "total_soc_used": total_soc_used,
        "path_coords"   : path_coords,
        "closed_edge"   : {
            "from": [u_data.get("y"), u_data.get("x")],
            "to"  : [v_data.get("y"), v_data.get("x")],
        }
    }