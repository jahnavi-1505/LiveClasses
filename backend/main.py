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

# ─── For sending emails asynchronously ───────────────────────────────────────────
import aiosmtplib
from email.message import EmailMessage

# ─── Load Config ───────────────────────────────────────────────────────────────
load_dotenv()

print(">> SMTP_HOST:", os.getenv("SMTP_HOST"))
print(">> SMTP_PORT:", os.getenv("SMTP_PORT"))
print(">> SMTP_USER:", os.getenv("SMTP_USER"))
print(">> SMTP_PASS starts with:", os.getenv("SMTP_PASS")[:4], "...")  
print(">> EMAIL_FROM:", os.getenv("EMAIL_FROM"))

DATABASE_URL = os.getenv("DATABASE_URL")
ZOOM_USER_ID = os.getenv("ZOOM_USER_ID")  # Zoom user’s email or ID
ZOOM_ACCOUNT_ID    = os.getenv("ZOOM_ACCOUNT_ID") 

# SMTP / email settings (for ICS invites)
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_FROM = os.getenv("EMAIL_FROM")

# Basic sanity checks
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")
if not ZOOM_USER_ID:
    raise RuntimeError("Zoom credentials not fully set. Require ZOOM_USER_ID.")
if not (SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASS and EMAIL_FROM):
    raise RuntimeError("SMTP_EMAIL settings are not fully set in .env")

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

# ─── Email Utility with ICS Attachment ──────────────────────────────────────────
async def send_email_with_ics(
    to_emails: List[str],
    subject: str,
    body: str,
    ics_content: str,
    ics_filename: str = "invite.ics"
) -> None:
    """
    Sends an email (async) with a plain-text body and an .ics calendar invite.
    """
    message = EmailMessage()
    message["From"] = EMAIL_FROM
    message["To"] = ", ".join(to_emails)
    message["Subject"] = subject
    message.set_content(body)

    # Attach the ICS file
    message.add_attachment(
        ics_content.encode("utf-8"),
        maintype="text",
        subtype="calendar",
        filename=ics_filename,
        params={"method": "REQUEST", "charset": "UTF-8"}
    )

    await aiosmtplib.send(
        message,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER,
        password=SMTP_PASS,
        start_tls=True
    )

# ─── Zoom Meeting Creation ─────────────────────────────────────────────────────
def _iso(dt: datetime) -> str:
    return dt.isoformat()

async def create_zoom_meeting(
    subject: str,
    start: datetime,
    end: datetime
) -> dict:
    """
    Schedules a Zoom meeting via oauth_token.get_zoom_oauth_token().
    """
    zoom_token = await get_zoom_oauth_token()

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

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise HTTPException(
                    status_code=resp.status,
                    detail=f"Zoom API error: {text}"
                )
            return await resp.json()

# ─── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(title="Zoom Live-Class Backend")

# CORS for your Next.js frontend (http://localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
async def add_participants(
    session_id: str,
    payload: ParticipantCreate,
    db: Session = Depends(get_db)
):
    """
    Add participants to a session, store them in DB,
    and email each new participant a placeholder .ics invite.
    """
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

    # Build a “placeholder” ICS since no meeting is scheduled yet
    now_dt = datetime.utcnow()
    uid = f"{session_id}@live-classes"
    ics_placeholder = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//Live Classes//EN\n"
        "METHOD:REQUEST\n"
        "BEGIN:VEVENT\n"
        f"UID:{uid}\n"
        f"DTSTAMP:{now_dt.strftime('%Y%m%dT%H%M%SZ')}\n"
        f"DTSTART:{now_dt.strftime('%Y%m%dT%H%M%SZ')}\n"
        f"DTEND:{(now_dt + timedelta(hours=1)).strftime('%Y%m%dT%H%M%SZ')}\n"
        f"SUMMARY:{sess.title} (not yet scheduled)\n"
        "END:VEVENT\n"
        "END:VCALENDAR"
    )

    to_addresses = [p.email for p in created]
    subject = f"Invited to session: {sess.title}"
    body = (
        f"Hello,\n\n"
        f"You’ve been added as a {payload.role} to “{sess.title}”.\n"
        f"Description: {sess.description or 'No description'}\n\n"
        f"A calendar invite is attached. When a meeting is scheduled, you’ll receive an updated invite with the Zoom link.\n\n"
        f"Best regards,\nLive Classes Team"
    )

    try:
        await send_email_with_ics(to_addresses, subject, body, ics_placeholder, "session_invite.ics")
    except Exception as e:
        print(f"⚠️ Failed to send participant invite ICS: {e}")

    return created

