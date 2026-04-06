"""
dashboard.py — HealO Doctor Dashboard (LIVE VERSION)
Reads directly from healo.db — no static CSVs needed.
Shows real bot data + daily risk scores from scheduler.
"""

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import json
import pickle
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="HealO — Doctor Dashboard",
    page_icon="🩺",
    layout="wide"
)

DB_PATH    = "healo.db"
MODEL_PATH = "dropout_model.pkl"

st.markdown("""
<style>
.header-bar {
    background: linear-gradient(135deg, #01696f, #0c4e54);
    padding: 20px 30px; border-radius: 12px;
    color: white; margin-bottom: 24px;
}
.stMetric { background: white; border-radius: 10px; padding: 12px; }
</style>
""", unsafe_allow_html=True)

# ── DB Connection ─────────────────────────────────────────────────────────
def get_conn():
    return sqlite3.connect(DB_PATH)

# ── Live Data Loader ──────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_live_data():
    conn = get_conn()

    patients = pd.read_sql_query("SELECT * FROM patients", conn)

    # Check if daily_risk_log exists (created by scheduler)
    tables = pd.read_sql_query(
        "SELECT name FROM sqlite_master WHERE type='table'", conn
    )["name"].tolist()

    if "daily_risk_log" in tables:
        today = datetime.now().date().isoformat()
        risk_log = pd.read_sql_query("""
            SELECT patient_id, risk_score, risk_label, action_taken,
                   message_sent, log_date
            FROM daily_risk_log
            WHERE log_date = ?
        """, conn, params=(today,))

        if risk_log.empty:
            # Fall back to most recent available date
            risk_log = pd.read_sql_query("""
                SELECT patient_id, risk_score, risk_label, action_taken,
                       message_sent, log_date
                FROM daily_risk_log
                WHERE log_date = (SELECT MAX(log_date) FROM daily_risk_log)
            """, conn)
    else:
        risk_log = pd.DataFrame()

    # Message logs — last 14 days per patient
    msg_logs = pd.read_sql_query("""
        SELECT patient_id, message_type, message_content,
               sent_at, whatsapp_message_id as intent
        FROM message_logs
        WHERE sent_at >= datetime('now', '-14 days')
        ORDER BY sent_at DESC
    """, conn)

    # Historical trend — reply rate per day (last 30 days)
    trend = pd.read_sql_query("""
        SELECT
            DATE(sent_at) as day,
            COUNT(DISTINCT patient_id) as active_patients
        FROM message_logs
        WHERE message_type = 'inbound'
          AND sent_at >= datetime('now', '-30 days')
        GROUP BY DATE(sent_at)
        ORDER BY day
    """, conn)

    conn.close()

    # Build master patient df
    df = patients.copy()

    if not risk_log.empty:
        df = df.merge(
            risk_log[["patient_id","risk_score","risk_label",
                      "action_taken","message_sent","log_date"]],
            left_on="id", right_on="patient_id", how="left"
        )
        df["risk_score"] = df["risk_score"].fillna(0.5)
    else:
        # Fall back to CSV if scheduler hasn't run yet
        try:
            feat = pd.read_csv("patient_features.csv")
            rl   = pd.read_csv("rl_results.csv")
            feat = feat.merge(
                rl[["patient_id","action","responded","reward","risk_score"]],
                on="patient_id", how="left"
            )
            feat["risk_score"] = feat["risk_score"].fillna(0.5)
            df = df.merge(
                feat[["patient_id","risk_score","action",
                      "reply_rate","streak","days_since_reply",
                      "med_taken_rate","recent_reply_rate"]],
                left_on="id", right_on="patient_id", how="left"
            )
            df.rename(columns={"action": "action_taken"}, inplace=True)
        except:
            df["risk_score"]   = 0.5
            df["action_taken"] = "unknown"

    df["risk_score"]   = pd.to_numeric(df["risk_score"], errors="coerce").fillna(0.5)
    df["risk_label"]   = pd.cut(df["risk_score"],
                                 bins=[-0.01, 0.33, 0.66, 1.01],
                                 labels=["Low", "Medium", "High"])
    df["risk_score_pct"] = (df["risk_score"] * 100).round(1)

    return df, msg_logs, trend

df, msg_logs, trend = load_live_data()

# ── Live / CSV mode indicator ─────────────────────────────────────────────
conn = get_conn()
tables = pd.read_sql_query(
    "SELECT name FROM sqlite_master WHERE type='table'", conn
)["name"].tolist()
conn.close()
live_mode = "daily_risk_log" in tables

