from sqlalchemy.orm import Session

from app.models.message_log import MessageLog
from app.models.patient import Patient
from app.schemas.message import MessageCreate, MessageResponse


def create_message_log(db: Session, message: MessageCreate) -> MessageResponse:
    patient = db.query(Patient).filter(Patient.id == message.patient_id).first()
    if not patient:
        raise ValueError(f"Patient ID {message.patient_id} not found")

    message_log = MessageLog(
        patient_id=message.patient_id,
        message_type=message.message_type,
        message_content=message.message_content,
        language=message.language
    )
    db.add(message_log)
    db.commit()
    db.refresh(message_log)
    return MessageResponse.model_validate(message_log)


def get_message_logs_by_patient(db: Session, patient_id: int):
    return db.query(MessageLog).filter(MessageLog.patient_id == patient_id).all()