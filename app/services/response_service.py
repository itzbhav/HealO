from sqlalchemy.orm import Session

from app.models.response import Response
from app.models.patient import Patient
from app.schemas.response import ResponseCreate, ResponseResponse


def create_response(db: Session, response: ResponseCreate) -> ResponseResponse:
    patient = db.query(Patient).filter(Patient.id == response.patient_id).first()
    if not patient:
        raise ValueError(f"Patient ID {response.patient_id} not found")

    response_obj = Response(
        patient_id=response.patient_id,
        message_log_id=response.message_log_id,
        raw_text=response.raw_text,
        normalized_label=response.normalized_label,
        sentiment=response.sentiment,
        intent=response.intent,
        reply_latency_seconds=response.reply_latency_seconds
    )
    db.add(response_obj)
    db.commit()
    db.refresh(response_obj)
    return ResponseResponse.model_validate(response_obj)


def get_responses_by_patient(db: Session, patient_id: int):
    return db.query(Response).filter(Response.patient_id == patient_id).all()