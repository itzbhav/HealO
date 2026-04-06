import sqlite3
import random
from datetime import datetime, timedelta

DB_PATH = "healo.db"
SIMULATION_DAYS = 60
START_DATE = datetime.now() - timedelta(days=SIMULATION_DAYS)

ARCHETYPES = {
    "adherent":     {"base_reply_rate": 0.90, "dropout_day": None,    "weekend_penalty": 0.05, "recovery_day": None},
    "early_dropout":{"base_reply_rate": 0.85, "dropout_day": 14,      "weekend_penalty": 0.10, "recovery_day": None},
    "erratic":      {"base_reply_rate": 0.70, "dropout_day": None,    "weekend_penalty": 0.40, "recovery_day": None},
    "recoverer":    {"base_reply_rate": 0.80, "dropout_day": 20,      "weekend_penalty": 0.10, "recovery_day": 35},
}

INBOUND_REPLIES = {
    "yes":   ["Yes took it", "Done!", "Took my meds", "Yes", "Haan liya", "Took it this morning", "✅"],
    "no":    ["Not yet", "Forgot", "Will take later", "Nahi liya", "Missed it today"],
    "short": ["ok", "k", "yes", "no", "done"],
}

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_archetype(patient_id: int) -> str:
    archetypes = list(ARCHETYPES.keys())
    # Distribute: 40% adherent, 25% early_dropout, 20% erratic, 15% recoverer
    weights = [0.40, 0.25, 0.20, 0.15]
    random.seed(patient_id)
    return random.choices(archetypes, weights=weights)[0]

def simulate_reply(archetype_cfg, day_num, weekday):
    cfg = archetype_cfg

    # Check dropout
    if cfg["dropout_day"] and day_num >= cfg["dropout_day"]:
        # Check recovery
        if cfg["recovery_day"] and day_num >= cfg["recovery_day"]:
            reply_rate = 0.75  # recovered
        else:
            reply_rate = 0.05  # dropped out
    else:
        reply_rate = cfg["base_reply_rate"]

    # Weekend penalty
    if weekday >= 5:  # Saturday=5, Sunday=6
        reply_rate -= cfg["weekend_penalty"]

    reply_rate = max(0.0, min(1.0, reply_rate))
    replied = random.random() < reply_rate

    if not replied:
        return None, None

    # Choose reply content
    if random.random() < 0.65:
        content = random.choice(INBOUND_REPLIES["yes"])
        intent = "medication_taken"
    elif random.random() < 0.5:
        content = random.choice(INBOUND_REPLIES["no"])
        intent = "medication_missed"
    else:
        content = random.choice(INBOUND_REPLIES["short"])
        intent = "general"

    return content, intent

def simulate_all_patients():
    conn = get_conn()
    patients = conn.execute("SELECT id, phone_number FROM patients").fetchall()

    logs = []

    for patient in patients:
        patient_id = patient["id"]
        archetype_name = get_archetype(patient_id)
        archetype_cfg = ARCHETYPES[archetype_name]

        random.seed(patient_id * 42)

        for day_num in range(SIMULATION_DAYS):
            current_date = START_DATE + timedelta(days=day_num)
            weekday = current_date.weekday()

            # Outbound message (bot sends reminder) — morning time
            send_hour = random.randint(8, 10)
            sent_at = current_date.replace(hour=send_hour, minute=random.randint(0, 59), second=0)

            logs.append((
                patient_id, "outbound",
                "Did you take your medication today? Reply YES or NO 💊",
                "English", sent_at, "delivered", None
            ))

            # Inbound reply (patient responds or not)
            reply_content, intent = simulate_reply(archetype_cfg, day_num, weekday)

            if reply_content:
                # Reply latency: 5min to 8 hours
                latency_minutes = random.randint(5, 480)
                replied_at = sent_at + timedelta(minutes=latency_minutes)

                logs.append((
                    patient_id, "inbound",
                    reply_content,
                    "English", replied_at, "delivered", intent
                ))

    # Bulk insert
    conn.executemany("""
        INSERT INTO message_logs
        (patient_id, message_type, message_content, language, sent_at, delivery_status, whatsapp_message_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, logs)

    conn.commit()
    conn.close()
    return len(logs), len(patients)

if __name__ == "__main__":
    print("🚀 Starting patient journey simulation...")
    total_logs, total_patients = simulate_all_patients()
    print(f"✅ Done! Generated {total_logs:,} message logs for {total_patients} patients over {SIMULATION_DAYS} days.")
    print(f"   Archetype distribution (seeded per patient_id):")
    print(f"   - Adherent:      ~40% ({int(total_patients*0.40)} patients)")
    print(f"   - Early dropout: ~25% ({int(total_patients*0.25)} patients)")
    print(f"   - Erratic:       ~20% ({int(total_patients*0.20)} patients)")
    print(f"   - Recoverer:     ~15% ({int(total_patients*0.15)} patients)")
    print(f"\n   Next step: run scripts/build_features.py to extract ML features!")