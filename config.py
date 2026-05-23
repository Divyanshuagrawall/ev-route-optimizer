# config.py

# ── EV Battery & Consumption (Tata Nexon EV) ──────────────────────────────
BATTERY_CAPACITY_KWH = 30.2        # Total usable battery (kWh)
BASE_CONSUMPTION_WH_PER_KM = 180   # Average Wh per km
SAFETY_BUFFER = 0.15               # 15% — never route below this SoC
MIN_SOC = 0.05                     # Hard cutoff — algorithm constraint (10%)

# ── Energy Model Coefficients ─────────────────────────────────────────────
GRADIENT_FACTOR = 0.05             # Extra Wh per meter of elevation gain
SPEED_FACTOR = 0.0005              # Wh penalty per (km/h)²
REGEN_FACTOR = 0.03                # Wh recovered per meter of elevation loss

# ── Speed Defaults by Road Type (km/h) ────────────────────────────────────
DEFAULT_SPEEDS = {
    "motorway": 80,
    "trunk": 60,
    "primary": 50,
    "secondary": 40,
    "tertiary": 30,
    "residential": 25,
    "unclassified": 20,
    "service": 15,
}
DEFAULT_SPEED_FALLBACK = 30        # If road type not in above dict

# ── Routing ───────────────────────────────────────────────────────────────
MAX_CHARGING_STOPS = 2             # Max stations to route through
REROUTE_TRIGGER_SOC = 0.20        # Re-evaluate if SoC drops below 20%

# ── Paths ─────────────────────────────────────────────────────────────────
JAIPUR_CENTER_LAT = 26.9124
JAIPUR_CENTER_LON = 75.7873
RADIUS_METERS = 5000
GRAPH_SAVE_PATH = "data/jaipur_graph.pkl"
MODEL_SAVE_PATH = "data/speed_model.pkl"
TRAINING_DATA_PATH = "data/training_data.csv"
CHARGING_STATIONS_PATH = "data/charging_stations.json"
OUTPUT_MAP_PATH = "output/route_map.html"