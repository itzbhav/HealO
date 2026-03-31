import sqlite3
import pandas as pd

DB_PATH = "healo.db"
PATIENTS_CSV = "synthetic_patients.csv"


def main():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_csv(PATIENTS_CSV)

    cursor = conn.cursor()

    for _, row in df.iterrows():
        cursor.execute("""
            INSERT OR IGNORE INTO patients
            (full_name, phone_number, age, gender, language, disease, doctor_name, expected_refill_date, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["full_name"],
            str(row["phone_number"]),
            int(row["age"]),
            row["gender"],
            row["language"],
            row["disease"],
            "Demo Doctor",
            None,
            1
        ))

    conn.commit()
    conn.close()
    print("Synthetic patients loaded into database.")
    

if __name__ == "__main__":
    main()