import os
from uuid import uuid4
from datetime import datetime, timedelta
from typing import List, Optional

import aiohttp
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, String, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# ─── Import your Zoom token helper ──────────────────────────────────────────────
from oauth_token import get_zoom_oauth_token

# ─── Load Config ───────────────────────────────────────────────────────────────
load_dotenv()

DATABASE_URL       = os.getenv("DATABASE_URL")
ZOOM_USER_ID       = os.getenv("ZOOM_USER_ID")       # Zoom user’s email or ID

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")
if not ZOOM_USER_ID:
    raise RuntimeError("Zoom credentials not fully set. Require ZOOM_USER_ID.")

# ─── Database Setup ────────────────────────────────────────────────────────────
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def now():
    return datetime.utcnow()

class ClassSession(Base):
    __tablename__ = "class_sessions"
    id          = Column(String, primary_key=True, index=True)
    title       = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at  = Column(DateTime, default=now)
    participants = relationship(
        "Participant", back_populates="session", cascade="all, delete-orphan"
    )
    meetings    = relationship(
        "Meeting", back_populates="session", cascade="all, delete-orphan"
    )

class Participant(Base):
    __tablename__ = "participants"
    id         = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("class_sessions.id"))
    email      = Column(String, nullable=False)
    role       = Column(String, default="student")
    session    = relationship("ClassSession", back_populates="participants")

class Meeting(Base):
    __tablename__ = "meetings"
    id            = Column(String, primary_key=True, index=True)
    session_id    = Column(String, ForeignKey("class_sessions.id"))
    join_url      = Column(String, nullable=False)
    scheduled_for = Column(DateTime, nullable=False)
    session       = relationship("ClassSession", back_populates="meetings")

def init_db():
    Base.metadata.create_all(bind=engine)

# ─── Pydantic Schemas ──────────────────────────────────────────────────────────
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

# ─── Dependencies ──────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ─── Zoom Meeting Creation ─────────────────────────────────────────────────────
def _iso(dt: datetime) -> str:
    return dt.isoformat()



async def create_zoom_meeting(
    subject: str,
    start: datetime,
    end: datetime
) -> dict:
    """
    Schedules a Zoom meeting via your oauth_token.get_zoom_oauth_token().
    """
    # 1. Fetch a fresh Zoom OAuth token
    zoom_token = await get_zoom_oauth_token()
    print("🔍 Zoom token (first 20 chars):", zoom_token[:20])

    # 2. Build the Zoom Create Meeting request
    url = f"https://api.zoom.us/v2/users/{ZOOM_USER_ID}/meetings"
    payload = {
        "topic": subject,
        "type": 2,  # scheduled meeting
        "start_time": start.isoformat(),
        "duration": int((end - start).total_seconds() / 60),
        "timezone": "UTC"
    }
    headers = {
        "Authorization": f"Bearer {zoom_token}",
        "Content-Type": "application/json"
    }

    # 3. Execute the POST
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise HTTPException(status_code=resp.status,
                    detail=f"Zoom API error: {text}")
            return await resp.json()

# ─── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(title="Zoom Live-Class Backend")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
  CORSMiddleware,
  allow_origins=["http://localhost:3000"],  # <-- front-end URL
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

@app.post("/sessions/{session_id}/meetings", response_model=MeetingOut)
async def schedule_meeting(
    session_id: str,
    payload: MeetingCreate,
    db: Session = Depends(get_db)
) -> MeetingOut:
    sess = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    start = payload.scheduled_for
    end   = start + timedelta(hours=1)

    zoom_meeting = await create_zoom_meeting(sess.title, start, end)
    meet_id   = str(zoom_meeting["id"])
    join_url  = zoom_meeting["join_url"]

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
