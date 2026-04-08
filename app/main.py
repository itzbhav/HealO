from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.health import router as health_router
from app.api.routes.patients import router as patients_router
from app.api.routes.messages import router as messages_router
from app.api.routes.webhook import router as webhook_router
from app.api.routes.reminders import router as reminders_router
from app.core.config import settings
from groq import Groq
from dotenv import load_dotenv
import sqlite3, os

load_dotenv()
_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

app = FastAPI(
    title=settings.app_name,
    description="Backend API for HealO medication adherence system",
    version="0.1.0"
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(patients_router)
app.include_router(messages_router)
app.include_router(webhook_router)
app.include_router(reminders_router)

# ── DB helper ─────────────────────────────────────────────────────────────────
def _get_conn():
    db_path = os.path.join(os.path.dirname(__file__), "..", "healo.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# ── Dashboard API ─────────────────────────────────────────────────────────────
@app.get("/api/dashboard")
def get_dashboard():
    conn = _get_conn()

    # Use the latest available date, not just today — prevents empty dashboard
    rows = conn.execute("""
        SELECT
            p.id,
            p.full_name,
            p.disease,
            p.doctor_name                          AS assigned_doctor,
            p.age,
            p.gender,
            p.language,
            p.phone_number,

            d.risk_score,
            d.risk_label,
            d.action_taken,
            d.message_sent,
            d.log_date,

            -- Reply rate: inbound responses / total messages sent
            COALESCE(
                CAST(
                    (SELECT COUNT(*) FROM responses r
                     WHERE r.patient_id = p.id) AS FLOAT
                ) /
                NULLIF(
                    (SELECT COUNT(*) FROM message_logs ml
                     WHERE ml.patient_id = p.id), 0
                ), 0
            ) AS reply_rate,

            -- Days silent: days since last inbound response
            COALESCE(
                CAST(
                    julianday('now') -
                    julianday((
                        SELECT MAX(received_at) FROM responses r2
                        WHERE r2.patient_id = p.id
                    )) AS INTEGER
                ), 0
            ) AS days_silent,

            -- Streak: distinct days with at least one response in last 30 days
            (
                SELECT COUNT(DISTINCT date(received_at))
                FROM responses r3
                WHERE r3.patient_id = p.id
                  AND r3.received_at >= date('now', '-30 days')
            ) AS streak,

            -- Latest intervention
            (
                SELECT action_type FROM interventions i
                WHERE i.patient_id = p.id
                ORDER BY i.created_at DESC LIMIT 1
            ) AS latest_intervention,

            -- Med adherence: confirmed doses / total reminder messages sent
            -- Uses LOWER() to handle both 'YES' and 'yes' stored values
            COALESCE(
                CAST(
                    (SELECT COUNT(*) FROM responses r4
                     WHERE r4.patient_id = p.id
                       AND LOWER(r4.normalized_label) IN ('taken','yes','done')
                    ) AS FLOAT
                ) /
                NULLIF(
                    (SELECT COUNT(*) FROM message_logs ml2
                     WHERE ml2.patient_id = p.id
                       AND ml2.message_type = 'outbound'
                    ), 0
                ), 0
            ) AS med_adherence

        FROM daily_risk_log d
        JOIN patients p ON p.id = d.patient_id
        WHERE d.log_date = (SELECT MAX(log_date) FROM daily_risk_log)
          AND p.is_active = 1
        ORDER BY d.risk_score DESC
    """).fetchall()

    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/dashboard/stats")
def get_dashboard_stats():
    """Summary KPIs for the top cards."""
    conn = _get_conn()

    stats = conn.execute("""
        SELECT
            (SELECT COUNT(*) FROM patients WHERE is_active=1)              AS total_patients,
            (SELECT COUNT(*) FROM daily_risk_log
             WHERE log_date=(SELECT MAX(log_date) FROM daily_risk_log)
               AND risk_label='High')                                       AS high_risk,
            (SELECT COUNT(*) FROM daily_risk_log
             WHERE log_date=(SELECT MAX(log_date) FROM daily_risk_log)
               AND risk_label='Medium')                                     AS medium_risk,
            (SELECT COUNT(*) FROM daily_risk_log
             WHERE log_date=(SELECT MAX(log_date) FROM daily_risk_log)
               AND risk_label='Low')                                        AS low_risk,
            (SELECT COUNT(*) FROM message_logs
             WHERE date(sent_at)=date('now'))                               AS messages_today,
            (SELECT COUNT(*) FROM responses
             WHERE date(received_at)=date('now'))                           AS replies_today,
            (SELECT COUNT(*) FROM interventions
             WHERE date(created_at)=date('now')
               AND action_type='escalate_to_doctor')                        AS escalations_today
    """).fetchone()

    conn.close()
    return dict(stats)


@app.get("/api/dashboard/trend")
def get_trend():
    """Last 7 days of High/Medium/Low patient counts for the risk trend chart."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT
            log_date,
            SUM(CASE WHEN risk_label='High'   THEN 1 ELSE 0 END) AS high,
            SUM(CASE WHEN risk_label='Medium' THEN 1 ELSE 0 END) AS medium,
            SUM(CASE WHEN risk_label='Low'    THEN 1 ELSE 0 END) AS low
        FROM daily_risk_log
        GROUP BY log_date
        ORDER BY log_date DESC
        LIMIT 7
    """).fetchall()
    conn.close()
    # Return in ascending order so the chart reads left→right
    result = [{"date": r["log_date"], "high": r["high"],
               "medium": r["medium"], "low": r["low"]}
              for r in reversed(rows)]
    return result


@app.get("/api/dashboard/patient/{patient_id}/explanation")
def get_patient_explanation(patient_id: int):
    """Generate an AI explanation of why a patient has their current risk score."""
    conn = _get_conn()

    row = conn.execute("""
        SELECT
            p.full_name, p.disease, p.doctor_name, p.age, p.gender,
            d.risk_score, d.risk_label, d.action_taken, d.log_date,
            COALESCE(
                CAST((SELECT COUNT(*) FROM responses r WHERE r.patient_id = p.id) AS FLOAT) /
                NULLIF((SELECT COUNT(*) FROM message_logs ml WHERE ml.patient_id = p.id), 0), 0
            ) AS reply_rate,
            COALESCE(
                CAST(julianday('now') - julianday(
                    (SELECT MAX(received_at) FROM responses r2 WHERE r2.patient_id = p.id)
                ) AS INTEGER), 0
            ) AS days_silent,
            (SELECT COUNT(DISTINCT date(received_at)) FROM responses r3
             WHERE r3.patient_id = p.id AND r3.received_at >= date('now', '-30 days')
            ) AS streak,
            COALESCE(
                CAST(
                    (SELECT COUNT(*) FROM responses r4 WHERE r4.patient_id = p.id
                       AND LOWER(r4.normalized_label) IN ('taken','yes','done')) AS FLOAT
                ) /
                NULLIF(
                    (SELECT COUNT(*) FROM message_logs ml2
                     WHERE ml2.patient_id = p.id AND ml2.message_type = 'outbound'), 0
                ), 0
            ) AS med_adherence
        FROM daily_risk_log d
        JOIN patients p ON p.id = d.patient_id
        WHERE p.id = ?
        ORDER BY d.log_date DESC
        LIMIT 1
    """, (patient_id,)).fetchone()
    conn.close()

    if not row:
        return {"explanation": "No risk data available for this patient yet."}

    r = dict(row)
    prompt = f"""You are a clinical AI assistant helping doctors understand patient risk.

Patient: {r['full_name']}, Age {r['age']}, {r['gender']}
Disease: {r['disease']} | Doctor: {r['doctor_name']}
Risk Score: {round(r['risk_score']*100)}% ({r['risk_label']} risk)
Reply Rate: {round(r['reply_rate']*100)}%
Medication Adherence: {round(r['med_adherence']*100)}%
Days Since Last Response: {r['days_silent']}
Response Streak (last 30d): {r['streak']} days
Recommended Action: {r['action_taken']}

Write a 2-3 sentence clinical summary explaining WHY this patient is {r['risk_label']} risk
and what the doctor should know. Be specific about the numbers. Do NOT use bullet points."""

    try:
        resp = _groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.4,
        )
        explanation = resp.choices[0].message.content.strip()
    except Exception as e:
        explanation = f"Unable to generate explanation: {e}"

    return {"explanation": explanation, "stats": r}


