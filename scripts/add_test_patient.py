# Run this ONCE: scripts/add_test_patient.py
import sqlite3
conn = sqlite3.connect('healo.db')
conn.execute("""
    INSERT OR IGNORE INTO patients 
    (full_name, phone_number, age, gender, language, disease, doctor_name, is_active)
    VALUES ('Bhavatharini', '+917418445928', 22, 'Female', 'English', 'Diabetes', 'Dr. Priya', 1)
""")
conn.execute("""
    INSERT INTO appointments
    (patient_id, doctor_name, specialty, appointment_date, appointment_time, status)
    SELECT id, 'Dr. Priya', 'Endocrinology', '2026-04-05', '10:00 AM', 'scheduled'
    FROM patients WHERE phone_number = '+917418445928'
""")
conn.commit()
print("✅ Test patient + appointment added!")
conn.close()