# main.py

from graph.map_loader import load_graph
from graph.graph_builder import add_edge_weights
from graph.charging_nodes import load_charging_stations, snap_stations_to_graph
from ml.data_generator import generate_training_data
from ml.train_model import train_speed_model
from ml.predictor import predict_speeds_for_graph, get_current_hour_and_day
from routing.router import plan_route, reroute
from visualization.map_renderer import render_route

import os
import datetime
import networkx as nx
import argparse


# ── Default Test Locations ─────────────────────────────────────────────────
LOCATIONS = {
    "badi_chaupar"  : (26.9230, 75.8268),
    "hawa_mahal"    : (26.9239, 75.8267),
    "albert_hall"   : (26.9118, 75.8195),
    "sindhi_camp"   : (26.9233, 75.8006),
    "jaipur_station": (26.9185, 75.7882),
    "ajmer_road"    : (26.9100, 75.7800),
    "chandpol_bazar": (26.9220, 75.8070),
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="EV Route & Charging Optimization System — Jaipur"
    )
    parser.add_argument(
        "--source", type=str, default="badi_chaupar",
        help=f"Source location. Options: {list(LOCATIONS.keys())}"
    )
    parser.add_argument(
        "--dest", type=str, default="ajmer_road",
        help=f"Destination location. Options: {list(LOCATIONS.keys())}"
    )
    parser.add_argument(
        "--soc", type=int, default=80,
        help="Starting battery percentage (0-100). e.g. --soc 15"
    )
    parser.add_argument(
        "--hour", type=int, default=None,
        help="Hour of day (0-23) for traffic simulation. Default: current hour"
    )
    parser.add_argument(
        "--reroute-node", type=int, default=None,
        help="Test rerouting from this node ID with updated SoC"
    )
    parser.add_argument(
        "--reroute-soc", type=int, default=None,
        help="Updated SoC for rerouting test"
    )
    return parser.parse_args()


def setup_pipeline(G):
    from config import TRAINING_DATA_PATH, MODEL_SAVE_PATH
    if not os.path.exists(TRAINING_DATA_PATH):
        print("\n── Generating ML training data...")
        generate_training_data(G)
    else:
        print("✅ Training data already exists.")
    if not os.path.exists(MODEL_SAVE_PATH):
        print("\n── Training XGBoost speed model...")
        train_speed_model()
    else:
        print("✅ Speed model already exists.")


def main():
    args = parse_args()

    # ── Resolve locations ──────────────────────────────────────────────
    if args.source not in LOCATIONS:
        print(f"❌ Unknown source '{args.source}'. Options: {list(LOCATIONS.keys())}")
        return
    if args.dest not in LOCATIONS:
        print(f"❌ Unknown dest '{args.dest}'. Options: {list(LOCATIONS.keys())}")
        return

    SOURCE_LAT, SOURCE_LON = LOCATIONS[args.source]
    DEST_LAT,   DEST_LON   = LOCATIONS[args.dest]
    START_SOC_PCT           = args.soc

    print("="*55)
    print("   🚗 EV Route & Charging Optimization System")
    print("   Jaipur City Centre | Tata Nexon EV")
    print("="*55)
    print(f"   Source : {args.source} ({SOURCE_LAT}, {SOURCE_LON})")
    print(f"   Dest   : {args.dest} ({DEST_LAT}, {DEST_LON})")
    print(f"   SoC    : {START_SOC_PCT}%")
    print("="*55)

    # ── Step 1: Load Graph ─────────────────────────────────────────────
    print("\n[1/6] Loading road network...")
    G = load_graph()

    # ── Step 2: Setup ML ───────────────────────────────────────────────
    print("\n[2/6] Setting up ML pipeline...")
    setup_pipeline(G)

    # ── Step 3: Predict Speeds & Add Weights ──────────────────────────
    print("\n[3/6] Predicting edge speeds (traffic-aware)...")
    hour, day = get_current_hour_and_day()
    if args.hour is not None:
        hour = args.hour
        print(f"      Using simulated hour: {hour}")
    else:
        print(f"      Current time: {datetime.datetime.now().strftime('%H:%M')} | Hour={hour} Day={day}")

    predicted_speeds = predict_speeds_for_graph(G, hour, day)
    G = add_edge_weights(G, predicted_speeds)

    # ── Step 4: Load Charging Stations ────────────────────────────────
    print("\n[4/6] Loading charging stations...")
    stations = load_charging_stations()
    snapped  = snap_stations_to_graph(G, stations)

    # ── Convert to DiGraph ─────────────────────────────────────────────
    print("      Converting to DiGraph for fast routing...")
    simple_G = nx.DiGraph()
    for u, v, data in G.edges(data=True):
        w = data.get("time_weight", 60.0)
        if not simple_G.has_edge(u, v) or simple_G[u][v]["time_weight"] > w:
            simple_G.add_edge(u, v, **data)
    for node, data in G.nodes(data=True):
        simple_G.nodes[node].update(data)
    G = simple_G
    print(f"      DiGraph ready: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # ── Step 5: Plan Route ────────────────────────────────────────────
    print(f"\n[5/6] Planning route with SoC={START_SOC_PCT}%...")
    result = plan_route(
        G,
        source_lat=SOURCE_LAT, source_lon=SOURCE_LON,
        dest_lat=DEST_LAT,     dest_lon=DEST_LON,
        start_soc_pct=START_SOC_PCT,
        snapped_stations=snapped,
        hour=hour, day=day
    )

    if result is None:
        print("\n❌ Could not find a valid route.")
        return

    result["all_stations"]  = snapped
    result["start_soc_pct"] = START_SOC_PCT

    # ── Optional: Test Rerouting ───────────────────────────────────────
    # ── Optional: Test Rerouting ───────────────────────────────────────
    if args.reroute_soc:
        print(f"\n🔄 Testing reroute at SoC={args.reroute_soc}%...")
        result = reroute(result, args.reroute_node, args.reroute_soc)
        if result:
            result["all_stations"]  = snapped
            result["start_soc_pct"] = args.reroute_soc

    # ── Step 6: Render Map ────────────────────────────────────────────
    print("\n[6/6] Rendering route map...")
    render_route(
        G, result,
        source_lat=SOURCE_LAT, source_lon=SOURCE_LON,
        dest_lat=DEST_LAT,     dest_lon=DEST_LON
    )

    print("\n" + "="*55)
    print("   ✅ DONE")
    print("="*55)
    print(f"   Route type  : {result['route_type']}")
    print(f"   Travel time : {result['total_time_min']} minutes")
    print(f"   Energy used : {result['total_kwh']} kWh")
    print(f"   SoC used    : {result['total_soc_used']}%")
    if result["charging_stops"]:
        print(f"   Charging at : {result['charging_stops'][0]['name']}")
    print(f"   Map saved   : output/route_map.html")
    print("="*55)


if __name__ == "__main__":
    main()