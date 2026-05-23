# ml/predictor.py

import pickle
import pandas as pd
import datetime
from config import MODEL_SAVE_PATH, DEFAULT_SPEEDS, DEFAULT_SPEED_FALLBACK


def load_model():
    """Load trained XGBoost model from disk."""
    with open(MODEL_SAVE_PATH, "rb") as f:
        model = pickle.load(f)
    print("Speed prediction model loaded.")
    return model


def get_current_hour_and_day():
    """Return current hour and day of week."""
    now = datetime.datetime.now()
    return now.hour, now.weekday()   # hour: 0-23, day: 0=Monday


def predict_speeds_for_graph(G, hour=None, day=None):
    """
    Predict speed for every edge in graph at given hour and day.
    Returns dict: {(u, v, k): predicted_speed}
    """
    model = load_model()

    if hour is None or day is None:
        hour, day = get_current_hour_and_day()

    print(f"Predicting speeds for hour={hour}, day={day}...")

    road_type_map = {
        "motorway": 0, "trunk": 1, "primary": 2,
        "secondary": 3, "tertiary": 4, "residential": 5,
        "unclassified": 6, "service": 7
    }

    rows   = []
    keys   = []

    for u, v, k, data in G.edges(keys=True, data=True):

        # Road type
        highway = data.get("highway", "unclassified")
        if isinstance(highway, list):
            highway = highway[0]
        road_type = str(highway)
        road_type_int = road_type_map.get(road_type, 6)

        # Maxspeed
        maxspeed = data.get("maxspeed", None)
        if maxspeed is None:
            maxspeed = DEFAULT_SPEEDS.get(road_type, DEFAULT_SPEED_FALLBACK)
        if isinstance(maxspeed, list):
            maxspeed = maxspeed[0]
        try:
            maxspeed = float(str(maxspeed).replace("mph","").replace("km/h","").strip())
        except:
            maxspeed = DEFAULT_SPEEDS.get(road_type, DEFAULT_SPEED_FALLBACK)

        # Lanes
        lanes = data.get("lanes", 1)
        if isinstance(lanes, list):
            lanes = lanes[0]
        try:
            lanes = int(lanes)
        except:
            lanes = 1

        length = data.get("length", 50)

        rows.append({
            "road_type"  : road_type_int,
            "hour_of_day": hour,
            "day_of_week": day,
            "maxspeed"   : maxspeed,
            "lanes"      : lanes,
            "length"     : length
        })
        keys.append((u, v, k))

    # Batch predict
    df      = pd.DataFrame(rows)
    speeds  = model.predict(df)

    predicted = {}
    for i, key in enumerate(keys):
        predicted[key] = max(float(speeds[i]), 5.0)

    print(f"Speeds predicted for {len(predicted)} edges.")
    return predicted


if __name__ == "__main__":
    from graph.map_loader import load_graph
    G = load_graph()
    hour, day = get_current_hour_and_day()
    speeds = predict_speeds_for_graph(G, hour, day)
    sample = list(speeds.items())[:3]
    print("Sample predictions:", sample)