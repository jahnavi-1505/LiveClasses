from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import uuid4
import os
import aiohttp

from sqlalchemy import Column, String, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

from dotenv import load_dotenv
load_dotenv()

# Read database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
def now():
    return datetime.utcnow()

class ClassSession(Base):
    __tablename__ = "class_sessions"
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=now)
    participants = relationship("Participant", back_populates="session", cascade="all, delete-orphan")
    meetings = relationship("Meeting", back_populates="session", cascade="all, delete-orphan")

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

# Create tables on startup
def init_db():
    Base.metadata.create_all(bind=engine)

# Pydantic Schemas
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

# Dependencies
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_user_token(authorization: str = Header(...)) -> str:
    try:
        scheme, token = authorization.split()
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authorization scheme must be Bearer")
    return token

async def schedule_teams_event(
    user_token: str,
    subject: str,
    start: datetime,
    end: datetime,
    attendees: List[str]
) -> dict:
    """
    (Deprecated) Schedules a calendar event with Teams meeting. Mailbox required.
    """
    url = "https://graph.microsoft.com/v1.0/me/events"
    # existing implementation... (not used)
    raise RuntimeError("Use create_online_meeting instead of schedule_teams_event")

async def create_online_meeting(
    user_token: str,
    subject: str,
    start: datetime,
    end: datetime
) -> dict:
    """
    Calls Graph /me/onlineMeetings to generate a Teams meeting join link.
    """
    url = "https://graph.microsoft.com/v1.0/me/onlineMeetings"
    payload = {
        "startDateTime": {"dateTime": start.isoformat(), "timeZone": "UTC"},
        "endDateTime":   {"dateTime": end.isoformat(),   "timeZone": "UTC"},
        "subject": subject
    }
    headers = {
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise HTTPException(status_code=resp.status, detail=f"Graph error: {text}")
            return await resp.json()

# FastAPI app
app = FastAPI(title="Teams Live-Class Backend")

@app.on_event("startup")
async def on_startup():
    init_db()

@app.post("/sessions", response_model=SessionOut)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db)
):
    session_id = str(uuid4())
    db_session = ClassSession(id=session_id, title=payload.title, description=payload.description)
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
        participant = Participant(id=part_id, session_id=session_id, email=email, role=payload.role)
        db.add(participant)
        created.append(participant)
    db.commit()
    return created

@app.post("/sessions/{session_id}/meetings", response_model=MeetingOut)
async def schedule_meeting(
    session_id: str,
    payload: MeetingCreate,
    db: Session = Depends(get_db),
    user_token: str = Depends(get_user_token)
):
    sess = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    start = payload.scheduled_for
    end = start + timedelta(hours=1)
    emails = [p.email for p in sess.participants]
    graph_event = await schedule_teams_event(user_token, sess.title, start, end, emails)
    meet_id = graph_event["id"]
    join_url = graph_event.get("onlineMeeting", {}).get("joinUrl")
    meeting = Meeting(id=meet_id, session_id=session_id, join_url=join_url, scheduled_for=start)
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