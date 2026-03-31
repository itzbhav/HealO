import pandas as pd
import numpy as np
import pickle
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    classification_report, roc_auc_score,
    confusion_matrix, ConfusionMatrixDisplay
)
import xgboost as xgb
import shap
import os

FEATURES_CSV = "features_dataset.csv"
MODEL_PATH = "models/dropout_model.pkl"
os.makedirs("models", exist_ok=True)


def load_and_prepare(csv_path):
    df = pd.read_csv(csv_path)

    feature_cols = [
        "reply_streak",
        "skip_rate_so_far",
        "weekend_skip_rate",
        "avg_reply_latency_seconds",
        "is_weekend",
        "messages_sent",
        "responses_received",
        "replied_today"
    ]

    df = df.dropna(subset=feature_cols + ["dropout_risk_label"])

    X = df[feature_cols].fillna(0)
    y = df["dropout_risk_label"]

    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    return X, y_encoded, le, df


def train(X, y, le):
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="mlogloss",
        random_state=42
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)

    print("=" * 50)
    print("CLASSIFICATION REPORT")
    print("=" * 50)
    print(classification_report(y_test, y_pred, target_names=le.classes_))

    auc = roc_auc_score(y_test, y_proba, multi_class="ovr", average="macro")
    print(f"ROC-AUC (macro, OvR): {auc:.4f}")

    if auc >= 0.80:
        print("✅ Target AUC ≥ 0.80 achieved!")
    else:
        print(f"⚠️  AUC below 0.80 — consider more features or data")

    cm = confusion_matrix(y_test, y_pred)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=le.classes_)
    disp.plot(cmap="Blues")
    plt.title("HealO Dropout Predictor — Confusion Matrix")
    plt.tight_layout()
    plt.savefig("models/confusion_matrix.png")
    print("Saved confusion_matrix.png")

    return model, X_test, y_test, le


def shap_analysis(model, X_test):
    # Fallback: use XGBoost native feature importance
    importance = model.get_booster().get_score(importance_type="gain")
    
    features = list(importance.keys())
    scores = list(importance.values())
    
    sorted_idx = sorted(range(len(scores)), key=lambda i: scores[i])
    
    plt.figure(figsize=(8, 5))
    plt.barh(
        [features[i] for i in sorted_idx],
        [scores[i] for i in sorted_idx],
        color="#01696f"
    )
    plt.xlabel("Feature Importance (Gain)")
    plt.title("HealO Dropout Predictor — Feature Importance")
    plt.tight_layout()
    plt.savefig("models/shap_importance.png")
    plt.close()
    print("Saved shap_importance.png")


def main():
    print("Loading features...")
    X, y, le, df = load_and_prepare(FEATURES_CSV)
    print(f"Dataset: {len(X)} rows, {X.shape[1]} features")
    print(f"Label distribution:\n{pd.Series(le.inverse_transform(y)).value_counts()}\n")

    print("Training XGBoost...")
    model, X_test, y_test, le = train(X, y, le)

    print("\nRunning SHAP analysis...")
    shap_analysis(model, X_test)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": model, "label_encoder": le}, f)
    print(f"\nModel saved to {MODEL_PATH}")


if __name__ == "__main__":
    main()