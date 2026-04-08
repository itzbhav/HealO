# HEALo — AI-Integrated Federated Learning Medication Adherence System

> A clinical AI tool that uses **Federated Learning**, **Reinforcement Learning**, and **Conversational AI** to monitor patient medication adherence across multiple clinics — without centralising sensitive health data.

---

## Problem Statement

Medication non-adherence is one of the leading causes of treatment failure in chronic diseases like Diabetes, Hypertension, and TB. Patients stop taking their medication without notifying their doctors, and by the time it's caught, significant damage has been done.

HEALo addresses this by:
- Predicting which patients are at risk of dropping out **before** it happens
- Automatically sending the right intervention at the right time
- Giving doctors a real-time view of their entire patient panel
- Reaching patients who go completely silent via AI voice calls

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                  ML PIPELINE  (Offline)                 │
│                                                         │
│   Clinic 1 Data   Clinic 2 Data   Clinic 3 Data         │
│        │               │               │                │
│   XGBoost (local) XGBoost (local) XGBoost (local)       │
│        └───────────────┼───────────────┘                │
│                Federated Aggregation                     │
│                  (Flower framework)                      │
│                        │                                │
│              Global Dropout Risk Model                   │
│                 dropout_model.pkl                        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              DAILY INTELLIGENCE LOOP                    │
│                   scheduler.py                          │
│                                                         │
│  Per patient:                                           │
│  1. Build live features from message history            │
│  2. Score dropout risk  →  Global XGBoost model         │
│  3. Pick action         →  RL Contextual Bandit (VW)    │
│  4. Send WhatsApp       →  Twilio                       │
│  5. Apply real rewards  →  Bandit learns from responses │
│  6. Log to DB           →  Powers the dashboard         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                  LIVE SYSTEM  (FastAPI)                 │
│                                                         │
│  Patient WhatsApp reply                                 │
│           │                                             │
│           ▼                                             │
│  LLM Intent Detection  (Groq · Llama 3.3-70B)           │
│  Multilingual — English, Hindi, Tamil, emoji, etc.      │
│           │                                             │
│   medication_taken / missed / appointment / general     │
│           │                                             │
│  Log to DB  →  LLM reply  →  Patient                   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│               DOCTOR DASHBOARD  (React)                 │
│                                                         │
│  Dashboard     →  502 patients ranked by risk           │
│  Risk Engine   →  FL accuracy · RL actions · Features   │
│  Interventions →  Silent patients + AI Call button      │
│  Patient Drawer→  AI clinical explanation per patient   │
└─────────────────────────────────────────────────────────┘
```

---

## Features

### Federated Learning (Flower + XGBoost)
- Patient data is split across 3 simulated clinics — raw data never leaves each clinic
- Each clinic trains a local XGBoost dropout risk classifier
- Models are aggregated into a single global federated model
- **Global AUC: 98.3%**
- Per-clinic vs federated accuracy visualised in the dashboard

### Reinforcement Learning (Vowpal Wabbit Contextual Bandit)
- 5 possible daily actions per patient:
  - `morning_reminder` · `evening_reminder` · `motivational_message` · `escalate_to_doctor` · `do_nothing`
- Context: risk score, response streak, weekend skip rate, latency, days silent
- **Delayed reward loop** — real patient responses are fetched each morning and fed back as rewards so the bandit actually learns from outcomes
- Hard override: risk > 70% AND silent 3+ days → always escalate

### AI WhatsApp Bot (Twilio + Groq)
- Outbound reminders sent daily based on RL decision
- Inbound replies processed by LLM — understands any language or phrasing
- Handles: medication confirmation, appointment management, general queries
- Conversational memory per patient (last 10 messages)
- Clinical, professional tone

### AI Voice Call (Twilio Voice + Amazon Polly)
- Doctor triggers an outbound call directly from the Interventions dashboard
- Indian English TTS using **Amazon Polly Aditi** voice
- Patient presses: **1** (medication taken) · **2** (missed) · **3** (request callback)
- Response logged to database instantly
- Built for patients who are completely unresponsive to WhatsApp

### Doctor Dashboard (React)
- Patient risk table — 502 patients sorted by dropout probability
- KPI cards: total patients, high / medium / low risk
- 7-day risk trend chart + today's risk split (donut)
- **Model Intelligence view** — FL clinic AUC, RL action distribution, XGBoost feature importance
- **Interventions view** — top 30 most critical patients with one-click AI Call
- Per-patient AI explanation generated by Groq LLM on demand
- Schedule and send WhatsApp messages directly from the dashboard

---

## Tech Stack

| Component | Technology |
|---|---|
| Federated Learning | Flower (`flwr`) |
| Dropout Risk Model | XGBoost |
| RL Agent | Vowpal Wabbit — Contextual Bandit (`--cb 5`) |
| LLM / Intent Detection | Groq — Llama 3.3-70B Versatile |
| Conversational Bot | Groq — Llama 3.3-70B Versatile |
| TTS Voice | Amazon Polly Aditi (via Twilio) |
| Messaging & Calls | Twilio (WhatsApp sandbox + Voice) |
| Backend | FastAPI + Uvicorn |
| Database | SQLite |
| Frontend | React + Vite |
| Charts | Chart.js |

---

## Project Structure

```
HEALo/
│
├── app/                          # FastAPI backend
│   ├── main.py                   # App entry + dashboard, ML insights, schedule APIs
│   ├── api/routes/
│   │   ├── webhook.py            # WhatsApp webhook + AI voice call routes
│   │   ├── patients.py           # Patient CRUD
│   │   ├── reminders.py          # Manual reminder trigger
│   │   └── messages.py           # Message log API
│   ├── core/
│   │   ├── groq_bot.py           # LLM conversational agent
│   │   ├── db_service.py         # SQLite connection + helpers
│   │   ├── config.py             # Environment settings
│   │   └── twilio_whatsapp.py    # Twilio send helper
│   ├── models/                   # SQLAlchemy ORM models
│   └── schemas/                  # Pydantic request/response schemas
│
├── healo-react/                  # React frontend (Vite)
│   └── src/
│       ├── App.jsx               # Layout, nav routing, view switching
│       ├── components/
│       │   ├── KpiCards.jsx      # Animated KPI summary cards
│       │   ├── RiskChart.jsx     # 7-day trend + donut chart
│       │   ├── PatientTable.jsx  # Sortable, filterable risk table
│       │   ├── PatientDrawer.jsx # Patient detail panel + AI explanation
│       │   ├── MLInsights.jsx    # FL / RL / feature importance panel
│       │   ├── Interventions.jsx # Critical patients list + AI Call
│       │   └── ScheduleModal.jsx # WhatsApp message sender
│       └── hooks/
│           ├── usePatients.js    # Dashboard + stats data hook
│           └── useTrend.js       # 7-day trend data hook
│
├── simulate_journeys.py          # Synthetic patient journey generator
├── build_features.py             # Feature engineering from message logs
├── train_model.py                # FL training with Flower + XGBoost
├── rl_agent.py                   # Offline RL simulation
├── scheduler.py                  # Daily intelligence loop (run once/day)
├── dashboard.py                  # Streamlit dashboard (legacy)
├── healo.db                      # SQLite database
├── dropout_model.pkl             # Trained global federated model
├── patient_features.csv          # Feature dataset (502 patients)
└── requirements.txt              # Python dependencies
```

---

## Database Schema

| Table | Purpose |
|---|---|
| `patients` | Patient demographics, disease, assigned doctor |
| `message_logs` | Every inbound/outbound WhatsApp message |
| `responses` | Parsed patient responses with intent + normalized label |
| `daily_risk_log` | Per-patient risk score + RL action per day |
| `interventions` | Escalation and intervention records |
| `appointments` | Scheduled appointments with status |
| `medications` | Medication records per patient |

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- Node.js 18+
- Twilio account (WhatsApp sandbox + a voice-capable phone number)
- Groq API key — [console.groq.com](https://console.groq.com) (free tier)
- ngrok — for exposing local server to Twilio webhooks

### 1. Clone the repository

```bash
git clone https://github.com/itzbhav/HEALo.git
cd HEALo
```

### 2. Python environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac / Linux

pip install -r requirements.txt
```

