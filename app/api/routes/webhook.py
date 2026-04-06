from fastapi import APIRouter, Form
from fastapi.responses import Response
from app.core.groq_bot import get_bot_reply
from app.core.db_service import (
    get_patient_by_phone, log_message,
    get_upcoming_appointment, confirm_appointment,
    cancel_appointment, log_medication_taken
)

router = APIRouter(prefix="/webhook", tags=["webhook"])

def detect_intent(message: str) -> str:
    """Simple intent detection"""
    msg = message.lower()
    if any(w in msg for w in ["confirm", "yes confirm", "book"]):
        return "confirm_appointment"
    elif any(w in msg for w in ["cancel", "cancel appointment"]):
        return "cancel_appointment"
    elif any(w in msg for w in ["took", "taken", "yes meds", "had my meds"]):
        return "medication_taken"
    elif any(w in msg for w in ["didn't take", "not taken", "missed", "no meds"]):
        return "medication_missed"
    elif any(w in msg for w in ["appointment", "when is", "my appointment"]):
        return "check_appointment"
    else:
        return "general"

@router.post("/whatsapp")
async def whatsapp_webhook(Body: str = Form(...), From: str = Form(...)):
    phone = From.replace("whatsapp:", "")
    message = Body.strip()
    intent = detect_intent(message)

    # 1. Log inbound message
    patient = get_patient_by_phone(phone)
    patient_id = patient["id"] if patient else None
    log_message(phone, "inbound", message, intent, patient_id)

    # 2. Build context for LLM
    if patient:
        appt = get_upcoming_appointment(patient_id)

        # 3. Handle intents with DB actions
        if intent == "confirm_appointment" and appt:
            confirm_appointment(patient_id)
            context = f"Patient {patient['full_name']} just confirmed their appointment on {appt['appointment_date']} at {appt['appointment_time']} with {appt['doctor_name']}. Celebrate briefly!"

        elif intent == "cancel_appointment" and appt:
            cancel_appointment(patient_id)
            context = f"Patient {patient['full_name']} cancelled their appointment on {appt['appointment_date']}. Acknowledge and suggest rescheduling."

        elif intent == "medication_taken":
            log_medication_taken(patient_id, taken=True)
            context = f"Patient {patient['full_name']} confirmed they took their {patient['disease']} medication today. Praise them warmly!"

        elif intent == "medication_missed":
            log_medication_taken(patient_id, taken=False)
            context = f"Patient {patient['full_name']} missed their {patient['disease']} medication. Gently encourage them to take it now."

        elif intent == "check_appointment" and appt:
            context = f"Patient {patient['full_name']} is asking about their appointment. Tell them: {appt['appointment_date']} at {appt['appointment_time']} with {appt['doctor_name']} ({appt['specialty']}). Status: {appt['status']}."

        elif intent == "confirm_appointment" and not appt:
            context = f"Patient {patient['full_name']} wants to confirm an appointment but no scheduled appointment found in DB. Apologize and suggest contacting clinic."

        else:
            context = f"Patient: {patient['full_name']}, Disease: {patient['disease']}, Doctor: {patient['doctor_name']}. They said: '{message}'. Respond helpfully."

    else:
        # Unknown patient - not in DB
        context = f"Unknown patient (phone: {phone}). Tell them they are not registered in HealO yet and to contact their clinic."

    # 4. Get LLM reply with DB-grounded context
    reply = get_bot_reply(phone, f"[CONTEXT: {context}]\nPatient said: {message}")

    # 5. Log outbound message
    log_message(phone, "outbound", reply, None, patient_id)

    # 6. Send TwiML response
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response><Message>{reply}</Message></Response>"""
    return Response(content=twiml, media_type="application/xml")