# ── Header ────────────────────────────────────────────────────────────────
mode_badge = "🟢 LIVE" if live_mode else "🟡 DEMO (run scheduler.py to go live)"
st.markdown(f"""
<div class="header-bar">
    <h1 style="margin:0; font-size:1.8rem;">🩺 HealO — Doctor Dashboard</h1>
    <p style="margin:4px 0 0; opacity:0.85;">
        Medication Adherence · Dropout Prediction · RL Interventions &nbsp;|&nbsp; {mode_badge}
    </p>
</div>
""", unsafe_allow_html=True)

# ── KPIs ──────────────────────────────────────────────────────────────────
total     = len(df)
high_risk = int((df["risk_label"] == "High").sum())
med_risk  = int((df["risk_label"] == "Medium").sum())
escalated = int((df.get("action_taken","") == "escalate_to_doctor").sum())             if "action_taken" in df.columns else 0

# Reply rate from live message logs
if not msg_logs.empty:
    today_logs  = msg_logs[msg_logs["message_type"] == "inbound"]
    resp_rate   = len(today_logs["patient_id"].unique()) / max(total, 1) * 100
else:
    resp_rate   = float(df["reply_rate"].mean() * 100) if "reply_rate" in df.columns else 0.0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("👥 Total Patients",  total)
c2.metric("🔴 High Risk",       high_risk, delta=f"{high_risk/total*100:.1f}%")
c3.metric("🟠 Medium Risk",     med_risk,  delta=f"{med_risk/total*100:.1f}%")
c4.metric("📨 Response Rate",   f"{resp_rate:.1f}%")
c5.metric("🚨 Escalated",       escalated)

st.divider()

# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔍 Filters")
    risk_filter    = st.multiselect("Risk Level",
                                    ["High","Medium","Low"],
                                    default=["High","Medium"])
    disease_filter = st.multiselect("Disease",
                                    df["disease"].dropna().unique().tolist(),
                                    default=df["disease"].dropna().unique().tolist())
    doctor_filter  = st.multiselect("Doctor",
                                    df["doctor_name"].dropna().unique().tolist(),
                                    default=df["doctor_name"].dropna().unique().tolist())
    search = st.text_input("🔎 Search patient name")
    st.divider()
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Updated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}")

# ── Apply Filters ─────────────────────────────────────────────────────────
filtered = df.copy()
if risk_filter:
    filtered = filtered[filtered["risk_label"].isin(risk_filter)]
if disease_filter:
    filtered = filtered[filtered["disease"].isin(disease_filter)]
if doctor_filter and "doctor_name" in filtered.columns:
    filtered = filtered[filtered["doctor_name"].isin(doctor_filter)]
if search:
    filtered = filtered[filtered["full_name"].str.contains(search, case=False, na=False)]
filtered = filtered.sort_values("risk_score", ascending=False)

# ── Trend Chart (full width) ──────────────────────────────────────────────
if not trend.empty:
    st.subheader("📈 Patient Engagement — Last 30 Days")
    fig_trend = px.area(trend, x="day", y="active_patients",
                        color_discrete_sequence=["#01696f"])
    fig_trend.update_layout(height=180, margin=dict(t=0,b=0,l=0,r=0),
                             xaxis_title="", yaxis_title="Patients Replied")
    st.plotly_chart(fig_trend, use_container_width=True)
    st.divider()

# ── Patient Table + Charts ────────────────────────────────────────────────
left, right = st.columns([2, 1])

with left:
    st.subheader(f"🚨 Patient Risk List ({len(filtered)} patients)")

    show_cols = ["full_name","disease","risk_label","risk_score_pct","doctor_name"]
    opt_cols  = ["streak","days_since_reply","reply_rate","action_taken"]
    for c in opt_cols:
        if c in filtered.columns:
            show_cols.append(c)

    show = filtered[show_cols].copy()
    col_rename = {
        "full_name": "Name", "disease": "Disease",
        "risk_label": "Risk", "risk_score_pct": "Score %",
        "doctor_name": "Doctor", "streak": "Streak",
        "days_since_reply": "Days Silent",
        "reply_rate": "Reply Rate", "action_taken": "Suggested Action"
    }
    show.rename(columns=col_rename, inplace=True)
    if "Reply Rate" in show.columns:
        show["Reply Rate"] = (show["Reply Rate"] * 100).round(1).astype(str) + "%"

    def highlight(row):
        if row.get("Risk") == "High":   return ["background-color:#fff5f5"]*len(row)
        if row.get("Risk") == "Medium": return ["background-color:#fff8f0"]*len(row)
        return [""]*len(row)

    st.dataframe(show.style.apply(highlight, axis=1),
                 use_container_width=True, height=400)

