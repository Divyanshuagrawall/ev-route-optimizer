# Adaptive EV Route Optimizer

A full-stack EV navigation system built on a real **OpenStreetMap road network** (Jaipur city centre) that finds optimal routes while respecting battery constraints. Uses a custom **A\*** implementation for route planning and **LPA\*** for real-time incremental rerouting, with battery-aware navigation under changing road conditions.

## What It Does

- **Direct route** — if battery is sufficient (with 15% safety buffer), finds the optimal path minimizing time and energy using A\*
- **Via-charging route** — if battery is insufficient, routes through the nearest reachable charging station
- **LPA\* rerouting** — when a road closure or accident is reported via the map UI, LPA\* incrementally recomputes only the affected portion of the route (not a full re-search)
- **Time-dependent traffic modeling** — edge travel speeds are estimated using hourly congestion multipliers and day-of-week factors based on Indian urban traffic patterns
- **Physics-based energy model** — edge travel cost accounts for base consumption, speed penalty, elevation gain, and regenerative braking on downhill segments

## Architecture

```
OSMnx road network (Jaipur)
        │
        ▼
 graph_builder.py  ←─  speed_estimator.py  (time-dependent traffic)
        │
        ▼
   router.py
   ├── astar.py        (custom heap-based A* from scratch)
   ├── lpastar.py      (LPA* incremental rerouting)
   └── energy_model.py (physics-based EV energy model)
        │
        ▼
   api.py (FastAPI)  ←─  /route, /incident endpoints
        │
        ▼
   static/index.html   (Leaflet.js interactive map)
```

## Tech Stack

| Component | Technology |
|---|---|
| Road Network | OSMnx (real OpenStreetMap data) |
| Pathfinding | Custom A\* + LPA\* (built from scratch) |
| Energy Model | Physics-based (base consumption + gradient + speed + regen) |
| Traffic Model | Time-dependent congestion multipliers |
| Backend | FastAPI, Uvicorn |
| Frontend | HTML, CSS, Leaflet.js |
| Graph DSA | Python, NetworkX |

## Key Algorithms

### A\* (routing/astar.py)
Custom heap-based implementation using `time_weight` as edge cost and haversine distance as the admissible heuristic. Closed set guarantees each node is finalized at most once. Mandatory waypoint support splits the problem into two sub-searches for via-charging routes.

### LPA\* (routing/lpastar.py)
Lifelong Planning A\* maintains `g` and `rhs` values per node. When an edge is closed (road incident reported on map), only the affected nodes are updated and re-expanded — not the full graph. This makes rerouting significantly faster than rerunning A\* from scratch.

### Physics-based Energy Model (routing/energy_model.py)
```
energy (Wh) = base_consumption × distance
            + gradient_factor × elevation_gain
            + speed_factor × speed²
            - regen_factor × elevation_loss
```
Calibrated for Tata Nexon EV (30.2 kWh battery, ~180 Wh/km base consumption).

### Time-dependent Traffic (routing/speed_estimator.py)
Edge speeds are computed as:
```
speed = base_road_speed × hourly_congestion[hour] × day_multiplier[weekday]
```
Congestion factors modeled on Indian urban traffic (peak hours 8–9 AM, 5–7 PM).

## Setup & Installation

### Prerequisites
- Python 3.10+

### Installation

```bash
git clone https://github.com/Divyanshuagrawall/ev-route-optimizer.git
cd ev-route-optimizer
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt
```

### First Run
On first run, the system will automatically download the Jaipur road network from OpenStreetMap and cache it to `data/jaipur_graph.pkl`. This takes ~30 seconds once.

## Usage

### Web UI
```bash
uvicorn api:app --reload
```
Open `http://localhost:8000` in your browser.

1. Select source and destination from the dropdown
2. Set your current battery (SoC %)
3. Click **Find Optimal Route** — the route draws on the map with travel time, energy used, and SoC consumed
4. Click **Report Road Closure / Accident**, then click anywhere on the map to trigger LPA\* rerouting around that edge

### CLI
```bash
python main.py --source badi_chaupar --dest ajmer_road --soc 80
python main.py --source sindhi_camp --dest albert_hall --soc 15   # triggers charging stop
python main.py --source badi_chaupar --dest ajmer_road --soc 80 --hour 8  # simulate morning peak
```

## Project Structure

```
ev-route-optimizer/
├── api.py                  # FastAPI backend — /route and /incident endpoints
├── config.py               # EV parameters, speed defaults, congestion tables
├── main.py                 # CLI entry point
├── graph/
│   ├── map_loader.py       # OSMnx download + caching
│   ├── graph_builder.py    # Edge weight computation
│   └── charging_nodes.py   # Station loading + snapping to graph nodes
├── routing/
│   ├── astar.py            # Custom A* implementation
│   ├── lpastar.py          # LPA* incremental rerouter
│   ├── energy_model.py     # Physics-based energy per edge
│   ├── speed_estimator.py  # Time-dependent speed estimation
│   └── router.py           # High-level routing logic
├── static/
│   └── index.html          # Leaflet.js web UI
└── data/
    └── charging_stations.json
```

## License
MIT License