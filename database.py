from sqlalchemy import create_engine, Column, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./plum_escalations.db")

# Railway provides postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Escalation(Base):
    __tablename__ = "escalations"

    id = Column(String, primary_key=True, index=True)
    source = Column(String, index=True)          # email | slack | whatsapp
    sender_name = Column(String)
    sender_email = Column(String)
    company = Column(String, index=True)
    subject = Column(String)
    body = Column(Text)
    category = Column(String, index=True)        # Escalation | Complaint | Follow-up | Query | Initiation | Appreciation
    priority = Column(String, index=True)        # P1 | P2 | P3
    status = Column(String, index=True)          # open | in-progress | resolved
    assigned_to = Column(String)
    assigned_role = Column(String)
    ai_summary = Column(Text, nullable=True)
    ai_reply_draft = Column(Text, nullable=True)
    channel = Column(String, nullable=True)      # Slack channel name
    thread_ts = Column(String, nullable=True)    # Slack thread timestamp
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_live = Column(Boolean, default=False)     # True = from live connector, False = mock


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
