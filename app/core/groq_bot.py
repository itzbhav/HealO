from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Store conversation history per patient
conversation_history = {}

SYSTEM_PROMPT = """You are HealO, a friendly and caring AI health assistant 
that communicates via WhatsApp. You help patients with:
- Confirming or cancelling appointments
- Medication reminders and logging
- Rescheduling appointments
- General health queries

Rules:
- Keep replies SHORT (max 3 lines) — this is WhatsApp!
- Be warm, friendly, and encouraging 💊
- Use 1-2 relevant emojis per message
- If patient confirms appointment → log it and celebrate
- If patient says they took meds → praise them
- If patient says they didn't take meds → gently remind them
- For medical questions beyond your scope → say "Please consult your doctor"
- Never make up medical advice
- Always respond in the same language the patient uses"""

def get_bot_reply(phone: str, patient_message: str) -> str:
    """Get LLM reply for patient message with conversation memory"""

    # Initialize history for new patient
    if phone not in conversation_history:
        conversation_history[phone] = []

    # Add patient message to history
    conversation_history[phone].append({
        "role": "user",
        "content": patient_message
    })

    # Keep only last 10 messages (memory management)
    if len(conversation_history[phone]) > 10:
        conversation_history[phone] = conversation_history[phone][-10:]

    # Call Groq LLM
    response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",   # ← ONLY THIS LINE CHANGED
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        *conversation_history[phone]
    ],
    max_tokens=150,
    temperature=0.7
)

    bot_reply = response.choices[0].message.content

    # Save bot reply to history
    conversation_history[phone].append({
        "role": "assistant",
        "content": bot_reply
    })

    return bot_reply