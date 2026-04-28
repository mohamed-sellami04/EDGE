from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import sqlite3
import random
import time
import os

try:
    import joblib
    import pandas as pd
except ImportError:
    joblib = None
    pd = None


# ======================================================
# APP CONFIG
# ======================================================

app = FastAPI(title="EcoTwin AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "ecotwin.db"
MODEL_FILE = "ai_models.pkl"

ELECTRICITY_PRICE_TND_PER_KWH = 0.30
CO2_FACTOR_KG_PER_KWH = 0.45

NORMAL_LIMITS = {
    "motor_01": {"power": 12.0, "temperature": 60.0},
    "fan_01": {"power": 9.0, "temperature": 50.0},
    "pump_01": {"power": 14.0, "temperature": 55.0},
}

DEFAULT_MACHINE_TYPE_MAP = {
    "motor_01": 1,
    "fan_01": 2,
    "pump_01": 3,
}

AI_MODELS = {
    "loaded": False,
    "data": None,
    "message": "AI model not loaded yet"
}


# ======================================================
# REQUEST MODELS
# ======================================================

class SensorData(BaseModel):
    machineId: str
    status: str
    voltage: float
    current: float
    power: float
    temperature: float
    productionRate: float = 0


class CommandRequest(BaseModel):
    machineId: str
    targetStatus: str


# ======================================================
# DATABASE
# ======================================================

def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS machines (
        machine_id TEXT PRIMARY KEY,
        name TEXT,
        type TEXT,
        status TEXT,
        target_status TEXT,
        latest_voltage REAL,
        latest_current REAL,
        latest_power REAL,
        latest_temperature REAL,
        production_rate REAL,
        total_energy_wh REAL,
        ai_status TEXT,
        recommendation TEXT,
        last_update REAL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_id TEXT,
        status TEXT,
        voltage REAL,
        current REAL,
        power REAL,
        temperature REAL,
        production_rate REAL,
        ai_status TEXT,
        recommendation TEXT,
        created_at TEXT
    )
    """)

    default_machines = [
        ("motor_01", "Motor 01", "Motor"),
        ("fan_01", "Cooling Fan 01", "Fan"),
        ("pump_01", "Pump 01", "Pump")
    ]

    for machine_id, name, machine_type in default_machines:
        cursor.execute(
            "SELECT machine_id FROM machines WHERE machine_id = ?",
            (machine_id,)
        )
        exists = cursor.fetchone()

        if not exists:
            cursor.execute("""
            INSERT INTO machines (
                machine_id, name, type, status, target_status,
                latest_voltage, latest_current, latest_power,
                latest_temperature, production_rate,
                total_energy_wh, ai_status, recommendation, last_update
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                machine_id,
                name,
                machine_type,
                "OFF",
                "OFF",
                0,
                0,
                0,
                25,
                0,
                0,
                "Normal",
                "No action needed",
                time.time()
            ))

    conn.commit()
    conn.close()


# ======================================================
# AI MODEL LOADING
# ======================================================

def load_ai_models():
    global AI_MODELS

    if joblib is None or pd is None:
        AI_MODELS = {
            "loaded": False,
            "data": None,
            "message": "joblib or pandas not installed. Using fallback rule-based AI."
        }
        return

    model_path = os.path.join(os.path.dirname(__file__), MODEL_FILE)

    if not os.path.exists(model_path):
        AI_MODELS = {
            "loaded": False,
            "data": None,
            "message": "ai_models.pkl not found. Using fallback rule-based AI."
        }
        return

    try:
        models = joblib.load(model_path)

        required_keys = ["anomaly_model", "energy_model", "machine_type_map"]

        for key in required_keys:
            if key not in models:
                AI_MODELS = {
                    "loaded": False,
                    "data": None,
                    "message": f"ai_models.pkl is missing key: {key}"
                }
                return

        AI_MODELS = {
            "loaded": True,
            "data": models,
            "message": "AI models loaded successfully"
        }

    except Exception as e:
        AI_MODELS = {
            "loaded": False,
            "data": None,
            "message": f"Failed to load AI models: {str(e)}"
        }


