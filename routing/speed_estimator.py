# routing/speed_estimator.py

import datetime
from config import DEFAULT_SPEEDS, DEFAULT_SPEED_FALLBACK, HOURLY_CONGESTION, DAY_MULTIPLIER


def get_current_hour_and_day():
    now = datetime.datetime.now()
    return now.hour, now.weekday()   # weekday: 0=Monday, 6=Sunday


def estimate_edge_speeds(G, hour, day):
    """
    Compute a speed estimate for every edge in G based on:
      - road type base speed (from OSM maxspeed or DEFAULT_SPEEDS)
      - time-of-day congestion multiplier
      - day-of-week multiplier

    Returns a dict: {(u, v, k): speed_kmh}
    """
    congestion = HOURLY_CONGESTION[hour]
    day_mult   = DAY_MULTIPLIER[day]

    speeds = {}

    for u, v, k, data in G.edges(keys=True, data=True):

        # Base speed: prefer OSM maxspeed, fall back to road-type default
        maxspeed = data.get("maxspeed", None)
        if maxspeed is None:
            highway  = data.get("highway", "unclassified")
            if isinstance(highway, list):
                highway = highway[0]
            maxspeed = DEFAULT_SPEEDS.get(str(highway), DEFAULT_SPEED_FALLBACK)
        if isinstance(maxspeed, list):
            maxspeed = maxspeed[0]
        try:
            maxspeed = float(str(maxspeed).replace("mph", "").replace("km/h", "").strip())
        except (ValueError, AttributeError):
            maxspeed = DEFAULT_SPEED_FALLBACK

        speed = max(maxspeed * congestion * day_mult, 5.0)
        speeds[(u, v, k)] = speed

    return speeds