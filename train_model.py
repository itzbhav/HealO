"""
train_model.py — HealO Heterogeneous Federated Learning
========================================================
Simulates 3 clinics each using a DIFFERENT local model type:
  Clinic 1  →  XGBoost          (handles complex non-linear patterns)
  Clinic 2  →  Random Forest    (robust to noisy / sparse data)
  Clinic 3  →  Logistic Reg.    (interpretable, lightweight)

Federated aggregation → weighted ensemble by each clinic's local AUC.
The final model is saved as dropout_model.pkl with the same
predict_proba() interface used everywhere in the system.
"""

import pandas as pd
import numpy as np
import pickle
import json
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
import xgboost as xgb

import flwr as fl
from flwr.common import NDArrays, Scalar
from typing import Dict

FEATURE_COLS = [
    "reply_rate", "streak", "weekend_skip_rate",
    "avg_latency_min", "days_since_reply", "med_taken_rate",
    "latency_drift", "recent_reply_rate", "disease_enc"
]
LABEL_COL  = "dropout_label"
N_CLIENTS  = 3


# ── Heterogeneous Ensemble (the "federated" model) ────────────────────────────
class HeterogeneousEnsemble:
    """
    Wraps 3 different clinic models. Predicts by taking a weighted average
    of their individual probability outputs (weights = local AUC scores).
    Exposes predict_proba() and feature_importances_ so the rest of the
    system works without any changes.
    """

    def __init__(self, models: list, weights: list, feature_names: list, scaler=None):
        self.models        = models          # [xgb_model, rf_model, lr_model]
        self.weights       = np.array(weights) / np.sum(weights)   # normalise
        self.feature_names = feature_names
        self.scaler        = scaler          # LR needs scaled input

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        X_scaled = self.scaler.transform(X) if self.scaler else X
        probs = []
        for i, model in enumerate(self.models):
            X_input = X_scaled if i == 2 else X   # LR is model index 2
            probs.append(model.predict_proba(X_input)[:, 1])
        weighted = np.average(np.array(probs), axis=0, weights=self.weights)
        return np.column_stack([1 - weighted, weighted])

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)

    @property
    def feature_importances_(self) -> np.ndarray:
        """
        Average importances from models that support it (XGBoost + RF).
        LR uses |coefficients| normalised to [0,1].
        """
        xgb_imp = self.models[0].feature_importances_
        rf_imp  = self.models[1].feature_importances_

        lr_coef = np.abs(self.models[2].coef_[0])
        lr_imp  = lr_coef / (lr_coef.sum() + 1e-9)

        combined = (
            self.weights[0] * xgb_imp +
            self.weights[1] * rf_imp  +
            self.weights[2] * lr_imp
        )
        return combined / (combined.sum() + 1e-9)


# ── Data loading ──────────────────────────────────────────────────────────────
def load_data():
    df = pd.read_csv("patient_features.csv")
    le = LabelEncoder()
    df["disease_enc"] = le.fit_transform(df["disease"].fillna("Unknown"))
    X = df[FEATURE_COLS].values
    y = df[LABEL_COL].values
    return X, y, df


def split_into_clinics(X, y, n=N_CLIENTS):
    """Simulate n clinics by splitting dataset into n partitions."""
    indices = np.arange(len(X))
    np.random.seed(42)
    np.random.shuffle(indices)
    splits = np.array_split(indices, n)
    return [(X[s], y[s]) for s in splits]


# ── Per-clinic model definitions ──────────────────────────────────────────────
def build_clinic_model(clinic_id: int, scaler=None):
    """Return the model assigned to each clinic."""
    if clinic_id == 0:
        return xgb.XGBClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.1,
            use_label_encoder=False, eval_metric="logloss",
            random_state=42, verbosity=0
        )
    elif clinic_id == 1:
        return RandomForestClassifier(
            n_estimators=100, max_depth=6,
            random_state=42, n_jobs=-1
        )
    else:
        return LogisticRegression(
            max_iter=500, random_state=42, C=1.0
        )


# ── Flower FL client ──────────────────────────────────────────────────────────
CLINIC_NAMES  = ["XGBoost", "Random Forest", "Logistic Regression"]
CLINIC_COLORS = ["🟦", "🟩", "🟧"]

