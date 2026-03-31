from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class MessageLog(Base):
    __tablename__ = "message_logs"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    message_type = Column(String(50), nullable=False)
    message_content = Column(Text, nullable=False)
    language = Column(String(20), nullable=False, default="English")
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    delivery_status = Column(String(30), nullable=False, default="sent")
    whatsapp_message_id = Column(String(120), nullable=True)