import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

DB_PATH = "healo.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def build_features():
    conn = sqlite3.connect(DB_PATH)

    # Load all message logs
    logs = pd.read_sql_query("""
        SELECT 
            m.patient_id,
            m.message_type,
            m.message_content,
            m.sent_at,
            m.whatsapp_message_id as intent
        FROM message_logs m
        WHERE m.patient_id IS NOT NULL
        ORDER BY m.patient_id, m.sent_at
    """, conn)

    patients = pd.read_sql_query("""
        SELECT id, disease, expected_refill_date FROM patients
    """, conn)
    conn.close()

    logs["sent_at"] = pd.to_datetime(logs["sent_at"], format="mixed")
    logs["day"] = logs["sent_at"].dt.date
    logs["hour"] = logs["sent_at"].dt.hour
    logs["weekday"] = logs["sent_at"].dt.weekday  # 0=Mon, 6=Sun

    outbound = logs[logs["message_type"] == "outbound"].copy()
    inbound  = logs[logs["message_type"] == "inbound"].copy()

    features_list = []

    for patient_id, group in outbound.groupby("patient_id"):
        days_sent = group["day"].unique()
        total_days = len(days_sent)

        if total_days < 7:
            continue  # not enough data

        # 1. Reply rate — how often did patient reply to outbound?
        patient_inbound = inbound[inbound["patient_id"] == patient_id]
        inbound_days = patient_inbound["day"].unique()
        reply_rate = len(inbound_days) / total_days

        # 2. Reply streak — consecutive days with a reply (from most recent)
        all_days_sorted = sorted(days_sent, reverse=True)
        streak = 0
        for i, d in enumerate(all_days_sorted):
            if i == 0:
                streak = 1
                continue
            prev = all_days_sorted[i - 1]
            if (prev - d).days == 1:
                streak += 1
            else:
                break

        # 3. Skip rate on weekends
        weekend_sent = group[group["weekday"] >= 5]["day"].unique()
        weekend_replied = patient_inbound[patient_inbound["weekday"] >= 5]["day"].unique()
        weekend_skip_rate = 1 - (len(weekend_replied) / max(len(weekend_sent), 1))

        # 4. Average reply latency in minutes
        latencies = []
        for _, out_row in group.iterrows():
            same_day_replies = patient_inbound[patient_inbound["day"] == out_row["day"]]
            if not same_day_replies.empty:
                lat = (same_day_replies.iloc[0]["sent_at"] - out_row["sent_at"]).total_seconds() / 60
                if lat > 0:
                    latencies.append(lat)
        avg_latency = np.mean(latencies) if latencies else 480  # default 8hrs if no reply

        # 5. Days since last response
        if len(inbound_days) > 0:
            last_reply = max(inbound_days)
            last_sent  = max(days_sent)
            days_since_reply = (last_sent - last_reply).days
        else:
            days_since_reply = total_days

        # 6. Medication taken rate (intent = medication_taken)
        med_taken = patient_inbound[patient_inbound["intent"] == "medication_taken"]
        med_taken_rate = len(med_taken) / max(total_days, 1)

        # 7. Latency trend — is latency getting worse over time? (drift)
        if len(latencies) >= 6:
            first_half = np.mean(latencies[:len(latencies)//2])
            second_half = np.mean(latencies[len(latencies)//2:])
            latency_drift = second_half - first_half  # positive = getting slower
        else:
            latency_drift = 0.0

        # 8. Label — dropout = reply_rate < 0.4 in last 14 days
        recent_days = sorted(days_sent, reverse=True)[:14]
        recent_inbound = patient_inbound[patient_inbound["day"].isin(recent_days)]
        recent_reply_rate = len(recent_inbound["day"].unique()) / max(len(recent_days), 1)
        dropout_label = 1 if recent_reply_rate < 0.40 else 0

        features_list.append({
            "patient_id":        patient_id,
            "total_days":        total_days,
            "reply_rate":        round(reply_rate, 4),
            "streak":            streak,
            "weekend_skip_rate": round(weekend_skip_rate, 4),
            "avg_latency_min":   round(avg_latency, 2),
            "days_since_reply":  days_since_reply,
            "med_taken_rate":    round(med_taken_rate, 4),
            "latency_drift":     round(latency_drift, 2),
            "recent_reply_rate": round(recent_reply_rate, 4),
            "dropout_label":     dropout_label,
        })

    df = pd.DataFrame(features_list)

    # Merge disease info
    df = df.merge(patients[["id", "disease"]], left_on="patient_id", right_on="id", how="left")
    df = df.drop(columns=["id"])

    # Save
    df.to_csv("patient_features.csv", index=False)

    print(f"✅ Features built for {len(df)} patients")
    print(f"   Dropout rate in dataset: {df['dropout_label'].mean()*100:.1f}%")
    print(f"\nFeature columns: {list(df.columns)}")
    print(f"\nSample (first 3 rows):")
    print(df.head(3).to_string(index=False))
    print(f"\n📁 Saved to: patient_features.csv")
    print(f"   Next step: python train_model.py")

if __name__ == "__main__":
    print("🔧 Building features from message logs...")
    build_features()