def get_machine_type_code(machine_id):
    if AI_MODELS["loaded"]:
        machine_type_map = AI_MODELS["data"].get(
            "machine_type_map",
            DEFAULT_MACHINE_TYPE_MAP
        )
        return machine_type_map.get(machine_id, 0)

    return DEFAULT_MACHINE_TYPE_MAP.get(machine_id, 0)


def build_ai_features(machine_id, status, power, temperature, current, production_rate):
    machine_type = get_machine_type_code(machine_id)
    status_code = 1 if status == "ON" else 0

    feature_data = {
        "machine_type": [machine_type],
        "status": [status_code],
        "power": [power],
        "temperature": [temperature],
        "current": [current],
        "production_rate": [production_rate]
    }

    return pd.DataFrame(feature_data)


# ======================================================
# AI FUNCTIONS
# ======================================================

def ml_detect_anomaly(machine_id, status, power, temperature, current, production_rate):
    if status == "OFF":
        return False

    if not AI_MODELS["loaded"]:
        return False

    try:
        anomaly_model = AI_MODELS["data"]["anomaly_model"]

        features = build_ai_features(
            machine_id,
            status,
            power,
            temperature,
            current,
            production_rate
        )

        prediction = anomaly_model.predict(features)[0]

        # Isolation Forest:
        # 1 = normal
        # -1 = anomaly
        return prediction == -1

    except Exception:
        return False


def ml_predict_energy_next_30_min_wh(
    machine_id,
    status,
    power,
    temperature,
    current,
    production_rate
):
    if status == "OFF":
        return 0

    if not AI_MODELS["loaded"]:
        multiplier = 1.0

        if temperature > 60:
            multiplier += 0.10

        return round(power * 0.5 * multiplier, 3)

    try:
        energy_model = AI_MODELS["data"]["energy_model"]

        features = build_ai_features(
            machine_id,
            status,
            power,
            temperature,
            current,
            production_rate
        )

        prediction = energy_model.predict(features)[0]

        return round(max(float(prediction), 0), 3)

    except Exception:
        multiplier = 1.0

        if temperature > 60:
            multiplier += 0.10

        return round(power * 0.5 * multiplier, 3)


def calculate_ai_risk_score(
    machine_id,
    status,
    power,
    temperature,
    current,
    production_rate
):
    if status == "OFF":
        return 0

    limit = NORMAL_LIMITS.get(
        machine_id,
        {"power": 15.0, "temperature": 60.0}
    )

    score = 5

    if power > limit["power"]:
        power_ratio = (power - limit["power"]) / limit["power"]
        score += min(power_ratio * 60, 45)

    if temperature > limit["temperature"]:
        temp_ratio = (temperature - limit["temperature"]) / limit["temperature"]
        score += min(temp_ratio * 50, 35)

    if status == "ON" and production_rate == 0 and power > 2:
        score += 35

    if ml_detect_anomaly(
        machine_id,
        status,
        power,
        temperature,
        current,
        production_rate
    ):
        score += 35

    return round(min(score, 100), 1)


def get_optimized_power(machine_id, status, power, temperature, production_rate):
    if status == "OFF":
        return 0

    limit = NORMAL_LIMITS.get(
        machine_id,
        {"power": 15.0, "temperature": 60.0}
    )

    if status == "ON" and production_rate == 0 and power > 2:
        return 0

    if power > limit["power"] and temperature > limit["temperature"]:
        return round(power * 0.60, 2)

    if power > limit["power"]:
        return round(power * 0.75, 2)

    if temperature > limit["temperature"]:
        return round(power * 0.85, 2)

    return round(power * 0.95, 2)


