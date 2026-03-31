from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.patients import get_db
from app.schemas.message import MessageCreate, MessageResponse
from app.services.message_service import create_message_log, get_message_logs_by_patient

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.post("/", response_model=MessageResponse)
def create_message(message: MessageCreate, db: Session = Depends(get_db)):
    try:
        return create_message_log(db, message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/patient/{patient_id}", response_model=list[MessageResponse])
def get_patient_messages(patient_id: int, db: Session = Depends(get_db)):
    messages = get_message_logs_by_patient(db, patient_id)
    return messages