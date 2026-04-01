from fastapi import APIRouter, Form
from fastapi.responses import Response
from app.core.groq_bot import get_bot_reply

router = APIRouter(prefix="/webhook", tags=["webhook"])

@router.post("/whatsapp")
async def whatsapp_webhook(
    Body: str = Form(...),
    From: str = Form(...)
):
    phone = From.replace("whatsapp:", "")
    patient_message = Body.strip()

    print(f"📩 {phone}: {patient_message}")

    # Get LLM reply
    reply = get_bot_reply(phone, patient_message)

    print(f"🤖 HealO: {reply}")

    # Send back via TwiML
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response><Message>{reply}</Message></Response>"""

    return Response(content=twiml, media_type="application/xml")