@app.post("/api/schedule-message")
async def schedule_message(body: dict):
    """Send a WhatsApp message via Twilio and log it to message_logs."""
    from twilio.rest import Client as TwilioClient
    from app.core.db_service import get_conn as _db_conn
    import datetime

    patient_id   = body.get("patient_id")
    message_text = body.get("message", "")
    twilio_sid   = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_from  = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    sid = None
    if patient_id and message_text:
        # Fetch patient phone number
        conn = _db_conn()
        row = conn.execute("SELECT phone_number FROM patients WHERE id=?", (patient_id,)).fetchone()
        conn.close()

        if row:
            phone = row["phone_number"]
            to    = f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone

            # Send via Twilio
            try:
                client = TwilioClient(twilio_sid, twilio_token)
                msg = client.messages.create(from_=twilio_from, to=to, body=message_text)
                sid = msg.sid
                status = "sent"
            except Exception as e:
                print(f"[schedule_message] Twilio error: {e}")
                status = "failed"

            # Log to message_logs
            conn2 = _db_conn()
            try:
                conn2.execute("""
                    INSERT INTO message_logs
                    (patient_id, message_type, message_content, language, sent_at, delivery_status)
                    VALUES (?, 'outbound', ?, 'English', ?, ?)
                """, (patient_id, message_text, datetime.datetime.now().isoformat(), status))
                conn2.commit()
            except Exception as e:
                print(f"[schedule_message] DB log error: {e}")
            finally:
                conn2.close()

            return {"status": status, "patient_id": patient_id, "sid": sid}

    return {"status": "error", "detail": "patient_id and message are required"}