def get_optimization_action(machine_id, status, power, temperature, production_rate):
    if status == "OFF":
        return "Machine is already OFF"

    limit = NORMAL_LIMITS.get(
        machine_id,
        {"power": 15.0, "temperature": 60.0}
    )

    if status == "ON" and production_rate == 0 and power > 2:
        return "Turn OFF idle machine to eliminate wasted energy"

    if power > limit["power"] and temperature > limit["temperature"]:
        return "Reduce load and schedule maintenance check"

    if power > limit["power"]:
        return "Reduce machine load or inspect abnormal consumption"

    if temperature > limit["temperature"]:
        return "Improve cooling or schedule maintenance"

    return "Eco mode: reduce power by 5% without affecting production"


def analyze_machine(machine_id, status, power, temperature, current, production_rate):
    limit = NORMAL_LIMITS.get(
        machine_id,
        {"power": 15.0, "temperature": 60.0}
    )

    if status == "OFF":
        return "Normal", "Machine is OFF"

    model_detected_anomaly = ml_detect_anomaly(
        machine_id,
        status,
        power,
        temperature,
        current,
        production_rate
    )

    if status == "ON" and production_rate == 0 and power > 2:
        return "Anomaly", "Idle energy waste detected: turn off machine or start production"

    if power > limit["power"] and temperature > limit["temperature"]:
        return "Anomaly", "High power and high temperature: check machine maintenance"

    if power > limit["power"]:
        return "Anomaly", "Abnormal power consumption: check machine load"

    if temperature > limit["temperature"]:
        return "Anomaly", "High temperature: cooling or maintenance required"

    if model_detected_anomaly:
        return "Anomaly", "AI model detected abnormal operating pattern"

    return "Normal", "No action needed"


# ======================================================
# MACHINE PROFILES FOR REALISTIC SIMULATION
# ======================================================

def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


MACHINE_PROFILES = {
    "motor_01": {
        "base_power": 9.5,
        "min_power": 8.0,
        "max_power": 12.0,
        "normal_temp": 38.0,
        "max_temp": 60.0,
        "load_factor": 0.045,
        "cooling_rate": 1.2
    },
    "fan_01": {
        "base_power": 6.5,
        "min_power": 5.0,
        "max_power": 9.0,
        "normal_temp": 34.0,
        "max_temp": 50.0,
        "load_factor": 0.030,
        "cooling_rate": 1.5
    },
    "pump_01": {
        "base_power": 11.0,
        "min_power": 8.0,
        "max_power": 14.0,
        "normal_temp": 40.0,
        "max_temp": 55.0,
        "load_factor": 0.050,
        "cooling_rate": 1.0
    }
}


# ======================================================
# UPDATE MACHINE STATE
# ======================================================

