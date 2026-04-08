import json
from fastapi import APIRouter, Form
from fastapi.responses import Response
from groq import Groq
from twilio.rest import Client as TwilioClient
from dotenv import load_dotenv
import os

from app.core.groq_bot import get_bot_reply
from app.core.db_service import (
    get_patient_by_phone, log_message, log_response,
    get_upcoming_appointment, confirm_appointment,
    cancel_appointment, log_medication_taken, get_conn,
)

load_dotenv()
_groq         = Groq(api_key=os.getenv("GROQ_API_KEY"))
_twilio_sid   = os.getenv("TWILIO_ACCOUNT_SID")
_twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
_twilio_from  = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
_voice_from   = os.getenv("TWILIO_PHONE_NUMBER")   # voice-capable number

router = APIRouter(prefix="/webhook", tags=["webhook"])

# ── WhatsApp intent prompt ─────────────────────────────────────────────────────
_INTENT_PROMPT = """\
You are an intent classifier for a medication adherence WhatsApp bot.

Classify the patient message below into exactly ONE intent:
  medication_taken     – patient says they took their medication (yes, done, taken, haan, le liya, ✅, ho gaya, etc.)
  medication_missed    – patient says they missed/didn't take medication (no, nahi, missed, bhool gaya, etc.)
  confirm_appointment  – patient confirms an appointment (confirm, ok confirm, yes appointment)
  cancel_appointment   – patient wants to cancel an appointment
  check_appointment    – patient asks about their next appointment
  general              – anything else (greetings, questions, unknown)

Message: "{message}"

Respond with valid JSON only, nothing else:
{{"intent": "...", "normalized_label": "yes|no|unknown", "sentiment": "positive|negative|neutral"}}"""


def detect_intent(message: str) -> dict:
    """Use Groq LLM for multilingual intent detection. Falls back to 'general' on error."""
    try:
        resp = _groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": _INTENT_PROMPT.format(message=message)}],
            max_tokens=80,
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        print(f"[detect_intent] LLM error, falling back: {e}")
        return {"intent": "general", "normalized_label": "unknown", "sentiment": "neutral"}


