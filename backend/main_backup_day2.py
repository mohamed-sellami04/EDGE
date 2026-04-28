from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import sqlite3
import random
import time

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

ELECTRICITY_PRICE_TND_PER_KWH = 0.30
CO2_FACTOR_KG_PER_KWH = 0.45

NORMAL_LIMITS = {
    "motor_01": {"power": 12.0, "temperature": 60.0},
    "fan_01": {"power": 9.0, "temperature": 50.0},
    "pump_01": {"power": 14.0, "temperature": 55.0},
}


# ======================================================
# DTO CLASSES
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
# AI / ANALYSIS LOGIC
# ======================================================

def analyze_machine(machine_id, status, power, temperature, production_rate):
    limit = NORMAL_LIMITS.get(
        machine_id,
        {"power": 15.0, "temperature": 60.0}
    )

    if status == "OFF":
        return "Normal", "Machine is OFF"

    if power > limit["power"] and temperature > limit["temperature"]:
        return "Anomaly", "High power and high temperature: check machine maintenance"

    if power > limit["power"]:
        return "Anomaly", "Abnormal power consumption: check machine load"

    if temperature > limit["temperature"]:
        return "Anomaly", "High temperature: cooling or maintenance required"

    if status == "ON" and production_rate == 0 and power > 2:
        return "Anomaly", "Idle energy waste: turn off machine or start production"

    return "Normal", "No action needed"


def update_machine_state(
    machine_id,
    status,
    voltage,
    current,
    power,
    temperature,
    production_rate
):
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
# SIMULATION FOR FAN AND PUMP
# ======================================================

def simulate_machine(machine_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT target_status FROM machines WHERE machine_id = ?",
        (machine_id,)
    )
    row = cursor.fetchone()

    conn.close()

    target_status = row[0] if row else "OFF"

    if target_status == "OFF":
        status = "OFF"
        voltage = 0
        current = 0
        power = 0
        temperature = round(random.uniform(24, 30), 1)
        production_rate = 0

    else:
        status = "ON"
        voltage = 12.0
        anomaly = random.random() < 0.10

        if machine_id == "fan_01":
            if anomaly:
                power = round(random.uniform(13, 18), 2)
                temperature = round(random.uniform(55, 70), 1)
            else:
                power = round(random.uniform(5, 8), 2)
                temperature = round(random.uniform(28, 40), 1)

        elif machine_id == "pump_01":
            if anomaly:
                power = round(random.uniform(20, 28), 2)
                temperature = round(random.uniform(58, 75), 1)
            else:
                power = round(random.uniform(8, 13), 2)
                temperature = round(random.uniform(30, 45), 1)

        else:
            power = round(random.uniform(7, 11), 2)
            temperature = round(random.uniform(30, 45), 1)

        current = round(power / voltage, 2)
        production_rate = random.choice([0, 50, 60, 70, 80, 90])

    update_machine_state(
        machine_id,
        status,
        voltage,
        current,
        power,
        temperature,
        production_rate
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
        energy_wh = row[10] or 0
        energy_kwh = energy_wh / 1000
        cost = energy_kwh * ELECTRICITY_PRICE_TND_PER_KWH
        co2 = energy_kwh * CO2_FACTOR_KG_PER_KWH

        machines.append({
            "machineId": row[0],
            "name": row[1],
            "type": row[2],
            "status": row[3],
            "targetStatus": row[4],
            "voltage": round(row[5] or 0, 2),
            "current": round(row[6] or 0, 2),
            "power": round(row[7] or 0, 2),
            "temperature": round(row[8] or 0, 1),
            "productionRate": round(row[9] or 0, 1),
            "energyWh": round(energy_wh, 3),
            "costTND": round(cost, 4),
            "co2Kg": round(co2, 4),
            "aiStatus": row[11],
            "recommendation": row[12]
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


# ======================================================
# API ENDPOINTS
# ======================================================

@app.get("/")
def home():
    return {
        "message": "EcoTwin AI Backend is running",
        "project": "AI-Powered IoT Digital Twin for Industrial Energy Optimization"
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
        "aiStatus": machine["aiStatus"] if machine else "Unknown",
        "recommendation": machine["recommendation"] if machine else "Unknown"
    }


@app.get("/api/factory-state")
def get_factory_state():
    # Simulation mode: all machines are simulated.
    # Later, when ESP32 is ready, remove simulate_machine("motor_01").
    simulate_machine("motor_01")
    simulate_machine("fan_01")
    simulate_machine("pump_01")
    machines = get_all_machines()

    total_power = sum(m["power"] for m in machines)
    total_energy_wh = sum(m["energyWh"] for m in machines)
    total_cost = sum(m["costTND"] for m in machines)
    total_co2 = sum(m["co2Kg"] for m in machines)
    anomaly_count = sum(1 for m in machines if m["aiStatus"] == "Anomaly")

    before_energy_wh = total_energy_wh
    after_energy_wh = total_energy_wh * 0.72
    energy_saved_wh = before_energy_wh - after_energy_wh

    return {
        "factoryName": "EcoTwin AI Factory",
        "timestamp": datetime.now().isoformat(),
        "totalPower": round(total_power, 2),
        "totalEnergyWh": round(total_energy_wh, 3),
        "totalCostTND": round(total_cost, 4),
        "totalCO2Kg": round(total_co2, 4),
        "anomalyCount": anomaly_count,
        "optimization": {
            "beforeEnergyWh": round(before_energy_wh, 3),
            "afterEnergyWh": round(after_energy_wh, 3),
            "energySavedWh": round(energy_saved_wh, 3),
            "energySavedPercent": 28
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
        "machine": machine
    }


@app.post("/api/command")
def send_command(command: CommandRequest):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE machines
    SET target_status = ?
    WHERE machine_id = ?
    """, (
        command.targetStatus,
        command.machineId
    ))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "machineId": command.machineId,
        "targetStatus": command.targetStatus
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