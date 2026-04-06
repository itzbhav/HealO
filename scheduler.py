"""
scheduler.py — HealO Daily Intelligence Loop
Runs once daily. For each patient:
  1. Pulls real message logs from healo.db
  2. Builds live features (streak, latency, skip rate)
  3. Scores dropout risk using trained XGBoost model
  4. RL Contextual Bandit picks the right intervention
  5. Sends WhatsApp ONLY to MY_TEST_NUMBER via Twilio
  6. Writes risk score + action back to DB for dashboard
"""

import sqlite3
import pickle
import os
import numpy as np
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from twilio.rest import Client
import vowpalwabbit as vw

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────
DB_PATH        = "healo.db"
MODEL_PATH     = "dropout_model.pkl"
TWILIO_SID     = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM    = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
MY_TEST_NUMBER = os.getenv("MY_TEST_NUMBER")   # only this number gets real messages

FEATURE_COLS = [
    "reply_rate", "streak", "weekend_skip_rate",
    "avg_latency_min", "days_since_reply", "med_taken_rate",
    "latency_drift", "recent_reply_rate", "disease_enc"
]

ACTIONS = {
    1: "morning_reminder",
    2: "evening_reminder",
    3: "motivational_message",
    4: "escalate_to_doctor",
    5: "do_nothing"
}

ACTION_MESSAGES = {
    1: "Good morning! 🌅 Time for your medication. Reply YES once you\'ve taken it 💊",
    2: "Good evening! 🌙 Have you taken your medication today? Reply YES or NO 💊",
    3: "You\'re doing great! 💪 Every dose is a step towards better health. Reply YES if taken!",
    4: None,   # escalation — flag to doctor only, no message to patient
    5: None    # do nothing
}

DISEASE_ENC = {"Diabetes": 0, "Hypertension": 1, "TB": 2}

