import sqlite3

conn = sqlite3.connect('healo.db')

existing = conn.execute("SELECT id FROM patients WHERE phone_number LIKE '%7418445928%'").fetchone()

if existing:
    pid = existing[0]
    conn.execute('UPDATE patients SET is_active=1 WHERE id=?', (pid,))
    conn.commit()
    print(f'Already exists. Patient ID: {pid}')
else:
    conn.execute(
        """INSERT INTO patients (full_name, phone_number, age, gender, language, disease, doctor_name, expected_refill_date, is_active, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,1,datetime('now'),datetime('now'))""",
        ('Bhavana Nair', '+917418445928', 22, 'Female', 'English', 'Diabetes Type 2', 'Dr. Rao', '2026-04-20')
    )
    conn.commit()
    pid = conn.execute("SELECT id FROM patients WHERE phone_number='+917418445928'").fetchone()[0]
    print(f'Inserted! Patient ID: {pid}')

med = conn.execute('SELECT id FROM medications WHERE patient_id=?', (pid,)).fetchone()
if not med:
    conn.execute(
        """INSERT INTO medications (patient_id, medication_name, dosage, frequency, schedule_time, start_date, end_date)
           VALUES (?,?,?,?,?,date('now'),date('now','+90 days'))""",
        (pid, 'Metformin', '500mg', 'twice_daily', '09:00')
    )
    conn.commit()
    print('Medication added: Metformin 500mg')
else:
    print(f'Medication already exists: {med}')

print('All done! Patient is registered and active.')
conn.close()
