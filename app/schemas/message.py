from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MessageBase(BaseModel):
    patient_id: int
    message_type: str = "reminder"
    message_content: str
    language: str = "English"


class MessageCreate(MessageBase):
    pass


class MessageResponse(MessageBase):
    id: int
    sent_at: datetime
    delivery_status: str
    whatsapp_message_id: Optional[str] = None

    class Config:
        from_attributes = True