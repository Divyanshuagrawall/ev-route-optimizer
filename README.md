\# Adaptive EV Route \& Charging Optimization System



A smart EV navigation system built on real Jaipur road network data that finds optimal routes while respecting battery constraints. Uses A\* pathfinding with SoC state space, XGBoost speed prediction, and LPA\* incremental rerouting.



\## Problem Statement



Electric vehicle users face a critical tradeoff between travel time and battery consumption. Traditional navigation systems optimize only for ETA and do not handle EV-specific battery constraints during route planning.



\## What It Does



\- \*\*Direct route\*\* — if battery is sufficient (with 15% safety buffer), finds optimal path minimizing time and energy

\- \*\*Via-charging route\*\* — if battery is insufficient, finds optimal path through the nearest charging station

\- \*\*LPA\* rerouting\*\* — if SoC drops mid-journey, incrementally recomputes only the affected portion of the route

\- \*\*Traffic-aware\*\* — XGBoost predicts speed per road segment based on time of day and road type



\## Setup \& Installation



\### Prerequisites

\- Python 3.10+



\### Installation



```bash

git clone https://github.com/Divyanshuagrawall/ev-route-optimizer.git

cd ev-route-optimizer

python -m venv venv

venv\\Scripts\\activate

pip install -r requirements.txt

```



\### First Run

On first run, the system will automatically:

1\. Download the Jaipur road network from OpenStreetMap

2\. Generate ML training data from graph edges

3\. Train the XGBoost speed model



\## Usage



\### Web UI

```bash

uvicorn api:app --reload

```

Open `http://localhost:8000` in your browser.



\### CLI

```bash

python main.py --source badi\_chaupar --dest ajmer\_road --soc 80

```



\## Tech Stack



| Component | Technology |

|-----------|------------|

| Graph \& DSA | Python, OSMnx, NetworkX |

| ML | XGBoost, scikit-learn |

| Backend | FastAPI, Uvicorn |

| Frontend | HTML, CSS, Leaflet.js |

| Visualization | Folium |



\## License

MIT License