def update_machine_state(
    machine_id,
    status,
    voltage,
    current,
    power,
    temperature,
    production_rate
):
    status = status.upper().strip()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT total_energy_wh, last_update FROM machines WHERE machine_id = ?",
        (machine_id,)
    )

    row = cursor.fetchone()
    now = time.time()

    if row:
        previous_energy_wh = row[0] or 0
        last_update = row[1] or now
        delta_hours = max((now - last_update) / 3600.0, 0)
        added_energy_wh = power * delta_hours
        total_energy_wh = previous_energy_wh + added_energy_wh
    else:
        total_energy_wh = 0

    ai_status, recommendation = analyze_machine(
        machine_id,
        status,
        power,
        temperature,
        current,
        production_rate
    )

    cursor.execute("""
    UPDATE machines
    SET status = ?,
        latest_voltage = ?,
        latest_current = ?,
        latest_power = ?,
        latest_temperature = ?,
        production_rate = ?,
        total_energy_wh = ?,
        ai_status = ?,
        recommendation = ?,
        last_update = ?
    WHERE machine_id = ?
    """, (
        status,
        voltage,
        current,
        power,
        temperature,
        production_rate,
        total_energy_wh,
        ai_status,
        recommendation,
        now,
        machine_id
    ))

    cursor.execute("""
    INSERT INTO sensor_history (
        machine_id, status, voltage, current, power,
        temperature, production_rate, ai_status,
        recommendation, created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        machine_id,
        status,
        voltage,
        current,
        power,
        temperature,
        production_rate,
        ai_status,
        recommendation,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


# ======================================================
# REALISTIC MACHINE SIMULATION
# ======================================================

def simulate_machine(machine_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT target_status, latest_power, latest_temperature, production_rate
    FROM machines
    WHERE machine_id = ?
    """, (machine_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return

    target_status = row[0]
    previous_power = row[1] or 0
    previous_temperature = row[2] or 25
    previous_production = row[3] or 0

    profile = MACHINE_PROFILES.get(machine_id, MACHINE_PROFILES["motor_01"])

    ambient_temp = 25.0
    voltage = 12.0

    if target_status == "OFF":
        status = "OFF"
        power = 0
        current = 0
        production_rate = 0

        temperature = previous_temperature - profile["cooling_rate"]
        temperature = clamp(temperature, ambient_temp, previous_temperature)

    else:
        status = "ON"

        production_change = random.uniform(-8, 8)
        production_rate = previous_production + production_change

        if production_rate <= 0:
            production_rate = random.choice([0, 50, 60, 70, 80, 90])

        production_rate = clamp(production_rate, 0, 100)

        anomaly_type = random.choices(
            ["normal", "overload", "overheat", "idle_waste"],
            weights=[88, 5, 4, 3],
            k=1
        )[0]

        if anomaly_type == "idle_waste":
            production_rate = 0
            power = random.uniform(
                profile["min_power"],
                profile["max_power"]
            )

        elif anomaly_type == "overload":
            production_rate = random.uniform(80, 100)
            power = profile["max_power"] * random.uniform(1.35, 1.75)

        elif anomaly_type == "overheat":
            production_rate = random.uniform(50, 90)
            power = random.uniform(
                profile["min_power"],
                profile["max_power"]
            )

        else:
            load_power = profile["base_power"] + (
                production_rate * profile["load_factor"]
            )

            noise = random.uniform(-0.5, 0.5)
            power = load_power + noise
            power = clamp(
                power,
                profile["min_power"],
                profile["max_power"]
            )

        if previous_power > 0:
            power = (previous_power * 0.65) + (power * 0.35)

        heat_gain = (power / profile["max_power"]) * 1.8
        natural_cooling = 0.5

        temperature = previous_temperature + heat_gain - natural_cooling

        if anomaly_type == "overheat":
            temperature += random.uniform(12, 22)

        temperature += random.uniform(-0.4, 0.4)
        temperature = clamp(temperature, ambient_temp, 80)

        current = round(power / voltage, 2)

    update_machine_state(
        machine_id,
        status,
        voltage,
        current,
        round(power, 2),
        round(temperature, 1),
        round(production_rate, 1)
    )


# ======================================================
# HELPER FUNCTIONS
# ======================================================

def get_all_machines():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT machine_id, name, type, status, target_status,
           latest_voltage, latest_current, latest_power,
           latest_temperature, production_rate,
           total_energy_wh, ai_status, recommendation
    FROM machines
    """)

    rows = cursor.fetchall()
    conn.close()

    machines = []

    for row in rows:
        machine_id = row[0]
        name = row[1]
        machine_type = row[2]
        status = row[3]
        target_status = row[4]
        voltage = row[5] or 0
        current = row[6] or 0
        power = row[7] or 0
        temperature = row[8] or 0
        production_rate = row[9] or 0
        energy_wh = row[10] or 0
        ai_status = row[11]
        recommendation = row[12]

        energy_kwh = energy_wh / 1000
        cost = energy_kwh * ELECTRICITY_PRICE_TND_PER_KWH
        co2 = energy_kwh * CO2_FACTOR_KG_PER_KWH

        risk_score = calculate_ai_risk_score(
            machine_id,
            status,
            power,
            temperature,
            current,
            production_rate
        )

        predicted_energy = ml_predict_energy_next_30_min_wh(
            machine_id,
            status,
            power,
            temperature,
            current,
            production_rate
        )

        optimized_power = get_optimized_power(
            machine_id,
            status,
            power,
            temperature,
            production_rate
        )

        optimization_action = get_optimization_action(
            machine_id,
            status,
            power,
            temperature,
            production_rate
        )

        machines.append({
            "machineId": machine_id,
            "name": name,
            "type": machine_type,
            "status": status,
            "targetStatus": target_status,
            "voltage": round(voltage, 2),
            "current": round(current, 2),
            "power": round(power, 2),
            "temperature": round(temperature, 1),
            "productionRate": round(production_rate, 1),
            "energyWh": round(energy_wh, 3),
            "costTND": round(cost, 4),
            "co2Kg": round(co2, 4),
            "aiStatus": ai_status,
            "recommendation": recommendation,
            "riskScore": risk_score,
            "predictedEnergyNext30MinWh": predicted_energy,
            "optimizedPower": optimized_power,
            "optimizationAction": optimization_action
        })

    return machines


def get_one_machine(machine_id):
    machines = get_all_machines()

    for machine in machines:
        if machine["machineId"] == machine_id:
            return machine

    return None


# ======================================================
# STARTUP
# ======================================================

@app.on_event("startup")
def startup_event():
    init_db()
    load_ai_models()
    print(AI_MODELS["message"])


# ======================================================
# API ENDPOINTS
# ======================================================

@app.get("/")
def home():
    return {
        "message": "EcoTwin AI Backend is running",
        "project": "AI-Powered Digital Twin for Industrial Energy Optimization",
        "aiModelLoaded": AI_MODELS["loaded"],
        "aiMessage": AI_MODELS["message"]
    }


@app.get("/api/ai-status")
def get_ai_status():
    model_mae = None
    dataset_rows = None

    if AI_MODELS["loaded"]:
        model_mae = AI_MODELS["data"].get("energy_model_mae", None)
        dataset_rows = AI_MODELS["data"].get("dataset_rows", None)

    return {
        "aiModelLoaded": AI_MODELS["loaded"],
        "message": AI_MODELS["message"],
        "models": {
            "anomalyDetection": "Isolation Forest",
            "energyPrediction": "Random Forest Regressor"
        },
        "energyModelMAE": model_mae,
        "datasetRows": dataset_rows
    }


@app.post("/api/sensor-data")
def receive_sensor_data(data: SensorData):
    update_machine_state(
        data.machineId,
        data.status,
        data.voltage,
        data.current,
        data.power,
        data.temperature,
        data.productionRate
    )

    machine = get_one_machine(data.machineId)

    return {
        "success": True,
        "message": "Sensor data received",
        "machineId": data.machineId,
        "aiModelLoaded": AI_MODELS["loaded"],
        "aiStatus": machine["aiStatus"] if machine else "Unknown",
        "recommendation": machine["recommendation"] if machine else "Unknown",
        "riskScore": machine["riskScore"] if machine else 0,
        "predictedEnergyNext30MinWh": machine["predictedEnergyNext30MinWh"] if machine else 0,
        "optimizationAction": machine["optimizationAction"] if machine else "Unknown"
    }


@app.get("/api/factory-state")
def get_factory_state():
    simulate_machine("motor_01")
    simulate_machine("fan_01")
    simulate_machine("pump_01")

    machines = get_all_machines()

    total_power = sum(m["power"] for m in machines)
    total_energy_wh = sum(m["energyWh"] for m in machines)
    total_cost = sum(m["costTND"] for m in machines)
    total_co2 = sum(m["co2Kg"] for m in machines)
    anomaly_count = sum(1 for m in machines if m["aiStatus"] == "Anomaly")

    before_energy_wh = sum(m["predictedEnergyNext30MinWh"] for m in machines)
    after_energy_wh = sum((m["optimizedPower"] * 0.5) for m in machines)
    energy_saved_wh = max(before_energy_wh - after_energy_wh, 0)

    if before_energy_wh > 0:
        energy_saved_percent = round((energy_saved_wh / before_energy_wh) * 100, 1)
    else:
        energy_saved_percent = 0

    cost_saved_tnd = (energy_saved_wh / 1000) * ELECTRICITY_PRICE_TND_PER_KWH
    co2_saved_kg = (energy_saved_wh / 1000) * CO2_FACTOR_KG_PER_KWH

    optimization_plan = []

    for machine in machines:
        optimization_plan.append({
            "machineId": machine["machineId"],
            "machineName": machine["name"],
            "currentPower": machine["power"],
            "optimizedPower": machine["optimizedPower"],
            "action": machine["optimizationAction"]
        })

    return {
        "factoryName": "EcoTwin AI Factory",
        "timestamp": datetime.now().isoformat(),
        "aiModelLoaded": AI_MODELS["loaded"],
        "aiMessage": AI_MODELS["message"],
        "totalPower": round(total_power, 2),
        "totalEnergyWh": round(total_energy_wh, 3),
        "totalCostTND": round(total_cost, 4),
        "totalCO2Kg": round(total_co2, 4),
        "anomalyCount": anomaly_count,
        "optimization": {
            "beforeEnergyWh": round(before_energy_wh, 3),
            "afterEnergyWh": round(after_energy_wh, 3),
            "energySavedWh": round(energy_saved_wh, 3),
            "energySavedPercent": energy_saved_percent,
            "costSavedTND": round(cost_saved_tnd, 4),
            "co2SavedKg": round(co2_saved_kg, 4),
            "optimizationPlan": optimization_plan
        },
        "machines": machines
    }


@app.get("/api/machine/{machine_id}")
def get_machine(machine_id: str):
    machine = get_one_machine(machine_id)

    if not machine:
        return {
            "success": False,
            "message": "Machine not found"
        }

    return {
        "success": True,
        "aiModelLoaded": AI_MODELS["loaded"],
        "machine": machine
    }


@app.post("/api/command")
def send_command(command: CommandRequest):
    target_status = command.targetStatus.upper().strip()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE machines
    SET target_status = ?
    WHERE machine_id = ?
    """, (
        target_status,
        command.machineId
    ))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "machineId": command.machineId,
        "targetStatus": target_status
    }


