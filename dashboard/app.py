import streamlit as st
import requests
import pandas as pd
import time

API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="EcoTwin AI Dashboard",
    page_icon="⚡",
    layout="wide"
)

st.markdown("""
<style>
.big-title {
    font-size: 42px;
    font-weight: 800;
}
.subtitle {
    font-size: 18px;
    color: #A0A0A0;
}
.machine-card {
    padding: 20px;
    border-radius: 16px;
    margin-bottom: 18px;
    border: 1px solid #444;
}
</style>
""", unsafe_allow_html=True)


def get_factory_state():
    try:
        response = requests.get(f"{API_URL}/api/factory-state", timeout=5)
        return response.json()
    except Exception as e:
        st.error(f"Backend connection error: {e}")
        return None


def send_command(machine_id, target_status):
    try:
        response = requests.post(
            f"{API_URL}/api/command",
            json={
                "machineId": machine_id,
                "targetStatus": target_status
            },
            timeout=5
        )
        return response.json()
    except Exception as e:
        st.error(f"Command error: {e}")
        return None


def reset_data():
    try:
        requests.post(f"{API_URL}/api/reset", timeout=5)
    except Exception as e:
        st.error(f"Reset error: {e}")


st.sidebar.title("EcoTwin AI Controls")
auto_refresh = st.sidebar.checkbox("Auto refresh", value=True)
refresh_delay = st.sidebar.slider("Refresh delay seconds", 1, 10, 3)

if st.sidebar.button("Reset Data"):
    reset_data()
    st.rerun()

if st.sidebar.button("Refresh Now"):
    st.rerun()

st.markdown('<div class="big-title">⚡ EcoTwin AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">AI-Powered Digital Twin for Industrial Energy Optimization</div>',
    unsafe_allow_html=True
)

factory = get_factory_state()

if factory is None:
    st.warning("Start the FastAPI backend first.")
    st.stop()

machines = factory["machines"]
optimization = factory["optimization"]

st.divider()

# ================= FACTORY OVERVIEW =================

st.markdown("## 🏭 Factory Overview")

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Total Power", f"{factory['totalPower']} W")
col2.metric("Total Energy", f"{factory['totalEnergyWh']} Wh")
col3.metric("Cost", f"{factory['totalCostTND']} TND")
col4.metric("CO₂", f"{factory['totalCO2Kg']} kg")
col5.metric("Anomalies", factory["anomalyCount"])

st.divider()

# ================= OPTIMIZATION IMPACT =================

st.markdown("## 🌱 AI Optimization Impact")

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Before", f"{optimization['beforeEnergyWh']} Wh")
c2.metric("After", f"{optimization['afterEnergyWh']} Wh")
c3.metric("Energy Saved", f"{optimization['energySavedWh']} Wh")
c4.metric("Saving Rate", f"{optimization['energySavedPercent']}%")
c5.metric("CO₂ Saved", f"{optimization['co2SavedKg']} kg")

impact_df = pd.DataFrame({
    "Scenario": ["Before AI Optimization", "After AI Optimization"],
    "Energy Wh": [
        optimization["beforeEnergyWh"],
        optimization["afterEnergyWh"]
    ]
})

st.bar_chart(impact_df, x="Scenario", y="Energy Wh")

st.success(
    f"AI optimization can save {optimization['energySavedWh']} Wh in the next 30 minutes, "
    f"reduce cost by {optimization['costSavedTND']} TND, "
    f"and reduce CO₂ by {optimization['co2SavedKg']} kg."
)

st.divider()

# ================= MACHINE CARDS =================

st.markdown("## 🤖 Digital Twin Machines")

for machine in machines:
    status = machine["status"]
    ai_status = machine["aiStatus"]
    risk = machine.get("riskScore", 0)

    if ai_status == "Anomaly":
        bg = "#3b0f0f"
        icon = "🚨"
    elif status == "ON":
        bg = "#0f2f1a"
        icon = "🟢"
    else:
        bg = "#222222"
        icon = "⚫"

    st.markdown(
        f"""
        <div class="machine-card" style="background-color:{bg};">
            <h3>{icon} {machine['name']}</h3>
            <p><b>Type:</b> {machine['type']}</p>
            <p><b>Status:</b> {machine['status']} | <b>Target:</b> {machine['targetStatus']}</p>
            <p><b>Power:</b> {machine['power']} W</p>
            <p><b>Temperature:</b> {machine['temperature']} °C</p>
            <p><b>Production Rate:</b> {machine['productionRate']}%</p>
            <p><b>AI Status:</b> {machine['aiStatus']}</p>
            <p><b>AI Recommendation:</b> {machine['recommendation']}</p>
            <p><b>Optimization Action:</b> {machine.get('optimizationAction', 'No action')}</p>
            <p><b>Predicted Energy Next 30 min:</b> {machine.get('predictedEnergyNext30MinWh', 0)} Wh</p>
            <p><b>Optimized Power:</b> {machine.get('optimizedPower', 0)} W</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.write(f"AI Risk Score: {risk}%")
    st.progress(min(float(risk) / 100, 1.0))

    b1, b2, b3 = st.columns(3)

    with b1:
        if st.button(f"Turn ON {machine['name']}", key=f"on_{machine['machineId']}"):
            send_command(machine["machineId"], "ON")
            st.rerun()

    with b2:
        if st.button(f"Turn OFF {machine['name']}", key=f"off_{machine['machineId']}"):
            send_command(machine["machineId"], "OFF")
            st.rerun()

    with b3:
        if ai_status == "Anomaly":
            st.error("Anomaly detected")
        else:
            st.success("Normal")

st.divider()

# ================= ENERGY ANALYSIS =================

st.markdown("## 📊 Energy Analysis")

df = pd.DataFrame(machines)

chart1, chart2 = st.columns(2)

with chart1:
    st.markdown("### Power by Machine")
    st.bar_chart(df, x="name", y="power")

with chart2:
    st.markdown("### Energy by Machine")
    st.bar_chart(df, x="name", y="energyWh")

chart3, chart4 = st.columns(2)

with chart3:
    st.markdown("### AI Risk Score")
    st.bar_chart(df, x="name", y="riskScore")

with chart4:
    st.markdown("### Predicted Energy Next 30 min")
    st.bar_chart(df, x="name", y="predictedEnergyNext30MinWh")

st.markdown("### Full Machine Data")
st.dataframe(df, use_container_width=True)

st.divider()

# ================= OPTIMIZATION PLAN =================

st.markdown("## 🧠 AI Optimization Plan")

for item in optimization["optimizationPlan"]:
    st.info(
        f"{item['machineName']} | "
        f"Current Power: {item['currentPower']} W → "
        f"Optimized Power: {item['optimizedPower']} W | "
        f"Action: {item['action']}"
    )

st.divider()

# ================= AI ALERTS =================

st.markdown("## 🚨 AI Alerts")

anomalies = [m for m in machines if m["aiStatus"] == "Anomaly"]

if len(anomalies) == 0:
    st.success("All machines are operating normally.")
else:
    for m in anomalies:
        st.error(f"{m['name']}: {m['recommendation']}")

# ================= AUTO REFRESH =================

if auto_refresh:
    time.sleep(refresh_delay)
    st.rerun()