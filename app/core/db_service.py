import sqlite3
from datetime import datetime

DB_PATH = "healo.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Patient ──────────────────────────────────────────────
def get_patient_by_phone(phone: str):
    """Look up patient by phone number.
    Tries both '+91...' and '91...' forms so it matches regardless of
    how the number is stored or how Twilio sends it.
    """
    # Normalise: strip whatsapp: prefix and whitespace
    stripped = phone.replace("whatsapp:", "").strip()
    # Build both variants: with and without leading +
    with_plus    = stripped if stripped.startswith("+") else "+" + stripped
    without_plus = stripped.lstrip("+")

    conn = get_conn()
    patient = conn.execute("""
        SELECT * FROM patients
        WHERE phone_number = ? OR phone_number = ?
        LIMIT 1
    """, (with_plus, without_plus)).fetchone()
    conn.close()
    return dict(patient) if patient else None


# ── Message Logging ───────────────────────────────────────
def log_message(phone: str, direction: str, message_text: str,
                intent: str = None, patient_id: int = None):
    """Log every inbound/outbound WhatsApp message"""
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO message_logs 
            (patient_id, message_type, message_content, language, sent_at, delivery_status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            patient_id,
            direction,
            message_text,
            'English',
            datetime.now(),
            'delivered'
        ))
        conn.commit()
    except Exception as e:
        print(f"[log_message] Warning: {e}")
    finally:
        conn.close()


# ── Appointments ──────────────────────────────────────────
def get_upcoming_appointment(patient_id: int):
    """Get the next scheduled appointment for a patient"""
    conn = get_conn()
    appt = conn.execute("""
        SELECT * FROM appointments
        WHERE patient_id = ? AND status = 'scheduled'
        ORDER BY appointment_date ASC, appointment_time ASC
        LIMIT 1
    """, (patient_id,)).fetchone()
    conn.close()
    return dict(appt) if appt else None


def confirm_appointment(patient_id: int):
    """Confirm the next scheduled appointment"""
    conn = get_conn()
    conn.execute("""
        UPDATE appointments SET status = 'confirmed', updated_at = ?
        WHERE patient_id = ? AND status = 'scheduled'
    """, (datetime.now(), patient_id))
    conn.commit()
    conn.close()


def cancel_appointment(patient_id: int):
    """Cancel the next scheduled appointment"""
    conn = get_conn()
    conn.execute("""
        UPDATE appointments SET status = 'cancelled', updated_at = ?
        WHERE patient_id = ? AND status = 'scheduled'
    """, (datetime.now(), patient_id))
    conn.commit()
    conn.close()


def book_appointment(patient_id: int, doctor_name: str,
                     specialty: str, date: str, time: str):
    """Book a new appointment"""
    conn = get_conn()
    conn.execute("""
        INSERT INTO appointments 
        (patient_id, doctor_name, specialty, appointment_date, appointment_time, status)
        VALUES (?, ?, ?, ?, ?, 'scheduled')
    """, (patient_id, doctor_name, specialty, date, time))
    conn.commit()
    conn.close()


# ── Medication Logging ────────────────────────────────────
def log_medication_taken(patient_id: int, taken: bool, raw_text: str = ""):
    """Log whether patient took medication today into the responses table."""
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO responses
            (patient_id, raw_text, normalized_label, sentiment, intent, received_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            patient_id,
            raw_text or ("taken" if taken else "missed"),
            "yes" if taken else "no",
            "positive" if taken else "negative",
            "medication_taken" if taken else "medication_missed",
            datetime.now(),
        ))
        conn.commit()
    except Exception as e:
        print(f"[log_medication_taken] Warning: {e}")
    finally:
        conn.close()


def log_response(patient_id: int, raw_text: str, normalized_label: str,
                 intent: str, sentiment: str = "neutral"):
    """Generic response logger for any inbound patient message."""
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO responses
            (patient_id, raw_text, normalized_label, sentiment, intent, received_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (patient_id, raw_text, normalized_label, sentiment, intent, datetime.now()))
        conn.commit()
    except Exception as e:
        print(f"[log_response] Warning: {e}")
    finally:
        conn.close()