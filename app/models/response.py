from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class Response(Base):
    __tablename__ = "responses"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    message_log_id = Column(Integer, ForeignKey("message_logs.id"), nullable=True)
    raw_text = Column(Text, nullable=False)
    normalized_label = Column(String(30), nullable=True)
    sentiment = Column(String(30), nullable=True)
    intent = Column(String(50), nullable=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    reply_latency_seconds = Column(Integer, nullable=True)