@app.get("/api/ml-insights")
def get_ml_insights():
    """
    Returns Federated Learning per-clinic AUC, RL action distribution,
    and XGBoost feature importances — powers the Model Intelligence panel.
    """
    import pandas as pd
    import numpy as np
    import pickle
    import xgboost as xgb
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import LabelEncoder

    FEATURE_COLS = [
        "reply_rate", "streak", "weekend_skip_rate", "avg_latency_min",
        "days_since_reply", "med_taken_rate", "latency_drift",
        "recent_reply_rate", "disease_enc",
    ]

    # ── Load data & global model ───────────────────────────────────────────
    try:
        df = pd.read_csv(
            os.path.join(os.path.dirname(__file__), "..", "patient_features.csv")
        )
    except FileNotFoundError:
        return {"error": "patient_features.csv not found"}

    le = LabelEncoder()
    df["disease_enc"] = le.fit_transform(df["disease"].fillna("Unknown"))
    X = df[FEATURE_COLS].values
    y = df["dropout_label"].values

    model_path = os.path.join(os.path.dirname(__file__), "..", "dropout_model.pkl")
    try:
        with open(model_path, "rb") as f:
            global_model = pickle.load(f)
        global_auc = round(float(roc_auc_score(y, global_model.predict_proba(X)[:, 1])), 3)
    except Exception as e:
        return {"error": str(e)}

    # ── FL: 3-clinic simulation ────────────────────────────────────────────
    # Split patients into 3 equal clinic partitions (same as train_model.py)
    np.random.seed(42)
    idx    = np.random.permutation(len(df))
    splits = np.array_split(idx, 3)

    clinic_results = []
    for i, test_idx in enumerate(splits):
        train_mask = np.ones(len(df), dtype=bool)
        train_mask[test_idx] = False

        local_model = xgb.XGBClassifier(
            n_estimators=60, max_depth=3, learning_rate=0.1,
            use_label_encoder=False, eval_metric="logloss",
            verbosity=0, random_state=42,
        )
        local_model.fit(X[train_mask], y[train_mask])
        try:
            local_auc = round(
                float(roc_auc_score(y[test_idx], local_model.predict_proba(X[test_idx])[:, 1])), 3
            )
        except Exception:
            local_auc = 0.5

        clinic_results.append({
            "clinic":        f"Clinic {i + 1}",
            "patients":      int(len(test_idx)),
            "local_auc":     local_auc,
            "federated_auc": global_auc,
        })

    # ── RL action distribution ─────────────────────────────────────────────
    conn = _get_conn()
    action_rows = conn.execute("""
        SELECT action_taken, COUNT(*) AS cnt
        FROM daily_risk_log
        WHERE log_date = (SELECT MAX(log_date) FROM daily_risk_log)
        GROUP BY action_taken ORDER BY cnt DESC
    """).fetchall()
    conn.close()
    action_dist = [{"action": r["action_taken"], "count": r["cnt"]} for r in action_rows]

    # ── Feature importance ─────────────────────────────────────────────────
    fi_pairs = sorted(
        zip(FEATURE_COLS, global_model.feature_importances_),
        key=lambda x: -x[1],
    )
    feature_importance = [
        {"feature": col.replace("_", " "), "importance": round(float(v), 4)}
        for col, v in fi_pairs
        if v > 0
    ]

    return {
        "global_auc":        global_auc,
        "clinic_results":    clinic_results,
        "action_distribution": action_dist,
        "feature_importance":  feature_importance,
    }


# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "message": f"{settings.app_name} is running",
        "environment": settings.app_env
    }


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True
    )
