import random
import pandas as pd
from faker import Faker
import os

fake = Faker('en_IN')

PATIENT_TYPES = ["adherent", "early_dropout", "erratic", "recoverer"]
WEIGHTS = [0.30, 0.30, 0.25, 0.15]

REPLY_PROBS = {
    "adherent": 0.95,
    "early_dropout": 0.70,
    "erratic": 0.80,
    "recoverer": 0.60
}

DROPOUT_DAYS = {
    "adherent": None,
    "early_dropout": random.randint(7, 21),
    "erratic": None,
    "recoverer": random.randint(14, 28)
}


def generate_synthetic_data(num_patients: int = 500):
    patients = []
    for i in range(num_patients):
        patient_type = random.choices(PATIENT_TYPES, weights=WEIGHTS)[0]

        patient = {
            "full_name": fake.name(),
            "phone_number": f"91{random.randint(9000000000, 9999999999)}",
            "age": random.randint(35, 70),
            "gender": random.choice(["Male", "Female"]),
            "language": random.choice(["Tamil", "Hindi", "English"]),
            "disease": random.choice(["Diabetes", "Hypertension", "TB"]),
            "patient_type": patient_type,
            "reply_prob": REPLY_PROBS[patient_type],
            "dropout_day": DROPOUT_DAYS[patient_type]
        }
        patients.append(patient)

    df = pd.DataFrame(patients)

    # Save to project root (where you run from)
    save_path = os.path.join(os.getcwd(), "synthetic_patients.csv")
    df.to_csv(save_path, index=False)

    print(f"Generated {len(df)} synthetic patients")
    print(f"Saved to: {save_path}")
    print(df.head())
    return df


if __name__ == "__main__":
    generate_synthetic_data(500)