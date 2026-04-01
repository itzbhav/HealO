from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.twilio_whatsapp import send_reminder

router = APIRouter(prefix="/reminders", tags=["reminders"])

class ReminderRequest(BaseModel):
    phone: str
    date: str
    time: str
    doctor: str = "Dr. Priya"

@router.post("/send")
async def send_reminder_endpoint(req: ReminderRequest):
    try:
        sid = send_reminder(req.phone, req.date, req.time, req.doctor)
        return {"status": "sent", "sid": sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))