with right:
    st.subheader("📊 Risk Distribution")
    rc = df["risk_label"].value_counts().reset_index()
    rc.columns = ["Risk","Count"]
    fig1 = px.pie(rc, values="Count", names="Risk", hole=0.45,
                  color="Risk",
                  color_discrete_map={"High":"#dc3545","Medium":"#fd7e14","Low":"#28a745"})
    fig1.update_layout(margin=dict(t=0,b=0,l=0,r=0), height=200)
    st.plotly_chart(fig1, use_container_width=True)

    st.subheader("🤖 RL Actions Today")
    if "action_taken" in df.columns:
        ac = df["action_taken"].value_counts().reset_index()
        ac.columns = ["Action","Count"]
        ac["Action"] = ac["Action"].str.replace("_"," ").str.title()
        fig2 = px.bar(ac, x="Count", y="Action", orientation="h",
                      color="Count", color_continuous_scale="Teal")
        fig2.update_layout(margin=dict(t=0,b=0,l=0,r=0), height=200,
                           coloraxis_showscale=False)
        st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ── Disease Risk ──────────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    st.subheader("🦠 Avg Dropout Risk by Disease")
    dr = df.groupby("disease")["risk_score"].mean().reset_index()
    dr.columns = ["Disease","Avg Risk"]
    dr = dr.sort_values("Avg Risk", ascending=True)
    fig3 = px.bar(dr, x="Avg Risk", y="Disease", orientation="h",
                  color="Avg Risk", color_continuous_scale="RdYlGn_r")
    fig3.update_layout(height=250, margin=dict(t=0,b=0,l=0,r=0),
                       coloraxis_showscale=False)
    st.plotly_chart(fig3, use_container_width=True)

with col2:
    try:
        with open("feature_importance.json") as f:
            importance = json.load(f)
        st.subheader("📈 Feature Importance (XGBoost)")
        imp_df = pd.DataFrame(list(importance.items()), columns=["Feature","Importance"])
        imp_df = imp_df.sort_values("Importance", ascending=True).tail(8)
        imp_df["Feature"] = imp_df["Feature"].str.replace("_"," ").str.title()
        fig4 = px.bar(imp_df, x="Importance", y="Feature", orientation="h",
                      color="Importance", color_continuous_scale="Teal")
        fig4.update_layout(height=250, margin=dict(t=0,b=0,l=0,r=0),
                           coloraxis_showscale=False)
        st.plotly_chart(fig4, use_container_width=True)
    except:
        st.info("Run train_model.py to see feature importance.")

st.divider()

# ── Patient Deep Dive ─────────────────────────────────────────────────────
st.subheader("🔎 Patient Deep Dive")
names = filtered["full_name"].dropna().tolist()
if names:
    selected = st.selectbox("Select a patient", names)
    row = filtered[filtered["full_name"] == selected].iloc[0]

    d1,d2,d3,d4 = st.columns(4)
    d1.metric("Disease",      row.get("disease","—"))
    d2.metric("Risk Score",   f"{row['risk_score_pct']}%")
    d3.metric("Streak",       f"{int(row.get('streak',0))} days" if "streak" in row else "—")
    d4.metric("Days Silent",  f"{int(row.get('days_since_reply',0))} days" if "days_since_reply" in row else "—")

    e1,e2,e3 = st.columns(3)
    e1.metric("Reply Rate",   f"{row.get('reply_rate',0)*100:.1f}%" if "reply_rate" in row else "—")
    e2.metric("Med Taken",    f"{row.get('med_taken_rate',0)*100:.1f}%" if "med_taken_rate" in row else "—")
    e3.metric("Action",       str(row.get("action_taken","—")).replace("_"," ").title())

    icon = {"High":"🔴","Medium":"🟠","Low":"🟢"}.get(str(row["risk_label"]),"⚪")
    st.info(
        f"{icon} **{selected}** — {row.get('disease','—')} patient. "
        f"Dropout risk: **{row['risk_score_pct']}%**. "
        f"Silent for {int(row.get('days_since_reply',0))} days. "
        f"Recommended: **{str(row.get('action_taken','—')).replace('_',' ').title()}**."
    )

    # Message history from live DB
    st.markdown("#### 💬 Recent Message History (last 14 days)")
    pid = int(row["id"])
    patient_msgs = msg_logs[msg_logs["patient_id"] == pid].copy() if not msg_logs.empty else pd.DataFrame()
    if not patient_msgs.empty:
        patient_msgs = patient_msgs.sort_values("sent_at", ascending=False).head(20)
        for _, m in patient_msgs.iterrows():
            direction = "➡️ Bot" if m["message_type"] == "outbound" else "⬅️ Patient"
            st.markdown(f"`{m['sent_at'][:16]}` **{direction}**: {m['message_content']}")
    else:
        st.caption("No recent messages found. Run scheduler.py to send today's messages.")
else:
    st.warning("No patients match your current filters.")
