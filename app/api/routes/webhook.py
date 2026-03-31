from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.patients import get_db
from app.schemas.response import ResponseCreate, ResponseResponse
from app.services.response_service import create_response

router = APIRouter(prefix="/webhook", tags=["Webhook"])


@router.post("/whatsapp", response_model=dict)
def whatsapp_webhook(payload: dict, db: Session = Depends(get_db)):
    # Simulate WhatsApp webhook payload parsing
    if "entry" not in payload or not payload["entry"]:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    entry = payload["entry"][0]
    if "changes" not in entry:
        raise HTTPException(status_code=400, detail="No changes in webhook")

    change = entry["changes"][0]
    messages = change.get("value", {}).get("messages", [])
    
    for message in messages:
        phone = message["from"]
        raw_text = message["text"]["body"]
        
        # Find patient by phone number (in real app, this would use phone lookup)
        # For now, assume patient_id=1
        response = ResponseCreate(
            patient_id=1,
            raw_text=raw_text,
            normalized_label="YES" if "yes" in raw_text.lower() else "NO" if "no" in raw_text.lower() else "OTHER"
        )
        create_response(db, response)
    
    return {"status": "received", "processed": len(messages)}


@router.get("/whatsapp")
def verify_whatsapp_webhook(hub_mode: str, hub_verify_token: str, hub_challenge: str):
    # WhatsApp webhook verification
    if hub_mode == "subscribe" and hub_verify_token == "healo_verify_token":
        return hub_challenge
    raise HTTPException(status_code=403, detail="Forbidden")