# ── WhatsApp webhook ───────────────────────────────────────────────────────────
@router.post("/whatsapp")
async def whatsapp_webhook(Body: str = Form(...), From: str = Form(...)):
    phone      = From.replace("whatsapp:", "")
    message    = Body.strip()

    intent_data = detect_intent(message)
    intent      = intent_data["intent"]
    norm_label  = intent_data["normalized_label"]
    sentiment   = intent_data["sentiment"]

    patient    = get_patient_by_phone(phone)
    patient_id = patient["id"] if patient else None
    log_message(phone, "inbound", message, intent, patient_id)

    if patient:
        appt = get_upcoming_appointment(patient_id)

        if intent == "medication_taken":
            log_medication_taken(patient_id, taken=True, raw_text=message)
            context = (
                f"Patient {patient['full_name']} confirmed they took their "
                f"{patient['disease']} medication today. Acknowledge professionally."
            )
        elif intent == "medication_missed":
            log_medication_taken(patient_id, taken=False, raw_text=message)
            context = (
                f"Patient {patient['full_name']} missed their {patient['disease']} "
                f"medication. Gently remind them to take it soon."
            )
        elif intent == "confirm_appointment" and appt:
            confirm_appointment(patient_id)
            context = (
                f"Patient {patient['full_name']} confirmed appointment on "
                f"{appt['appointment_date']} at {appt['appointment_time']} with {appt['doctor_name']}."
            )
        elif intent == "cancel_appointment" and appt:
            cancel_appointment(patient_id)
            context = (
                f"Patient {patient['full_name']} cancelled appointment on "
                f"{appt['appointment_date']}. Acknowledge and suggest rescheduling."
            )
        elif intent == "check_appointment" and appt:
            context = (
                f"Patient {patient['full_name']} asking about appointment: "
                f"{appt['appointment_date']} at {appt['appointment_time']} "
                f"with {appt['doctor_name']}. Status: {appt['status']}."
            )
        elif intent in ("confirm_appointment", "check_appointment") and not appt:
            context = (
                f"Patient {patient['full_name']} mentioned an appointment but none scheduled. "
                f"Suggest contacting the clinic."
            )
        else:
            log_response(patient_id, message, norm_label, intent, sentiment)
            context = (
                f"Patient: {patient['full_name']}, Disease: {patient['disease']}, "
                f"Doctor: {patient['doctor_name']}. They said: '{message}'. Respond helpfully."
            )
    else:
        context = (
            f"Unknown patient (phone: {phone}). "
            f"Tell them they are not registered in HealO yet."
        )

    reply = get_bot_reply(phone, f"[CONTEXT: {context}]\nPatient said: {message}")
    log_message(phone, "outbound", reply, None, patient_id)

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response><Message>{reply}</Message></Response>"""
    return Response(content=twiml, media_type="application/xml")


# ── AI Voice Call — initiate ───────────────────────────────────────────────────
@router.post("/initiate-call/{patient_id}")
async def initiate_call(patient_id: int):
    """
    Triggers an outbound Twilio voice call to the patient.
    The call plays a TTS medication/appointment reminder and captures
    the patient's keypress (1 = taken, 2 = missed, 3 = callback needed).
    """
    if not _voice_from or _voice_from == "+1xxxxxxxxxx":
        return {"error": "TWILIO_PHONE_NUMBER not configured in .env"}

    base_url = os.getenv("BASE_URL", "").rstrip("/")
    if not base_url or "xxxx" in base_url:
        return {"error": "BASE_URL not configured in .env — set it to your ngrok URL"}

    # Fetch patient details
    conn = get_conn()
    row  = conn.execute(
        "SELECT full_name, phone_number, disease, doctor_name FROM patients WHERE id=?",
        (patient_id,)
    ).fetchone()
    conn.close()

    if not row:
        return {"error": "Patient not found"}

    phone     = row["phone_number"].lstrip("+")
    to_num    = f"+{phone}"
    voice_url = f"{base_url}/webhook/voice/{patient_id}"

    try:
        client = TwilioClient(_twilio_sid, _twilio_token)
        call   = client.calls.create(
            to=to_num,
            from_=_voice_from,
            url=voice_url,
            timeout=30,
        )
        return {"status": "calling", "sid": call.sid, "to": to_num}
    except Exception as e:
        return {"error": str(e)}


# ── AI Voice Call — TwiML script ──────────────────────────────────────────────
@router.api_route("/voice/{patient_id}", methods=["GET", "POST"])
async def voice_twiml(patient_id: int):
    """
    Returns the TwiML script for the outbound call.
    Uses Amazon Polly Aditi voice (Indian English) for natural pronunciation.
    """
    conn = get_conn()
    row  = conn.execute(
        "SELECT full_name, disease, doctor_name FROM patients WHERE id=?",
        (patient_id,)
    ).fetchone()
    conn.close()

    if not row:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response><Say>Patient record not found. Goodbye.</Say></Response>"""
        return Response(content=twiml, media_type="application/xml")

    name    = row["full_name"]
    disease = row["disease"]
    doctor  = row["doctor_name"] or "your doctor"

    base_url     = os.getenv("BASE_URL", "").rstrip("/")
    response_url = f"{base_url}/webhook/voice/response/{patient_id}"

    # Polly.Aditi = Indian English TTS voice
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Aditi" language="en-IN">
    Hello {name}. This is HealO, calling on behalf of {doctor}.
    We are following up on your {disease} medication adherence.
  </Say>
  <Pause length="1"/>
  <Gather numDigits="1" action="{response_url}" method="POST" timeout="8">
    <Say voice="Polly.Aditi" language="en-IN">
      Please press 1 if you have taken your medication today.
      Press 2 if you have not taken your medication today.
      Press 3 if you need a callback from your doctor.
    </Say>
  </Gather>
  <Say voice="Polly.Aditi" language="en-IN">
    We did not receive a response. Please contact your clinic or reply to our WhatsApp message. Goodbye.
  </Say>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


# ── AI Voice Call — DTMF response handler ────────────────────────────────────
@router.post("/voice/response/{patient_id}")
async def voice_response(patient_id: int, Digits: str = Form(default="")):
    """
    Handles the patient's keypress after the TTS prompt.
    1 → medication taken   (logged to responses table)
    2 → medication missed  (logged to responses table)
    3 → callback requested (logged as intervention)
    """
    digit = Digits.strip()

    if digit == "1":
        log_medication_taken(patient_id, taken=True, raw_text="[voice: pressed 1]")
        message = "Thank you. Your medication has been recorded as taken today. Take care. Goodbye."
        label   = "yes"
    elif digit == "2":
        log_medication_taken(patient_id, taken=False, raw_text="[voice: pressed 2]")
        message = (
            "Thank you for letting us know. Please take your medication as soon as possible "
            "and contact your clinic if you need assistance. Goodbye."
        )
        label = "no"
    elif digit == "3":
        # Log callback request as a response entry
        log_response(patient_id, "[voice: pressed 3 — callback requested]",
                     "callback", "callback_requested", "neutral")
        message = (
            "Understood. We will arrange a callback from your doctor. "
            "Please keep your phone available. Goodbye."
        )
        label = "callback"
    else:
        message = "We did not recognise your input. Please contact your clinic directly. Goodbye."
        label   = "unknown"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Aditi" language="en-IN">{message}</Say>
  <Hangup/>
</Response>"""
    return Response(content=twiml, media_type="application/xml")
