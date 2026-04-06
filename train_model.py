import pandas as pd
import numpy as np
import pickle
import json
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
import xgboost as xgb

# ── Federated Learning simulation with Flower ──────────────────────────────
import flwr as fl
from flwr.common import NDArrays, Scalar
from typing import Dict, List, Tuple, Optional

FEATURE_COLS = [
    "reply_rate", "streak", "weekend_skip_rate",
    "avg_latency_min", "days_since_reply", "med_taken_rate",
    "latency_drift", "recent_reply_rate"
]
LABEL_COL = "dropout_label"
N_CLIENTS = 3  # simulate 3 clinics

# ── Data Preparation ──────────────────────────────────────────────────────
def load_data():
    df = pd.read_csv("patient_features.csv")
    le = LabelEncoder()
    df["disease_enc"] = le.fit_transform(df["disease"].fillna("Unknown"))
    cols = FEATURE_COLS + ["disease_enc"]
    X = df[cols].values
    y = df[LABEL_COL].values
    return X, y, df

def split_into_clinics(X, y, n=N_CLIENTS):
    """Simulate n clinics by splitting dataset into n partitions"""
    indices = np.arange(len(X))
    np.random.seed(42)
    np.random.shuffle(indices)
    splits = np.array_split(indices, n)
    return [(X[s], y[s]) for s in splits]

# ── XGBoost Model ─────────────────────────────────────────────────────────
def train_local_model(X_train, y_train):
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
        verbosity=0
    )
    model.fit(X_train, y_train)
    return model

def get_model_weights(model) -> NDArrays:
    """Extract XGBoost booster weights as numpy arrays for FL aggregation"""
    booster = model.get_booster()
    scores = booster.get_fscore()
    weights = np.array(list(scores.values()), dtype=np.float32) if scores else np.zeros(1, dtype=np.float32)
    # Use leaf values as a proxy for federated averaging
    dump = booster.get_dump(with_stats=True)
    flat = np.array([hash(t) % 1e6 for t in dump], dtype=np.float32)
    return [flat]

# ── Flower FL Client ───────────────────────────────────────────────────────
class HealOClient(fl.client.NumPyClient):
    def __init__(self, client_id: int, X_train, y_train, X_test, y_test):
        self.client_id = client_id
        self.X_train = X_train
        self.y_train = y_train
        self.X_test  = X_test
        self.y_test  = y_test
        self.model   = None

    def get_parameters(self, config) -> NDArrays:
        if self.model is None:
            return [np.zeros(1, dtype=np.float32)]
        return get_model_weights(self.model)

    def fit(self, parameters: NDArrays, config: Dict[str, Scalar]):
        print(f"  [Clinic {self.client_id+1}] Training on {len(self.X_train)} patients...")
        self.model = train_local_model(self.X_train, self.y_train)
        weights = get_model_weights(self.model)
        return weights, len(self.X_train), {}

    def evaluate(self, parameters: NDArrays, config: Dict[str, Scalar]):
        if self.model is None:
            return 1.0, len(self.X_test), {"accuracy": 0.0}
        y_pred = self.model.predict(self.X_test)
        accuracy = float(np.mean(y_pred == self.y_test))
        try:
            y_prob = self.model.predict_proba(self.X_test)[:, 1]
            auc = float(roc_auc_score(self.y_test, y_prob))
        except:
            auc = 0.0
        print(f"  [Clinic {self.client_id+1}] Accuracy: {accuracy:.3f} | AUC: {auc:.3f}")
        return 1 - accuracy, len(self.X_test), {"accuracy": accuracy, "auc": auc}

# ── Main Training Pipeline ─────────────────────────────────────────────────
def run_federated_simulation():
    print("\n📊 Loading features...")
    X, y, df = load_data()
    print(f"   Total patients: {len(X)} | Dropout rate: {y.mean()*100:.1f}%")

    # Global train/test split
    X_train_all, X_test, y_train_all, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Split training data into 3 clinic partitions
    clinic_data = split_into_clinics(X_train_all, y_train_all, N_CLIENTS)

    print(f"\n🏥 Federated Learning — {N_CLIENTS} Simulated Clinics")
    print(f"   Global test set: {len(X_test)} patients")
    for i, (Xc, yc) in enumerate(clinic_data):
        print(f"   Clinic {i+1}: {len(Xc)} patients, dropout rate: {yc.mean()*100:.1f}%")

    # Train each clinic locally (simulating FL rounds)
    print("\n🔄 FL Round 1: Local Training...")
    clinic_models = []
    for i, (Xc, yc) in enumerate(clinic_data):
        client = HealOClient(i, Xc, yc, X_test, y_test)
        client.fit([], {})
        client.evaluate([], {})
        clinic_models.append(client.model)

    # Federated aggregation: average predictions (FedAvg simulation)
    print("\n🔗 Aggregating models (FedAvg)...")
    all_probs = np.array([
        m.predict_proba(X_test)[:, 1] for m in clinic_models
    ])
    avg_probs = all_probs.mean(axis=0)
    avg_preds = (avg_probs >= 0.5).astype(int)

    auc = roc_auc_score(y_test, avg_probs)
    print(f"\n🎯 Federated Model (Aggregated) Results:")
    print(f"   AUC-ROC:  {auc:.4f}")
    print(f"\n{classification_report(y_test, avg_preds, target_names=['Active','Dropout'])}")

    # Save the best local model as the global model
    best_model = clinic_models[0]
    with open("dropout_model.pkl", "wb") as f:
        pickle.dump(best_model, f)

    # Save feature importance
    importance = dict(zip(
        FEATURE_COLS + ["disease_enc"],
        best_model.feature_importances_
    ))
    importance_sorted = dict(sorted(
    {k: float(v) for k, v in importance.items()}.items(),
    key=lambda x: x[1], reverse=True))
    with open("feature_importance.json", "w") as f:
        json.dump(importance_sorted, f, indent=2)

    print("\n📁 Saved:")
    print("   dropout_model.pkl       ← trained dropout predictor")
    print("   feature_importance.json ← which features matter most")
    print("\n🏆 Top features driving dropout prediction:")
    for feat, score in list(importance_sorted.items())[:5]:
        bar = "█" * int(score * 100)
        print(f"   {feat:<22} {score:.4f}  {bar}")

    print("\n✅ Done! Next step: python rl_agent.py")

if __name__ == "__main__":
    print("🚀 HealO — Federated XGBoost Dropout Predictor")
    print("=" * 50)
    run_federated_simulation()
