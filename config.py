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
    "motorway"     : 80,
    "trunk"        : 60,
    "primary"      : 50,
    "secondary"    : 40,
    "tertiary"     : 30,
    "residential"  : 25,
    "unclassified" : 20,
    "service"      : 15,
}
DEFAULT_SPEED_FALLBACK = 30        # If road type not in above dict

# ── Congestion multipliers by hour (Indian urban traffic patterns) ─────────
# 1.0 = free flow, 0.4 = heavy congestion
HOURLY_CONGESTION = {
     0: 0.95,  1: 0.95,  2: 0.95,  3: 0.95,  4: 0.95,
     5: 0.90,  6: 0.75,  7: 0.55,  8: 0.45,  9: 0.55,
    10: 0.70, 11: 0.75, 12: 0.70, 13: 0.70, 14: 0.72,
    15: 0.70, 16: 0.60, 17: 0.45, 18: 0.40, 19: 0.50,
    20: 0.65, 21: 0.75, 22: 0.85, 23: 0.90,
}

# Day of week multiplier (0=Monday, 6=Sunday)
DAY_MULTIPLIER = {
    0: 0.90, 1: 0.90, 2: 0.90, 3: 0.90, 4: 0.85,
    5: 0.75, 6: 0.95,
}

# ── Routing ───────────────────────────────────────────────────────────────
MAX_CHARGING_STOPS = 2             # Max stations to route through
REROUTE_TRIGGER_SOC = 0.20        # Re-evaluate if SoC drops below 20%

# ── Paths ─────────────────────────────────────────────────────────────────
JAIPUR_CENTER_LAT = 26.9124
JAIPUR_CENTER_LON = 75.7873
RADIUS_METERS = 5000
GRAPH_SAVE_PATH        = "data/jaipur_graph.pkl"
CHARGING_STATIONS_PATH = "data/charging_stations.json"
OUTPUT_MAP_PATH        = "output/route_map.html"