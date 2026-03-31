from app.db.base import Base
from app.db.session import engine

# Import models so SQLAlchemy registers them
from app.models.patient import Patient
from app.models.medication import Medication
from app.models.message_log import MessageLog
from app.models.response import Response
from app.models.risk_score import RiskScore
from app.models.intervention import Intervention


def init_db():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database tables created successfully.")