@app.post("/sessions/{session_id}/meetings", response_model=MeetingOut)
async def schedule_meeting(
    session_id: str,
    payload: MeetingCreate,
    db: Session = Depends(get_db)
) -> MeetingOut:
    """
    Schedule a Zoom meeting, store in DB, then email all participants a real ICS with Zoom link.
    """
    sess = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    start = payload.scheduled_for
    end   = start + timedelta(hours=1)

    zoom_meeting = await create_zoom_meeting(sess.title, start, end)
    meet_id   = str(zoom_meeting["id"])
    join_url  = zoom_meeting.get("join_web_url", zoom_meeting.get("join_url", ""))

    meeting = Meeting(
        id=meet_id,
        session_id=session_id,
        join_url=join_url,
        scheduled_for=start
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # Build a proper ICS for the scheduled Zoom meeting
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dtstart = start.strftime("%Y%m%dT%H%M%SZ")
    dtend   = end.strftime("%Y%m%dT%H%M%SZ")
    uid = f"{meet_id}@live-classes"

    ics_event = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//Live Classes//EN\n"
        "METHOD:REQUEST\n"
        "BEGIN:VEVENT\n"
        f"UID:{uid}\n"
        f"DTSTAMP:{dtstamp}\n"
        f"DTSTART:{dtstart}\n"
        f"DTEND:{dtend}\n"
        f"SUMMARY:{sess.title}\n"
        f"DESCRIPTION:Join Zoom Meeting: {join_url}\\n\\n{sess.description or ''}\n"
        f"LOCATION:{join_url}\n"
        "END:VEVENT\n"
        "END:VCALENDAR"
    )

    if sess.participants:
        to_addresses = [p.email for p in sess.participants]
        subject = f"Zoom meeting scheduled for session: {sess.title}"
        body = (
            f"Hello,\n\n"
            f"The Zoom meeting for session “{sess.title}” has been scheduled.\n"
            f"Join URL: {join_url}\n"
            f"Scheduled For: {start.isoformat()}\n\n"
            f"Please find the calendar invite attached.\n\n"
            f"Best regards,\nLive Classes Team"
        )
        try:
            await send_email_with_ics(to_addresses, subject, body, ics_event, "meeting_invite.ics")
        except Exception as e:
            print(f"⚠️ Failed to send meeting invite ICS: {e}")

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

# 1️⃣ List all meetings for a session
@app.get("/sessions/{session_id}/meetings", response_model=List[MeetingOut])
def list_meetings(
    session_id: str,
    db: Session = Depends(get_db)
):
    sess = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not sess:
        raise HTTPException(404, "Session not found")
    return sess.meetings

# 2️⃣ Get a single meeting’s details
@app.get("/sessions/{session_id}/meetings/{meeting_id}", response_model=MeetingOut)
def get_meeting(
    session_id: str,
    meeting_id: str,
    db: Session = Depends(get_db)
):
    meet = (
        db.query(Meeting)
          .filter(Meeting.session_id == session_id, Meeting.id == meeting_id)
          .first()
    )
    if not meet:
        raise HTTPException(404, "Meeting not found")
    return meet

# 3️⃣ Update (reschedule) a meeting
class MeetingUpdate(BaseModel):
    scheduled_for: datetime

