import sqlite3
from datetime import datetime

DB_PATH = "healo.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Patient ──────────────────────────────────────────────
def get_patient_by_phone(phone: str):
    """Look up patient by phone number"""
    phone_clean = phone.replace("whatsapp:", "").replace("+", "").strip()
    conn = get_conn()
    patient = conn.execute("""
        SELECT * FROM patients WHERE phone_number = ?
    """, (phone_clean,)).fetchone()
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
def log_medication_taken(patient_id: int, taken: bool):
    """Log whether patient took medication today"""
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO responses
            (patient_id, response_type, response_value, created_at)
            VALUES (?, 'medication', ?, ?)
        """, (patient_id, 'yes' if taken else 'no', datetime.now()))
        conn.commit()
    except Exception as e:
        print(f"[log_medication_taken] Warning: {e}")
    finally:
        conn.close()