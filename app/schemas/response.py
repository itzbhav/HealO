from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ResponseBase(BaseModel):
    patient_id: int
    message_log_id: Optional[int] = None
    raw_text: str
    normalized_label: Optional[str] = None
    sentiment: Optional[str] = None
    intent: Optional[str] = None
    reply_latency_seconds: Optional[int] = None


class ResponseCreate(ResponseBase):
    pass


class ResponseResponse(ResponseBase):
    id: int
    received_at: datetime

    class Config:
        from_attributes = True