@app.patch("/sessions/{session_id}/meetings/{meeting_id}", response_model=MeetingOut)
async def update_meeting(
    session_id: str,
    meeting_id: str,
    payload: MeetingUpdate,
    db: Session = Depends(get_db)
):
    meet = (
        db.query(Meeting)
          .filter(Meeting.session_id == session_id, Meeting.id == meeting_id)
          .first()
    )
    if not meet:
        raise HTTPException(404, "Meeting not found")

    new_start = payload.scheduled_for
    new_end   = new_start + timedelta(hours=1)

    # 1) Patch Zoom
    zoom_token = await get_zoom_oauth_token()
    url = f"https://api.zoom.us/v2/meetings/{meeting_id}"
    patch_payload = {
        "start_time": new_start.isoformat(),
        "duration": int((new_end - new_start).total_seconds() / 60)
    }
    headers = {
        "Authorization": f"Bearer {zoom_token}",
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        async with session.patch(url, json=patch_payload, headers=headers) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise HTTPException(resp.status, f"Zoom API error: {text}")

    # 2) Update our DB record
    meet.scheduled_for = new_start
    db.commit()
    db.refresh(meet)
    return meet

# 4️⃣ Remove a participant
@app.delete("/sessions/{session_id}/participants/{participant_id}", status_code=204)
def delete_participant(
    session_id: str,
    participant_id: str,
    db: Session = Depends(get_db)
):
    part = (
        db.query(Participant)
          .filter(
              Participant.session_id == session_id,
              Participant.id == participant_id
          )
          .first()
    )
    if not part:
        raise HTTPException(404, "Participant not found")
    db.delete(part)
    db.commit()
    return None


@app.post("/sessions/{session_id}/send-invites")
async def send_invites(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Look up the session by ID, find its most recent meeting (Zoom),
    build an ICS with the Zoom link, and send an invite to every participant.
    """
    # 1. Fetch the session
    sess = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    # 2. Fetch the latest meeting (assumes only one or you want the last one)
    if not sess.meetings:
        raise HTTPException(status_code=400, detail="No meeting scheduled yet for this session")
    # Here we pick the most recent by scheduled_for – you can also just take sess.meetings[-1]
    latest_meeting = sorted(sess.meetings, key=lambda m: m.scheduled_for)[-1]

    # 3. Build the .ics content using that meeting’s join_url and scheduled_for
    start = latest_meeting.scheduled_for
    end = start + timedelta(hours=1)

    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dtstart = start.strftime("%Y%m%dT%H%M%SZ")
    dtend = end.strftime("%Y%m%dT%H%M%SZ")
    uid = f"{latest_meeting.id}@live-classes"

    ics_event = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//Live Classes//EN\n"
        "METHOD:REQUEST\n"
        "BEGIN:VEVENT\n"
        f"UID:{uid}\n"
        f"DTSTAMP:{dtstamp}\n"
        f"DTSTART:{dtstart}\n"
        f"DTEND:{dtend}\n"
        f"SUMMARY:{sess.title}\n"
        f"DESCRIPTION:Join Zoom Meeting: {latest_meeting.join_url}\\n\\n{sess.description or ''}\n"
        f"LOCATION:{latest_meeting.join_url}\n"
        "END:VEVENT\n"
        "END:VCALENDAR"
    )

    # 4. Collect all participant emails
    emails = [p.email for p in sess.participants]
    if not emails:
        raise HTTPException(status_code=400, detail="No participants to invite")

    subject = f"Invitation: {sess.title} (Zoom Meeting)"
    body = (
        f"Hello,\n\n"
        f"You’re invited to the upcoming Zoom meeting for session “{sess.title}”.\n"
        f"Join URL: {latest_meeting.join_url}\n"
        f"Scheduled For: {start.isoformat()} UTC\n\n"
        f"Please find the attached calendar invite (.ics) and add it to your calendar.\n\n"
        f"Best regards,\nLive Classes Team"
    )


    try:
        await send_email_with_ics(emails, subject, body, ics_event, "meeting_invite.ics")
    except Exception as e:

        raise HTTPException(status_code=500, detail=f"Failed to send invites: {e}")

    return {"detail": f"Invites sent to {len(emails)} participants"}