@app.get("/api/command/{machine_id}")
def get_command(machine_id: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT target_status FROM machines WHERE machine_id = ?",
        (machine_id,)
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "success": False,
            "message": "Machine not found"
        }

    return {
        "success": True,
        "machineId": machine_id,
        "targetStatus": row[0]
    }


@app.get("/api/history/{machine_id}")
def get_history(machine_id: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT power, temperature, ai_status, recommendation, created_at
    FROM sensor_history
    WHERE machine_id = ?
    ORDER BY id DESC
    LIMIT 50
    """, (machine_id,))

    rows = cursor.fetchall()
    conn.close()

    history = []

    for row in rows:
        history.append({
            "power": row[0],
            "temperature": row[1],
            "aiStatus": row[2],
            "recommendation": row[3],
            "createdAt": row[4]
        })

    return {
        "machineId": machine_id,
        "history": history
    }


@app.post("/api/reset")
def reset_data():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM sensor_history")

    cursor.execute("""
    UPDATE machines
    SET status = 'OFF',
        target_status = 'OFF',
        latest_voltage = 0,
        latest_current = 0,
        latest_power = 0,
        latest_temperature = 25,
        production_rate = 0,
        total_energy_wh = 0,
        ai_status = 'Normal',
        recommendation = 'No action needed',
        last_update = ?
    """, (time.time(),))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": "EcoTwin AI data reset"
    }