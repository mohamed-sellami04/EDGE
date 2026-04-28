import random
import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

random.seed(42)
np.random.seed(42)

# ======================================================
# MACHINE PROFILES
# ======================================================

MACHINE_PROFILES = {
    "motor_01": {
        "type_code": 1,
        "base_power": 9.5,
        "min_power": 8.0,
        "max_power": 12.0,
        "normal_temp_min": 32.0,
        "normal_temp_max": 45.0,
        "anomaly_power_min": 16.0,
        "anomaly_power_max": 21.0,
        "anomaly_temp_min": 62.0,
        "anomaly_temp_max": 75.0,
        "load_factor": 0.045
    },
    "fan_01": {
        "type_code": 2,
        "base_power": 6.5,
        "min_power": 5.0,
        "max_power": 9.0,
        "normal_temp_min": 28.0,
        "normal_temp_max": 40.0,
        "anomaly_power_min": 13.0,
        "anomaly_power_max": 18.0,
        "anomaly_temp_min": 55.0,
        "anomaly_temp_max": 70.0,
        "load_factor": 0.030
    },
    "pump_01": {
        "type_code": 3,
        "base_power": 11.0,
        "min_power": 8.0,
        "max_power": 14.0,
        "normal_temp_min": 30.0,
        "normal_temp_max": 45.0,
        "anomaly_power_min": 20.0,
        "anomaly_power_max": 28.0,
        "anomaly_temp_min": 58.0,
        "anomaly_temp_max": 75.0,
        "load_factor": 0.050
    }
}


# ======================================================
# DATASET GENERATION
# ======================================================

rows = []

for machine_id, profile in MACHINE_PROFILES.items():

    # ---------------- NORMAL DATA ----------------
    for _ in range(900):
        machine_type = profile["type_code"]
        status = 1

        production_rate = np.random.uniform(50, 95)

        load_power = profile["base_power"] + production_rate * profile["load_factor"]
        noise = np.random.uniform(-0.5, 0.5)

        power = load_power + noise
        power = max(profile["min_power"], min(power, profile["max_power"]))

        temperature = np.random.uniform(
            profile["normal_temp_min"],
            profile["normal_temp_max"]
        )

        current = power / 12.0
        anomaly = 0

        energy_next_30_min = power * 0.5

        rows.append([
            machine_type,
            status,
            power,
            temperature,
            current,
            production_rate,
            anomaly,
            energy_next_30_min
        ])

    # ---------------- OVERLOAD ANOMALY ----------------
    for _ in range(250):
        machine_type = profile["type_code"]
        status = 1

        production_rate = np.random.uniform(80, 100)

        power = np.random.uniform(
            profile["anomaly_power_min"],
            profile["anomaly_power_max"]
        )

        temperature = np.random.uniform(
            profile["normal_temp_max"],
            profile["anomaly_temp_max"]
        )

        current = power / 12.0
        anomaly = 1

        energy_next_30_min = power * 0.5 * 1.10

        rows.append([
            machine_type,
            status,
            power,
            temperature,
            current,
            production_rate,
            anomaly,
            energy_next_30_min
        ])

    # ---------------- OVERHEAT ANOMALY ----------------
    for _ in range(250):
        machine_type = profile["type_code"]
        status = 1

        production_rate = np.random.uniform(50, 90)

        power = np.random.uniform(
            profile["min_power"],
            profile["max_power"]
        )

        temperature = np.random.uniform(
            profile["anomaly_temp_min"],
            profile["anomaly_temp_max"]
        )

        current = power / 12.0
        anomaly = 1

        energy_next_30_min = power * 0.5 * 1.10

        rows.append([
            machine_type,
            status,
            power,
            temperature,
            current,
            production_rate,
            anomaly,
            energy_next_30_min
        ])

    # ---------------- IDLE WASTE ANOMALY ----------------
    for _ in range(250):
        machine_type = profile["type_code"]
        status = 1

        production_rate = 0

        power = np.random.uniform(
            profile["min_power"],
            profile["max_power"]
        )

        temperature = np.random.uniform(
            profile["normal_temp_min"],
            profile["normal_temp_max"]
        )

        current = power / 12.0
        anomaly = 1

        energy_next_30_min = power * 0.5

        rows.append([
            machine_type,
            status,
            power,
            temperature,
            current,
            production_rate,
            anomaly,
            energy_next_30_min
        ])

    # ---------------- OFF DATA ----------------
    for _ in range(150):
        machine_type = profile["type_code"]
        status = 0
        power = 0
        temperature = np.random.uniform(24, 30)
        current = 0
        production_rate = 0
        anomaly = 0
        energy_next_30_min = 0

        rows.append([
            machine_type,
            status,
            power,
            temperature,
            current,
            production_rate,
            anomaly,
            energy_next_30_min
        ])


columns = [
    "machine_type",
    "status",
    "power",
    "temperature",
    "current",
    "production_rate",
    "anomaly",
    "energy_next_30_min"
]

df = pd.DataFrame(rows, columns=columns)

X = df[[
    "machine_type",
    "status",
    "power",
    "temperature",
    "current",
    "production_rate"
]]

y_energy = df["energy_next_30_min"]

normal_data = df[df["anomaly"] == 0][[
    "machine_type",
    "status",
    "power",
    "temperature",
    "current",
    "production_rate"
]]

# ======================================================
# TRAIN ANOMALY MODEL
# ======================================================

anomaly_model = IsolationForest(
    n_estimators=200,
    contamination=0.16,
    random_state=42
)

anomaly_model.fit(normal_data)

# ======================================================
# TRAIN ENERGY PREDICTION MODEL
# ======================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y_energy,
    test_size=0.2,
    random_state=42
)

energy_model = RandomForestRegressor(
    n_estimators=200,
    random_state=42
)

energy_model.fit(X_train, y_train)

predictions = energy_model.predict(X_test)
mae = mean_absolute_error(y_test, predictions)

# ======================================================
# SAVE MODELS
# ======================================================

models = {
    "anomaly_model": anomaly_model,
    "energy_model": energy_model,
    "machine_type_map": {
        "motor_01": 1,
        "fan_01": 2,
        "pump_01": 3
    },
    "energy_model_mae": mae,
    "dataset_rows": len(df)
}

joblib.dump(models, "ai_models.pkl")

print("AI models trained successfully.")
print("Saved file: ai_models.pkl")
print(f"Training samples: {len(df)}")
print(f"Energy prediction MAE: {mae:.4f} Wh")