import os
from uuid import uuid4
from datetime import datetime, timedelta
from typing import List, Optional

import aiohttp
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, String, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables\load_dotenv()
load_dotenv()
# Database URL from .env
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Utility for timestamp defaults
def now():
    return datetime.utcnow()

# Models
class ClassSession(Base):
    __tablename__ = "class_sessions"
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=now)
    participants = relationship(
        "Participant", back_populates="session", cascade="all, delete-orphan"
    )
    meetings = relationship(
        "Meeting", back_populates="session", cascade="all, delete-orphan"
    )

class Participant(Base):
    __tablename__ = "participants"
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("class_sessions.id"))
    email = Column(String, nullable=False)
    role = Column(String, default="student")
    session = relationship("ClassSession", back_populates="participants")

class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("class_sessions.id"))
    join_url = Column(String, nullable=False)
    scheduled_for = Column(DateTime, nullable=False)
    session = relationship("ClassSession", back_populates="meetings")

# Initialize DB tables
def init_db():
    Base.metadata.create_all(bind=engine)

# Pydantic schemas
class SessionCreate(BaseModel):
    title: str
    description: Optional[str] = None

class ParticipantCreate(BaseModel):
    emails: List[EmailStr]
    role: Optional[str] = "student"

class MeetingCreate(BaseModel):
    scheduled_for: datetime

class ParticipantOut(BaseModel):
    id: str
    email: EmailStr
    role: str

class MeetingOut(BaseModel):
    id: str
    join_url: str
    scheduled_for: datetime

class SessionOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    created_at: datetime
    participants: List[ParticipantOut]
    meetings: List[MeetingOut]

# Security scheme for Swagger
#bearer_scheme = HTTPBearer()

# Dependencies
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# Comment this out or leave unused
# bearer_scheme = HTTPBearer()

# Replace token injection with file-based one
def get_user_token_from_file() -> str:
    try:
        with open(".access_token", "r") as f:
            token = f.read().strip()
            return token
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Access token not found. Run token3.py first.")


# Microsoft Graph helper
def _iso(dt: datetime) -> str:
    return dt.isoformat()

async def create_online_meeting(
    user_token: str,
    subject: str,
    start: datetime,
    end: datetime
) -> dict:
    print("🔍 Access token used (first 40 chars):", user_token[:40])  # <-- Add this line

    url = "https://graph.microsoft.com/v1.0/me/onlineMeetings"
    payload = {
        "startDateTime": {"dateTime": _iso(start), "timeZone": "UTC"},
        "endDateTime":   {"dateTime": _iso(end),   "timeZone": "UTC"},
        "subject": subject
    }
    headers = {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise HTTPException(status_code=resp.status, detail=f"Graph error: {text}")
            return await resp.json()


# FastAPI application
app = FastAPI(title="Teams Live-Class Backend")


# allow swagger /docs to talk to your API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000"],  # or ["*"] for everything
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    init_db()

@app.post("/sessions", response_model=SessionOut)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db)
):
    session_id = str(uuid4())
    db_session = ClassSession(
        id=session_id,
        title=payload.title,
        description=payload.description
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

@app.get("/sessions", response_model=List[SessionOut])
def list_sessions(db: Session = Depends(get_db)):
    return db.query(ClassSession).all()

@app.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    sess = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess

@app.post("/sessions/{session_id}/participants", response_model=List[ParticipantOut])
def add_participants(
    session_id: str,
    payload: ParticipantCreate,
    db: Session = Depends(get_db)
):
    sess = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    created: List[Participant] = []
    for email in payload.emails:
        part_id = str(uuid4())
        participant = Participant(
            id=part_id,
            session_id=session_id,
            email=email,
            role=payload.role
        )
        db.add(participant)
        created.append(participant)
    db.commit()
    return created
def get_user_token_from_file() -> str:
    try:
        with open(".access_token", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Access token not found. Run token3.py first.")

@app.post("/sessions/{session_id}/meetings", response_model=MeetingOut)
async def schedule_meeting(
    session_id: str,
    payload: MeetingCreate,
    db: Session = Depends(get_db),
    user_token: str = get_user_token_from_file()
  # Force use of local token
) -> MeetingOut:

    sess = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    start = payload.scheduled_for
    end   = start + timedelta(hours=1)

    graph_meeting = await create_online_meeting(user_token, sess.title, start, end)
    meet_id     = graph_meeting.get("id")
    join_url    = graph_meeting.get("joinWebUrl")

    meeting = Meeting(
        id=meet_id,
        session_id=session_id,
        join_url=join_url,
        scheduled_for=start
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting

@app.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    sess = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(sess)
    db.commit()
    return None
