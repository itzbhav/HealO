import sqlite3
import pandas as pd
import random
from datetime import datetime, timedelta

DB_PATH = "healo.db"
PATIENTS_CSV = "synthetic_patients.csv"

MESSAGE_TEMPLATES = {
    "English": "Did you take your medicine today? Reply YES or NO.",
    "Tamil": "நீங்கள் இன்று உங்கள் மருந்தை எடுத்தீர்களா? YES அல்லது NO என்று பதிலளிக்கவும்.",
    "Hindi": "क्या आपने आज अपनी दवा ली? YES या NO में जवाब दें।"
}


def generate_reply(patient_type, day_number, weekend=False):
    if patient_type == "adherent":
        prob = 0.95 if not weekend else 0.8
    elif patient_type == "early_dropout":
        if day_number > 14:
            prob = 0.15
        else:
            prob = 0.7
    elif patient_type == "erratic":
        prob = 0.8 if not weekend else 0.35
    elif patient_type == "recoverer":
        if 10 <= day_number <= 18:
            prob = 0.2
        elif day_number > 18:
            prob = 0.75
        else:
            prob = 0.65
    else:
        prob = 0.5

    if random.random() < prob:
        return random.choice(["YES", "Yes", "yes", "Taken", "Done"])
    return None


def main():
    conn = sqlite3.connect(DB_PATH)
    patients_df = pd.read_csv(PATIENTS_CSV)

    cursor = conn.cursor()

    cursor.execute("DELETE FROM responses")
    cursor.execute("DELETE FROM message_logs")
    conn.commit()

    start_date = datetime(2026, 3, 1, 9, 0, 0)

    patient_id_map = {}
    db_patients = pd.read_sql_query("SELECT id, phone_number FROM patients", conn)
    for _, row in db_patients.iterrows():
        patient_id_map[str(row["phone_number"])] = row["id"]

    for _, patient in patients_df.iterrows():
        phone = str(patient["phone_number"])
        patient_id = patient_id_map.get(phone)

        if not patient_id:
            continue

        language = patient["language"]
        patient_type = patient["patient_type"]

        for day in range(30):
            send_time = start_date + timedelta(days=day)
            is_weekend = send_time.weekday() >= 5

            message_content = MESSAGE_TEMPLATES.get(language, MESSAGE_TEMPLATES["English"])

            cursor.execute("""
                INSERT INTO message_logs (patient_id, message_type, message_content, language, sent_at, delivery_status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                patient_id,
                "reminder",
                message_content,
                language,
                send_time.isoformat(sep=" "),
                "sent"
            ))

            message_log_id = cursor.lastrowid

            reply_text = generate_reply(patient_type, day + 1, is_weekend)

            if reply_text:
                latency_seconds = random.randint(300, 7200)
                received_at = send_time + timedelta(seconds=latency_seconds)

                cursor.execute("""
                    INSERT INTO responses (
                        patient_id, message_log_id, raw_text, normalized_label,
                        sentiment, intent, received_at, reply_latency_seconds
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    patient_id,
                    message_log_id,
                    reply_text,
                    "YES",
                    "positive",
                    "dose_confirmed",
                    received_at.isoformat(sep=" "),
                    latency_seconds
                ))

    conn.commit()
    conn.close()
    print("Synthetic message logs and responses inserted successfully.")


if __name__ == "__main__":
    main()