"""
HealO WhatsApp - Twilio Sandbox (Phase 1)
Later: Switch to Meta API (Phase 2)
"""
from twilio.rest import Client
from dotenv import load_dotenv
import os

load_dotenv()

# Twilio Sandbox Client
_client = Client(
    os.getenv('TWILIO_ACCOUNT_SID'),
    os.getenv('TWILIO_AUTH_TOKEN')
)

def send_reminder(phone: str, date: str, time: str, doctor: str = "Dr. Priya") -> str:
    message = _client.messages.create(
        from_=os.getenv('TWILIO_WHATSAPP_FROM'),
        content_sid=os.getenv('TWILIO_CONTENT_SID'),
        content_variables=f'{{"1":"{date} with {doctor}","2":"{time}"}}',  # ← doctor added here
        to=f'whatsapp:{phone}'
    )
    print(f"✅ HealO → {phone}: {date} {time} w/ {doctor} | SID: {message.sid}")
    return message.sid

# Test function
if __name__ == "__main__":
    send_reminder("917418445928", "12/2", "4pm", "Dr. Priya")