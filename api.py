# api.py

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import networkx as nx
import os

from graph.map_loader import load_graph
from graph.graph_builder import add_edge_weights
from graph.charging_nodes import load_charging_stations, snap_stations_to_graph
from ml.data_generator import generate_training_data
from ml.train_model import train_speed_model
from ml.predictor import predict_speeds_for_graph, get_current_hour_and_day
from routing.router import plan_route, reroute

app = FastAPI(title="EV Route Optimizer")

# ── Startup: load everything once ─────────────────────────────────────────
G        = None
snapped  = None

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

    from config import TRAINING_DATA_PATH, MODEL_SAVE_PATH
    if not os.path.exists(TRAINING_DATA_PATH):
        generate_training_data(raw_G)
    if not os.path.exists(MODEL_SAVE_PATH):
        train_speed_model()

    hour, day = get_current_hour_and_day()
    predicted  = predict_speeds_for_graph(raw_G, hour, day)
    raw_G      = add_edge_weights(raw_G, predicted)

    # Snap stations before DiGraph conversion
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


# ── Request Model ──────────────────────────────────────────────────────────
class RouteRequest(BaseModel):
    source: str
    destination: str
    soc: int
    hour: int = None


# ── Routes ─────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()


@app.get("/locations")
async def get_locations():
    return {"locations": list(LOCATIONS.keys())}


@app.post("/route")
async def get_route(req: RouteRequest):
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

    # Build path coordinates for frontend
    path_coords = []
    for node in result["path"]:
        if node in G.nodes:
            data = G.nodes[node]
            lat  = data.get("y")
            lon  = data.get("x")
            if lat and lon:
                path_coords.append([lat, lon])

    # Build charging stops for frontend
    charging_stops = []
    for s in result["charging_stops"]:
        charging_stops.append({
            "name"        : s["name"],
            "lat"         : s["lat"],
            "lon"         : s["lon"],
            "charger_type": s["charger_type"],
            "rate_kw"     : s["rate_kw"]
        })

    # All stations for map display
    all_stations = []
    for s in snapped:
        all_stations.append({
            "name"        : s["name"],
            "lat"         : s["lat"],
            "lon"         : s["lon"],
            "charger_type": s["charger_type"],
            "rate_kw"     : s["rate_kw"]
        })

    return {
        "route_type"     : result["route_type"],
        "total_time_min" : result["total_time_min"],
        "total_kwh"      : result["total_kwh"],
        "total_soc_used" : result["total_soc_used"],
        "path_coords"    : path_coords,
        "charging_stops" : charging_stops,
        "all_stations"   : all_stations,
        "source"         : {"lat": source_lat, "lon": source_lon, "name": req.source},
        "destination"    : {"lat": dest_lat,   "lon": dest_lon,   "name": req.destination},
    }