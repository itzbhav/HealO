from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Store conversation history per patient
conversation_history = {}

SYSTEM_PROMPT = """You are HealO, a clinical AI assistant communicating with patients via WhatsApp on behalf of their doctor and care team.

Your role:
- Confirm or log medication adherence
- Remind patients about missed doses
- Handle appointment confirmations and cancellations
- Answer basic health queries within your scope

Tone guidelines:
- Professional and clinical — you represent a hospital/clinic, not a wellness app
- Empathetic but concise — acknowledge the patient's situation without being overly casual
- Never use phrases like "Your body will thank you", "You've got this!", or similar motivational clichés
- Do NOT use more than one emoji per message; use none if the message is serious
- Address the patient by name once per reply, not repeatedly

Response format:
- Maximum 2 sentences — this is WhatsApp, not an email
- If the patient missed medication: acknowledge, state the clinical recommendation (take it now if less than X hours, skip if close to next dose), and note it has been logged for their doctor
- If the patient took medication: confirm it has been recorded
- For appointment actions: confirm the change clearly and state next steps
- For questions outside your scope: "Please contact your clinic or consult Dr. [name] directly."
- Never fabricate medical advice or dosage instructions
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
    max_tokens=120,
    temperature=0.3
)

    bot_reply = response.choices[0].message.content

    # Save bot reply to history
    conversation_history[phone].append({
        "role": "assistant",
        "content": bot_reply
    })

    return bot_reply