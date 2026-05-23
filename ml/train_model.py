# ml/train_model.py

import pandas as pd
import pickle
import os
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from config import TRAINING_DATA_PATH, MODEL_SAVE_PATH


def train_speed_model():
    """Train XGBoost model to predict speed per edge."""

    # ── Load Data ─────────────────────────────────────────────────────────
    print("Loading training data...")
    df = pd.read_csv(TRAINING_DATA_PATH)

    features = ["road_type", "hour_of_day", "day_of_week",
                "maxspeed", "lanes", "length"]
    target   = "predicted_speed"

    X = df[features]
    y = df[target]

    # ── Train / Test Split ────────────────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # ── Train XGBoost ─────────────────────────────────────────────────────
    print("Training XGBoost model...")
    model = XGBRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train, y_train)

    # ── Evaluate ──────────────────────────────────────────────────────────
    y_pred = model.predict(X_test)
    mae    = mean_absolute_error(y_test, y_pred)
    r2     = r2_score(y_test, y_pred)
    print(f"MAE  : {mae:.2f} km/h")
    print(f"R²   : {r2:.4f}")

    # ── Save Model ────────────────────────────────────────────────────────
    os.makedirs("data", exist_ok=True)
    with open(MODEL_SAVE_PATH, "wb") as f:
        pickle.dump(model, f)
    print(f"Model saved to {MODEL_SAVE_PATH}")

    return model


if __name__ == "__main__":
    train_speed_model()