### 3. Environment variables

Create a `.env` file in the root directory:

```env
APP_NAME=HealO Backend
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000
DATABASE_URL=sqlite:///./healo.db

TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
MY_TEST_NUMBER=+91xxxxxxxxxx

GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
BASE_URL=https://xxxx.ngrok-free.app
```

### 4. Run the ML pipeline (first time only)

```bash
python simulate_journeys.py   # generate synthetic data
python build_features.py      # engineer features
python train_model.py         # train federated model
python rl_agent.py            # run RL simulation
```

### 5. Start everything

**Terminal 1 — Backend:**
```bash
venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — ngrok tunnel:**
```bash
ngrok http 8000
```
Copy the HTTPS URL into `BASE_URL` in `.env` and restart the backend.

**Terminal 3 — Frontend:**
```bash
cd healo-react
npm run dev
```
Open [http://localhost:5173](http://localhost:5173)

**Terminal 4 — Daily scheduler:**
```bash
venv\Scripts\python scheduler.py
```

### 6. Configure Twilio

In the Twilio console, set the WhatsApp sandbox webhook to:
```
https://xxxx.ngrok-free.app/webhook/whatsapp
```

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/dashboard` | GET | All patients with risk scores (latest date) |
| `/api/dashboard/stats` | GET | KPI counts — high / medium / low risk |
| `/api/dashboard/trend` | GET | 7-day risk distribution history |
| `/api/dashboard/patient/{id}/explanation` | GET | LLM risk explanation for one patient |
| `/api/ml-insights` | GET | FL clinic AUC, RL action dist, feature importance |
| `/api/schedule-message` | POST | Send WhatsApp message to patient via Twilio |
| `/webhook/whatsapp` | POST | Twilio inbound WhatsApp message handler |
| `/webhook/initiate-call/{id}` | POST | Trigger AI voice call to patient |
| `/webhook/voice/{id}` | GET/POST | TwiML script served to Twilio for the call |
| `/webhook/voice/response/{id}` | POST | Handle patient DTMF keypress response |

---

## Rubric Mapping

| Criteria | Implementation |
|---|---|
| **Input Data** (5 marks) | 502-patient synthetic dataset with 9 engineered features; real-time WhatsApp message stream; SQLite with 7 tables |
| **Basic FL Requirement** (10 marks) | Flower framework; 3-clinic data partitions; local XGBoost per clinic; federated aggregation; global AUC 98.3% |
| **Advanced AI** (10 marks) | RL contextual bandit with real delayed rewards (Vowpal Wabbit); LLM intent detection in any language (Groq/Llama 3.3); AI voice call with TTS (Amazon Polly); conversational bot with memory |
| **Visualization** (3 marks) | React dashboard — risk trend chart, donut, FL accuracy bars, RL action distribution, XGBoost feature importance, animated KPI cards |
| **Tool + GitHub** (2 marks) | Full-stack deployable system; source on GitHub |



---

*HEALo — Because every missed dose matters.*
