"""
demo_send.py — Send sample HEALo WhatsApp messages to MY_TEST_NUMBER.
Run:  python demo_send.py
"""
import os, time
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

client   = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
FROM     = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
TO       = "whatsapp:" + os.getenv("MY_TEST_NUMBER", "")

MESSAGES = [
    ("Medication Reminder",
     "HEALo: Good morning! \U0001f305 Time for your Diabetes medication.\n"
     "Reply *YES* once you've taken it, or *NO* if you missed it. \U0001f48a"),

    ("Motivational Nudge",
     "HEALo: You're doing amazing! \U0001f4aa Every dose brings you closer to better health.\n"
     "Reply *YES* to confirm today's dose. We're rooting for you! \U0001f31f"),

    ("Appointment Reminder",
     "HEALo: \U0001f4c5 Reminder — you have an upcoming appointment with Dr. Priya.\n"
     "Reply *CONFIRM* to confirm or *CANCEL* to reschedule."),
]

print(f"Sending {len(MESSAGES)} demo messages to {TO}\n")

for label, body in MESSAGES:
    try:
        msg = client.messages.create(from_=FROM, to=TO, body=body)
        print(f"  [OK] {label} — SID: {msg.sid[:12]}...")
    except Exception as e:
        print(f"  [FAIL] {label} — {e}")
    time.sleep(2)   # small gap so they arrive in order

print("\nDone! Check your WhatsApp.")
print("Reply to any message — if your FastAPI server is running, the webhook will process it.")
print("Start server: python -m uvicorn app.main:app --reload --port 8000")
