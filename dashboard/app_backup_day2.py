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

st.title("⚡ EcoTwin AI")
st.subheader("AI-Powered Digital Twin for Industrial Energy Optimization")

# Auto refresh
if "refresh" not in st.session_state:
    st.session_state.refresh = True


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


factory = get_factory_state()

if factory is None:
    st.warning("Start the FastAPI backend first.")
    st.stop()

# ================= OVERVIEW =================

st.markdown("## 🏭 Factory Overview")

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Total Power", f"{factory['totalPower']} W")
col2.metric("Total Energy", f"{factory['totalEnergyWh']} Wh")
col3.metric("Cost", f"{factory['totalCostTND']} TND")
col4.metric("CO₂", f"{factory['totalCO2Kg']} kg")
col5.metric("Anomalies", factory["anomalyCount"])

st.divider()

# ================= OPTIMIZATION =================

st.markdown("## 🌱 Optimization Impact")

optimization = factory["optimization"]

before = optimization["beforeEnergyWh"]
after = optimization["afterEnergyWh"]
saved = optimization["energySavedWh"]
saved_percent = optimization["energySavedPercent"]

c1, c2, c3, c4 = st.columns(4)

c1.metric("Before Optimization", f"{before} Wh")
c2.metric("After Optimization", f"{after} Wh")
c3.metric("Energy Saved", f"{saved} Wh")
c4.metric("Saving Rate", f"{saved_percent}%")

chart_df = pd.DataFrame({
    "Scenario": ["Before Optimization", "After Optimization"],
    "Energy Wh": [before, after]
})

st.bar_chart(chart_df, x="Scenario", y="Energy Wh")

st.divider()

# ================= MACHINE CARDS =================

st.markdown("## 🤖 Digital Twin Machines")

machines = factory["machines"]

for machine in machines:
    status = machine["status"]
    ai_status = machine["aiStatus"]

    if ai_status == "Anomaly":
        card_color = "#3b0f0f"
        status_icon = "🚨"
    elif status == "ON":
        card_color = "#0f2f1a"
        status_icon = "🟢"
    else:
        card_color = "#222222"
        status_icon = "⚫"

    with st.container():
        st.markdown(
            f"""
            <div style="
                background-color:{card_color};
                padding:20px;
                border-radius:15px;
                margin-bottom:15px;
                border:1px solid #444;
            ">
                <h3>{status_icon} {machine['name']}</h3>
                <p><b>Type:</b> {machine['type']}</p>
                <p><b>Status:</b> {machine['status']}</p>
                <p><b>Target Status:</b> {machine['targetStatus']}</p>
                <p><b>Power:</b> {machine['power']} W</p>
                <p><b>Temperature:</b> {machine['temperature']} °C</p>
                <p><b>Production Rate:</b> {machine['productionRate']}%</p>
                <p><b>AI Status:</b> {machine['aiStatus']}</p>
                <p><b>Recommendation:</b> {machine['recommendation']}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        b1, b2 = st.columns(2)

        with b1:
            if st.button(f"Turn ON {machine['name']}", key=f"on_{machine['machineId']}"):
                send_command(machine["machineId"], "ON")
                st.rerun()

        with b2:
            if st.button(f"Turn OFF {machine['name']}", key=f"off_{machine['machineId']}"):
                send_command(machine["machineId"], "OFF")
                st.rerun()

st.divider()

# ================= CHARTS =================

st.markdown("## 📊 Energy Analysis")

df = pd.DataFrame(machines)

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("### Power by Machine")
    st.bar_chart(df, x="name", y="power")

with chart_col2:
    st.markdown("### Energy by Machine")
    st.bar_chart(df, x="name", y="energyWh")

st.markdown("### Machine Data Table")
st.dataframe(df, use_container_width=True)

st.divider()

# ================= AI RECOMMENDATIONS =================

st.markdown("## 🧠 AI Recommendations")

anomalies = [m for m in machines if m["aiStatus"] == "Anomaly"]

if len(anomalies) == 0:
    st.success("All machines are operating normally.")
else:
    for m in anomalies:
        st.error(f"{m['name']}: {m['recommendation']}")

st.divider()

# ================= CONTROLS =================

st.markdown("## ⚙️ System Controls")

c1, c2 = st.columns(2)

with c1:
    if st.button("Reset Data"):
        reset_data()
        st.rerun()

with c2:
    if st.button("Refresh Now"):
        st.rerun()

time.sleep(1)
st.rerun()