class HealOClient(fl.client.NumPyClient):
    def __init__(self, clinic_id: int, X_train, y_train, X_test, y_test, scaler=None):
        self.clinic_id = clinic_id
        self.X_train   = X_train
        self.y_train   = y_train
        self.X_test    = X_test
        self.y_test    = y_test
        self.scaler    = scaler
        self.model     = build_clinic_model(clinic_id)
        self.local_auc = 0.0

    def _prepare(self, X):
        """Apply scaler for Logistic Regression only."""
        return self.scaler.transform(X) if (self.scaler and self.clinic_id == 2) else X

    def get_parameters(self, config) -> NDArrays:
        return [np.zeros(1, dtype=np.float32)]

    def fit(self, parameters: NDArrays, config: Dict[str, Scalar]):
        label = CLINIC_NAMES[self.clinic_id]
        print(f"  {CLINIC_COLORS[self.clinic_id]} Clinic {self.clinic_id+1} [{label}] "
              f"— training on {len(self.X_train)} patients...")
        self.model.fit(self._prepare(self.X_train), self.y_train)
        return [np.zeros(1, dtype=np.float32)], len(self.X_train), {}

    def evaluate(self, parameters: NDArrays, config: Dict[str, Scalar]):
        y_prob = self.model.predict_proba(self._prepare(self.X_test))[:, 1]
        y_pred = (y_prob >= 0.5).astype(int)
        acc    = float(np.mean(y_pred == self.y_test))
        try:
            self.local_auc = float(roc_auc_score(self.y_test, y_prob))
        except Exception:
            self.local_auc = 0.5
        print(f"     Accuracy: {acc:.3f}  |  AUC: {self.local_auc:.3f}")
        return 1 - acc, len(self.X_test), {"accuracy": acc, "auc": self.local_auc}


# ── Main training pipeline ────────────────────────────────────────────────────
def run_federated_simulation():
    print("\n📊 Loading patient features...")
    X, y, df = load_data()
    print(f"   Total patients : {len(X)}")
    print(f"   Dropout rate   : {y.mean()*100:.1f}%")

    X_train_all, X_test, y_train_all, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    clinic_data = split_into_clinics(X_train_all, y_train_all, N_CLIENTS)

    # Scaler for Logistic Regression (Clinic 3 only)
    scaler = StandardScaler().fit(X_train_all)

    print(f"\n🏥 Heterogeneous Federated Learning — {N_CLIENTS} Clinics")
    print(f"   {'Clinic':<10} {'Model':<22} {'Patients':>8}  {'Dropout':>8}")
    model_names = CLINIC_NAMES
    for i, (Xc, yc) in enumerate(clinic_data):
        print(f"   Clinic {i+1:<4}  {model_names[i]:<22} {len(Xc):>8}  {yc.mean()*100:>7.1f}%")

    print(f"\n🔄 FL Round — Local Training per Clinic")
    print("-" * 55)

    clients = []
    for i, (Xc, yc) in enumerate(clinic_data):
        client = HealOClient(i, Xc, yc, X_test, y_test, scaler=scaler)
        client.fit([], {})
        client.evaluate([], {})
        clients.append(client)

    # ── Federated aggregation: weighted by local AUC ──────────────────────
    print("\n🔗 Federated Aggregation — Weighted Ensemble by Local AUC")
    print("-" * 55)

    weights = [c.local_auc for c in clients]
    models  = [c.model for c in clients]

    for i, (w, auc) in enumerate(zip(weights, [c.local_auc for c in clients])):
        norm_w = w / sum(weights)
        bar    = "█" * int(norm_w * 30)
        print(f"   Clinic {i+1} [{CLINIC_NAMES[i]:<22}]  AUC={auc:.3f}  weight={norm_w:.2f}  {bar}")

    ensemble = HeterogeneousEnsemble(
        models=models,
        weights=weights,
        feature_names=FEATURE_COLS,
        scaler=scaler,
    )

    # ── Evaluate the ensemble on the global test set ──────────────────────
    ensemble_probs = ensemble.predict_proba(X_test)[:, 1]
    ensemble_preds = ensemble.predict(X_test)
    ensemble_auc   = roc_auc_score(y_test, ensemble_probs)

    print(f"\n🎯 Federated Ensemble — Global Test Set")
    print("-" * 55)
    print(f"   AUC-ROC : {ensemble_auc:.4f}")
    print(f"\n{classification_report(y_test, ensemble_preds, target_names=['Active','Dropout'])}")

    # ── Save ──────────────────────────────────────────────────────────────
    with open("dropout_model.pkl", "wb") as f:
        pickle.dump(ensemble, f)

    importance = dict(zip(FEATURE_COLS, ensemble.feature_importances_))
    importance_sorted = dict(
        sorted({k: float(v) for k, v in importance.items()}.items(),
               key=lambda x: x[1], reverse=True)
    )
    with open("feature_importance.json", "w") as f:
        json.dump(importance_sorted, f, indent=2)

    print("📁 Saved:")
    print("   dropout_model.pkl       ← heterogeneous federated ensemble")
    print("   feature_importance.json ← weighted feature importances")

    print("\n🏆 Top features driving dropout prediction:")
    for feat, score in list(importance_sorted.items())[:5]:
        bar = "█" * int(score * 50)
        print(f"   {feat:<22} {score:.4f}  {bar}")

    print("\n✅ Done! Run: python rl_agent.py")


if __name__ == "__main__":
    print("🚀 HealO — Heterogeneous Federated Learning")
    print("   Clinic 1: XGBoost  |  Clinic 2: Random Forest  |  Clinic 3: Logistic Regression")
    print("=" * 60)
    run_federated_simulation()