# ── DB Helpers ────────────────────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_daily_log_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_risk_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id   INTEGER NOT NULL,
            log_date     TEXT NOT NULL,
            risk_score   REAL,
            risk_label   TEXT,
            action_taken TEXT,
            message_sent TEXT,
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(patient_id, log_date)
        )
    """)
    conn.commit()
    conn.close()

# ── Live Feature Engineering ──────────────────────────────────────────────
def build_live_features(patient_id: int, disease: str) -> dict:
    conn = get_conn()
    logs = pd.read_sql_query("""
        SELECT message_type, message_content, sent_at,
               whatsapp_message_id as intent
        FROM message_logs
        WHERE patient_id = ?
        ORDER BY sent_at ASC
    """, conn, params=(patient_id,))
    conn.close()

    if logs.empty:
        return None

    logs["sent_at"] = pd.to_datetime(logs["sent_at"], format="mixed")
    logs["day"]     = logs["sent_at"].dt.date
    logs["weekday"] = logs["sent_at"].dt.weekday

    outbound = logs[logs["message_type"] == "outbound"]
    inbound  = logs[logs["message_type"] == "inbound"]

    days_sent    = outbound["day"].unique()
    total_days   = max(len(days_sent), 1)
    inbound_days = inbound["day"].unique()
    reply_rate   = len(inbound_days) / total_days

    # Streak
    all_days = sorted(days_sent, reverse=True)
    streak = 0
    for i, d in enumerate(all_days):
        if i == 0:
            streak = 1; continue
        if (all_days[i-1] - d).days == 1:
            streak += 1
        else:
            break

    # Weekend skip rate
    wk_sent    = outbound[outbound["weekday"] >= 5]["day"].unique()
    wk_replied = inbound[inbound["weekday"] >= 5]["day"].unique()
    weekend_skip_rate = 1 - (len(wk_replied) / max(len(wk_sent), 1))

    # Latency
    latencies = []
    for _, row in outbound.iterrows():
        same_day = inbound[inbound["day"] == row["day"]]
        if not same_day.empty:
            lat = (same_day.iloc[0]["sent_at"] - row["sent_at"]).total_seconds() / 60
            if lat > 0:
                latencies.append(lat)
    avg_latency = float(np.mean(latencies)) if latencies else 480.0

    # Days since last reply
    days_since_reply = (max(days_sent) - max(inbound_days)).days                        if len(inbound_days) > 0 else total_days

    # Med taken rate
    med_taken_rate = len(inbound[inbound["intent"] == "medication_taken"]) / total_days

    # Latency drift
    if len(latencies) >= 6:
        mid = len(latencies) // 2
        latency_drift = float(np.mean(latencies[mid:]) - np.mean(latencies[:mid]))
    else:
        latency_drift = 0.0

    # Recent reply rate (last 14 days)
    recent_days        = sorted(days_sent, reverse=True)[:14]
    recent_reply_rate  = len(inbound[inbound["day"].isin(recent_days)]["day"].unique())                          / max(len(recent_days), 1)

    return {
        "reply_rate":        round(reply_rate, 4),
        "streak":            streak,
        "weekend_skip_rate": round(weekend_skip_rate, 4),
        "avg_latency_min":   round(avg_latency, 2),
        "days_since_reply":  days_since_reply,
        "med_taken_rate":    round(med_taken_rate, 4),
        "latency_drift":     round(latency_drift, 2),
        "recent_reply_rate": round(recent_reply_rate, 4),
        "disease_enc":       DISEASE_ENC.get(disease, 0),
    }

# ── Dropout Risk Prediction ───────────────────────────────────────────────
def predict_risk(features: dict) -> float:
    try:
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)
        X = np.array([[features.get(c, 0) for c in FEATURE_COLS]])
        return float(model.predict_proba(X)[0][1])
    except:
        if features.get("days_since_reply", 0) >= 3:   return 0.85
        if features.get("recent_reply_rate", 1) < 0.4: return 0.75
        return 0.3

# ── RL Action Selection ───────────────────────────────────────────────────
bandit = vw.Workspace("--cb 5 --epsilon 0.1 --quiet")

def select_action(features: dict, risk_score: float) -> int:
    if risk_score > 0.7 and features.get("days_since_reply", 0) >= 3:
        return 4  # escalate
    hour    = datetime.now().hour
    weekday = datetime.now().weekday()
    example = (
        f"| streak:{features.get('streak',0)} "
        f"skip:{features.get('weekend_skip_rate',0):.2f} "
        f"risk:{risk_score:.2f} "
        f"latency:{features.get('avg_latency_min',0):.0f} "
        f"days_silent:{features.get('days_since_reply',0)} "
        f"hour:{hour} weekday:{weekday}"
    )
    return max(1, min(5, int(bandit.predict(example))))

def update_bandit(features: dict, risk_score: float, action: int, reward: float):
    hour    = datetime.now().hour
    weekday = datetime.now().weekday()
    example = (
        f"{action}:{-reward:.2f}:0.2 | "
        f"streak:{features.get('streak',0)} "
        f"skip:{features.get('weekend_skip_rate',0):.2f} "
        f"risk:{risk_score:.2f} "
        f"latency:{features.get('avg_latency_min',0):.0f} "
        f"days_silent:{features.get('days_since_reply',0)} "
        f"hour:{hour} weekday:{weekday}"
    )
    bandit.learn(example)

# ── Twilio Sender ─────────────────────────────────────────────────────────
def send_whatsapp(to_number: str, message: str) -> bool:
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        msg = client.messages.create(
            from_=TWILIO_FROM,
            to=f"whatsapp:{to_number}",
            body=message
        )
        print(f"     ✅ Sent to {to_number} [{msg.sid[:8]}...]")
        return True
    except Exception as e:
        print(f"     ❌ Twilio error: {e}")
        return False

# ── DB Logger ─────────────────────────────────────────────────────────────
def log_to_db(patient_id, risk_score, action, message, log_date):
    risk_label = "High" if risk_score > 0.66 else "Medium" if risk_score > 0.33 else "Low"
    conn = get_conn()
    conn.execute("""
        INSERT INTO daily_risk_log
            (patient_id, log_date, risk_score, risk_label, action_taken, message_sent)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(patient_id, log_date) DO UPDATE SET
            risk_score=excluded.risk_score,
            risk_label=excluded.risk_label,
            action_taken=excluded.action_taken,
            message_sent=excluded.message_sent
    """, (patient_id, log_date, risk_score, risk_label, action, message or ""))
    conn.commit()
    conn.close()

# ── Main Daily Loop ───────────────────────────────────────────────────────
def run_daily():
    print(f"\n{'='*58}")
    print(f"🚀 HealO Daily Scheduler — {datetime.now().strftime('%d %b %Y %I:%M %p')}")
    print(f"{'='*58}")

    if not MY_TEST_NUMBER:
        print("⚠️  MY_TEST_NUMBER not set in .env — running in full DRY RUN mode")
        print("   Add MY_TEST_NUMBER=+91XXXXXXXXXX to .env to receive real messages\n")
    else:
        print(f"📱 Real messages will be sent to: {MY_TEST_NUMBER}")
        print(f"   All other patients: scored + logged (no message sent)\n")

    ensure_daily_log_table()
    today = datetime.now().date().isoformat()

    conn = get_conn()
    patients = conn.execute(
        "SELECT id, full_name, phone_number, disease FROM patients"
    ).fetchall()
    conn.close()

    print(f"👥 Scoring {len(patients)} patients...\n")

    stats = {"high": 0, "medium": 0, "low": 0,
             "real_sent": 0, "dry_run": 0,
             "escalated": 0, "skipped": 0}

    for p in patients:
        pid     = p["id"]
        name    = p["full_name"]
        phone   = p["phone_number"]
        disease = p["disease"] or "Diabetes"

        # 1. Build live features
        features = build_live_features(pid, disease)
        if features is None:
            stats["skipped"] += 1
            continue

        # 2. Predict risk
        risk_score = predict_risk(features)
        risk_label = "High" if risk_score > 0.66 else                      "Medium" if risk_score > 0.33 else "Low"
        stats[risk_label.lower()] += 1

        # 3. RL selects action
        action_id  = select_action(features, risk_score)
        action_str = ACTIONS[action_id]
        message    = ACTION_MESSAGES.get(action_id)

        print(f"  [{risk_label:6}] {name:<28} risk={risk_score:.2f}  → {action_str}")

        # 4. Send ONLY to MY_TEST_NUMBER — all others are dry run
        reward = 0.0
        if action_id in [1, 2, 3] and message:
            if phone == MY_TEST_NUMBER:
                # ✅ REAL SEND — this is your verified number
                sent = send_whatsapp(phone, message)
                if sent:
                    stats["real_sent"] += 1
                    reward = 0.5
                    # Log to message_logs
                    conn = get_conn()
                    conn.execute("""
                        INSERT INTO message_logs
                            (patient_id, message_type, message_content,
                             language, sent_at, delivery_status)
                        VALUES (?, 'outbound', ?, 'English', ?, 'sent')
                    """, (pid, message, datetime.now().isoformat()))
                    conn.commit()
                    conn.close()
            else:
                # 📋 DRY RUN — score + log, skip Twilio
                stats["dry_run"] += 1
                reward = 0.5  # optimistic prior for simulation

        elif action_id == 4:
            stats["escalated"] += 1

        # 5. Update RL bandit
        update_bandit(features, risk_score, action_id, reward)

        # 6. Write to daily_risk_log → powers the live dashboard
        log_to_db(pid, risk_score, action_str, message, today)

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{'─'*58}")
    print(f"📊 Daily Run Complete")
    print(f"   🔴 High risk:       {stats['high']}")
    print(f"   🟠 Medium risk:     {stats['medium']}")
    print(f"   🟢 Low risk:        {stats['low']}")
    print(f"   ✅ Real msg sent:   {stats['real_sent']}  (to {MY_TEST_NUMBER})")
    print(f"   📋 Dry run:         {stats['dry_run']}  (scored, no Twilio call)")
    print(f"   🚨 Escalated:       {stats['escalated']}")
    print(f"   ⏭️  Skipped:         {stats['skipped']}")
    print(f"\n🖥️  Dashboard updated → http://localhost:8501")
    print(f"{'='*58}\n")

if __name__ == "__main__":
    run_daily()
