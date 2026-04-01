import streamlit as st
import pandas as pd
import sqlite3
import pickle
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = "healo.db"
MODEL_PATH = "models/dropout_model.pkl"

st.set_page_config(
    page_title="HealO — Doctor Dashboard",
    page_icon="💊",
    layout="wide"
)

# ── Styles ──────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background-color: #f7f6f2; }
.metric-card {
    background: white;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    text-align: center;
}
.risk-high   { color: #a12c7b; font-weight: 700; }
.risk-medium { color: #da7101; font-weight: 700; }
.risk-low    { color: #437a22; font-weight: 700; }
.section-title { font-size: 1.1rem; font-weight: 600; color: #28251d; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)


# ── Data loaders ─────────────────────────────────────────
@st.cache_resource
def load_model():
    with open(MODEL_PATH, "rb") as f:
        data = pickle.load(f)
    return data["model"], data["label_encoder"]


@st.cache_data(ttl=30)
def load_patients():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT p.id, p.full_name, p.age, p.gender, p.language,
               p.disease, p.is_active,
               COUNT(DISTINCT m.id) as messages_sent,
               COUNT(DISTINCT r.id) as replies_received
        FROM patients p
        LEFT JOIN message_logs m ON m.patient_id = p.id
        LEFT JOIN responses r ON r.patient_id = p.id
        GROUP BY p.id
    """, conn)
    conn.close()
    return df


@st.cache_data(ttl=30)
def load_features():
    try:
        df = pd.read_csv("features_dataset.csv")
        df["date"] = pd.to_datetime(df["date"])
        return df
    except FileNotFoundError:
        return pd.DataFrame()


def get_latest_features(features_df, patient_id):
    patient_feats = features_df[features_df["patient_id"] == patient_id]
    if patient_feats.empty:
        return None
    return patient_feats.sort_values("date").iloc[-1]


def predict_risk(model, le, row):
    feature_cols = [
        "reply_streak", "skip_rate_so_far", "weekend_skip_rate",
        "avg_reply_latency_seconds", "is_weekend",
        "messages_sent", "responses_received", "replied_today"
    ]
    X = [[row.get(col, 0) for col in feature_cols]]
    pred = model.predict(X)[0]
    proba = model.predict_proba(X)[0]
    label = le.inverse_transform([pred])[0]
    confidence = max(proba) * 100
    return label, confidence


def generate_shap_explanation(row, risk_label):
    explanations = []
    if row.get("reply_streak", 0) == 0:
        explanations.append("❌ No recent reply streak")
    elif row.get("reply_streak", 0) < 3:
        explanations.append(f"⚠️ Short streak: {int(row['reply_streak'])} days")
    else:
        explanations.append(f"✅ Streak: {int(row['reply_streak'])} days")

    skip = row.get("skip_rate_so_far", 0)
    if skip > 0.5:
        explanations.append(f"❌ High skip rate: {skip*100:.0f}%")
    elif skip > 0.2:
        explanations.append(f"⚠️ Moderate skip rate: {skip*100:.0f}%")
    else:
        explanations.append(f"✅ Low skip rate: {skip*100:.0f}%")

    latency = row.get("avg_reply_latency_seconds", 0)
    if latency > 5400:
        explanations.append(f"⚠️ Slow replies: avg {latency/3600:.1f}h")
    elif latency > 0:
        explanations.append(f"✅ Reply time: avg {latency/60:.0f} min")

    weekend_skip = row.get("weekend_skip_rate", 0)
    if weekend_skip > 0.5:
        explanations.append(f"❌ Weekend skip rate: {weekend_skip*100:.0f}%")

    return explanations


# ── Header ───────────────────────────────────────────────
col_logo, col_title = st.columns([1, 8])
with col_logo:
    st.markdown("## 💊")
with col_title:
    st.markdown("# HealO — Medication Adherence Dashboard")
    st.caption(f"Last updated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}")

st.divider()

# ── Load data ────────────────────────────────────────────
model, le = load_model()
patients_df = load_patients()
features_df = load_features()

# Score every patient
risk_labels = []
confidences = []
for _, patient in patients_df.iterrows():
    row = get_latest_features(features_df, patient["id"])
    if row is not None:
        label, conf = predict_risk(model, le, row)
    else:
        label, conf = "Low", 50.0
    risk_labels.append(label)
    confidences.append(conf)

patients_df["risk_label"] = risk_labels
patients_df["confidence"] = confidences

risk_order = {"High": 0, "Medium": 1, "Low": 2}
patients_df["risk_order"] = patients_df["risk_label"].map(risk_order)
patients_df = patients_df.sort_values("risk_order")

# ── KPI Cards ────────────────────────────────────────────
total = len(patients_df)
high_risk = len(patients_df[patients_df["risk_label"] == "High"])
medium_risk = len(patients_df[patients_df["risk_label"] == "Medium"])
low_risk = len(patients_df[patients_df["risk_label"] == "Low"])
avg_compliance = (
    patients_df["replies_received"].sum() /
    max(patients_df["messages_sent"].sum(), 1) * 100
)

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.metric("Total Patients", total)
with k2:
    st.metric("🔴 High Risk", high_risk, delta=f"{high_risk/total*100:.0f}%")
with k3:
    st.metric("🟠 Medium Risk", medium_risk)
with k4:
    st.metric("🟢 Low Risk", low_risk)
with k5:
    st.metric("📬 Avg Compliance", f"{avg_compliance:.1f}%")

st.divider()

# ── Main layout ──────────────────────────────────────────
left, right = st.columns([2, 1])

with left:
    st.markdown("### 🚨 Patient Risk List")

    risk_filter = st.selectbox(
        "Filter by risk",
        ["All", "High", "Medium", "Low"],
        index=0
    )

    display_df = patients_df.copy()
    if risk_filter != "All":
        display_df = display_df[display_df["risk_label"] == risk_filter]

    def color_risk(val):
        colors = {"High": "#fce4f0", "Medium": "#fff3e0", "Low": "#e8f5e9"}
        return f"background-color: {colors.get(val, 'white')}"

    st.dataframe(
        display_df[[
            "full_name", "age", "disease", "language",
            "messages_sent", "replies_received", "risk_label", "confidence"
        ]].rename(columns={
            "full_name": "Patient",
            "age": "Age",
            "disease": "Disease",
            "language": "Language",
            "messages_sent": "Msgs Sent",
            "replies_received": "Replies",
            "risk_label": "Risk",
            "confidence": "Confidence %"
        }).style.applymap(color_risk, subset=["Risk"]),
        use_container_width=True,
        height=400
    )

with right:
    st.markdown("### 📊 Risk Distribution")
    risk_counts = patients_df["risk_label"].value_counts().reset_index()
    risk_counts.columns = ["Risk", "Count"]
    fig_pie = px.pie(
        risk_counts,
        values="Count",
        names="Risk",
        color="Risk",
        color_discrete_map={
            "High": "#a12c7b",
            "Medium": "#da7101",
            "Low": "#437a22"
        },
        hole=0.4
    )
    fig_pie.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        showlegend=True,
        height=250
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("### 🦠 By Disease")
    disease_risk = patients_df.groupby(
        ["disease", "risk_label"]
    ).size().reset_index(name="count")
    fig_bar = px.bar(
        disease_risk,
        x="disease",
        y="count",
        color="risk_label",
        color_discrete_map={
            "High": "#a12c7b",
            "Medium": "#da7101",
            "Low": "#437a22"
        },
        barmode="stack"
    )
    fig_bar.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        height=220,
        showlegend=False,
        xaxis_title="",
        yaxis_title="Patients"
    )
    st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ── Patient Detail ───────────────────────────────────────
st.markdown("### 🔍 Patient Detail View")

selected_name = st.selectbox(
    "Select a patient",
    patients_df["full_name"].tolist()
)

selected = patients_df[patients_df["full_name"] == selected_name].iloc[0]
patient_feats = get_latest_features(features_df, selected["id"])

d1, d2, d3 = st.columns(3)
with d1:
    st.markdown(f"**Name:** {selected['full_name']}")
    st.markdown(f"**Age:** {selected['age']} | **Gender:** {selected['gender']}")
    st.markdown(f"**Disease:** {selected['disease']}")
    st.markdown(f"**Language:** {selected['language']}")

with d2:
    risk = selected["risk_label"]
    css_class = f"risk-{risk.lower()}"
    st.markdown(f"**Risk Level:** <span class='{css_class}'>{risk}</span>",
                unsafe_allow_html=True)
    st.markdown(f"**Confidence:** {selected['confidence']:.1f}%")
    st.markdown(f"**Messages sent:** {selected['messages_sent']}")
    st.markdown(f"**Replies received:** {selected['replies_received']}")

with d3:
    if patient_feats is not None:
        st.markdown("**Why flagged:**")
        explanations = generate_shap_explanation(patient_feats, risk)
        for exp in explanations:
            st.markdown(f"- {exp}")
    else:
        st.markdown("_No feature data available_")

# ── Trend Chart ──────────────────────────────────────────
if not features_df.empty:
    st.markdown("### 📈 Adherence Trend")
    patient_history = features_df[
        features_df["patient_id"] == selected["id"]
    ].sort_values("date")

    if not patient_history.empty:
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=patient_history["date"],
            y=patient_history["reply_streak"],
            mode="lines+markers",
            name="Reply Streak",
            line=dict(color="#01696f", width=2)
        ))
        fig_trend.add_trace(go.Scatter(
            x=patient_history["date"],
            y=patient_history["skip_rate_so_far"] * 10,
            mode="lines",
            name="Skip Rate (×10)",
            line=dict(color="#a12c7b", width=2, dash="dash")
        ))
        fig_trend.update_layout(
            height=280,
            margin=dict(t=10, b=10, l=10, r=10),
            legend=dict(orientation="h"),
            xaxis_title="Date",
            yaxis_title="Value"
        )
        st.plotly_chart(fig_trend, use_container_width=True)