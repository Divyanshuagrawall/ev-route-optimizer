# ml/data_generator.py

import pandas as pd
import numpy as np
import os
from config import TRAINING_DATA_PATH, DEFAULT_SPEEDS, DEFAULT_SPEED_FALLBACK

# Congestion multipliers by hour (based on Indian urban traffic studies)
# 1.0 = free flow, 0.4 = heavy congestion
HOURLY_CONGESTION = {
    0: 0.95, 1: 0.95, 2: 0.95, 3: 0.95, 4: 0.95,
    5: 0.90, 6: 0.75, 7: 0.55, 8: 0.45, 9: 0.55,
    10: 0.70, 11: 0.75, 12: 0.70, 13: 0.70, 14: 0.72,
    15: 0.70, 16: 0.60, 17: 0.45, 18: 0.40, 19: 0.50,
    20: 0.65, 21: 0.75, 22: 0.85, 23: 0.90
}

# Day of week multiplier (0=Monday, 6=Sunday)
DAY_MULTIPLIER = {
    0: 0.90, 1: 0.90, 2: 0.90, 3: 0.90, 4: 0.85,
    5: 0.75, 6: 0.95
}


def generate_training_data(G):
    """
    Generate training data from OSMnx graph edges.
    Each row = one edge at one hour of one day type.
    """
    print("Generating training data from graph edges...")
    rows = []

    for u, v, k, data in G.edges(keys=True, data=True):

        # Road type
        highway = data.get("highway", "unclassified")
        if isinstance(highway, list):
            highway = highway[0]
        road_type = str(highway)

        # Max speed
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

        # Encode road type as integer
        road_type_map = {
            "motorway": 0, "trunk": 1, "primary": 2,
            "secondary": 3, "tertiary": 4, "residential": 5,
            "unclassified": 6, "service": 7
        }
        road_type_int = road_type_map.get(road_type, 6)

        # Generate one sample per hour per day type (weekday + weekend)
        for hour in range(24):
            for day in range(7):
                congestion   = HOURLY_CONGESTION[hour]
                day_mult     = DAY_MULTIPLIER[day]
                noise        = np.random.uniform(0.95, 1.05)  # ±5% noise

                predicted_speed = maxspeed * congestion * day_mult * noise
                predicted_speed = max(predicted_speed, 5.0)

                rows.append({
                    "road_type"       : road_type_int,
                    "hour_of_day"     : hour,
                    "day_of_week"     : day,
                    "maxspeed"        : maxspeed,
                    "lanes"           : lanes,
                    "length"          : length,
                    "predicted_speed" : predicted_speed
                })

    df = pd.DataFrame(rows)
    os.makedirs("data", exist_ok=True)
    df.to_csv(TRAINING_DATA_PATH, index=False)
    print(f"Training data saved: {len(df)} rows → {TRAINING_DATA_PATH}")
    return df


if __name__ == "__main__":
    from graph.map_loader import load_graph
    G = load_graph()
    df = generate_training_data(G)
    print(df.head())
    print(df.describe())