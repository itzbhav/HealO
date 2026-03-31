from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.patients import router as patients_router
from app.api.routes.messages import router as messages_router
from app.api.routes.webhook import router as webhook_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description="Backend API for HealO medication adherence system",
    version="0.1.0"
)

app.include_router(health_router)
app.include_router(patients_router)
app.include_router(messages_router)
app.include_router(webhook_router)


@app.get("/")
def root():
    return {
        "message": f"{settings.app_name} is running",
        "environment": settings.app_env
    }