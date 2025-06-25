import os
import traceback
from uuid import uuid4
from datetime import datetime, timedelta
from typing import List, Optional
import aiohttp
import aiofiles
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, String, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from azure.storage.blob.aio import BlobServiceClient
from oauth_token import get_zoom_oauth_token
from urllib.parse import quote_plus

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

# SMTP settings (for ICS invites)
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_FROM = os.getenv("EMAIL_FROM")

AZURE_CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER")

if not AZURE_CONN_STR or not AZURE_CONTAINER:
    raise RuntimeError("Missing AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_CONTAINER in .env")

# create one BlobServiceClient per process
blob_service = BlobServiceClient.from_connection_string(AZURE_CONN_STR)
container_client = blob_service.get_container_client(AZURE_CONTAINER)

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
    uuid          = Column(String, nullable=False)
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
        "timezone": "UTC",
        "settings": {
            "auto_recording": "cloud"   # <-- enable automatic cloud recording
        }
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
    meet_num = str(zoom_meeting["id"])
    meet_uuid = zoom_meeting["uuid"]
    join_url  = zoom_meeting.get("join_web_url", zoom_meeting.get("join_url", ""))

    meeting = Meeting(
        session_id=session_id,
        id=meet_num,
        uuid=meet_uuid,
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

@app.get("/sessions/{session_id}/recordings")
async def list_recordings(
    session_id: str,
    db: Session = Depends(get_db)
):
    sess = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    zoom_token = await get_zoom_oauth_token()
    headers = {"Authorization": f"Bearer {zoom_token}"}
    recordings = []

    async with aiohttp.ClientSession(headers=headers) as client:
        for meet in sess.meetings:
            url = f"https://api.zoom.us/v2/meetings/{meet.id}/recordings"
            async with client.get(url) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()
                for file in data.get("recording_files", []):
                    # append Zoom download token to URL
                    download_url = f"{file['download_url']}?access_token={zoom_token}"
                    recordings.append({
                        "meeting_id": meet.id,
                        "id": file.get("id"),
                        "file_type": file.get("file_type"),
                        "download_url": download_url,
                        "recording_start": file.get("recording_start"),
                        "recording_end": file.get("recording_end"),
                    })
    return {"recordings": recordings}

@app.get("/sessions/{session_id}/recordings")
async def list_recordings(
    session_id: str,
    db: Session = Depends(get_db)
):
    sess = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    zoom_token = await get_zoom_oauth_token()
    headers = {"Authorization": f"Bearer {zoom_token}"}
    recordings = []

    async with aiohttp.ClientSession(headers=headers) as client:
        for meet in sess.meetings:
            url = f"https://api.zoom.us/v2/meetings/{meet.id}/recordings"
            async with client.get(url) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()
                for file in data.get("recording_files", []):
                    recordings.append({
                        "meeting_id": meet.id,
                        "id": file.get("id"),
                        "file_type": file.get("file_type"),
                        "download_url": file["download_url"],
                        "recording_start": file.get("recording_start"),
                        "recording_end": file.get("recording_end"),
                    })
    return {"recordings": recordings}


@app.post("/sessions/{session_id}/store-recordings")
async def store_recordings_to_azure(
    session_id: str,
    db: Session = Depends(get_db)
):
    sess = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    zoom_token = await get_zoom_oauth_token()
    headers = {"Authorization": f"Bearer {zoom_token}"}
    stored = []

    async with aiohttp.ClientSession(headers=headers) as client:
        for meet in sess.meetings:
            list_url = f"https://api.zoom.us/v2/meetings/{meet.id}/recordings"
            
            print(f"Fetching recordings for meeting {meet.id}: {list_url}")
            
            async with client.get(list_url) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    print(f"Failed to list recordings for meeting {meet.id}: {resp.status} - {error_text}")
                    continue
                data = await resp.json()

            recording_files = data.get("recording_files", [])
            print(f"Found {len(recording_files)} recording files for meeting {meet.id}")

            for file in recording_files:
                try:
                    # Method 1: Try direct download with Bearer token
                    download_url = file['download_url']
                    print(f"Attempting download for file {file['id']} from: {download_url}")
                    
                    async with client.get(download_url) as dl:
                        if dl.status == 200:
                            content = await dl.read()
                            print(f"✅ Successfully downloaded {len(content)} bytes for file {file['id']}")
                        else:
                            # Method 2: Try with download_access_token query parameter
                            print(f"❌ Bearer method failed ({dl.status}), trying download_access_token method")
                            download_url_with_token = f"{download_url}?download_access_token={zoom_token}"
                            
                            async with client.get(download_url_with_token) as dl2:
                                if dl2.status == 200:
                                    content = await dl2.read()
                                    print(f"✅ Download_access_token method worked: {len(content)} bytes")
                                else:
                                    # Method 3: Try without any authentication (for public recordings)
                                    print(f"❌ download_access_token failed ({dl2.status}), trying without auth")
                                    async with aiohttp.ClientSession() as no_auth_client:
                                        async with no_auth_client.get(download_url) as dl3:
                                            if dl3.status == 200:
                                                content = await dl3.read()
                                                print(f"✅ No-auth method worked: {len(content)} bytes")
                                            else:
                                                error_text = await dl3.text()
                                                print(f"❌ All download methods failed. Last error: {dl3.status} - {error_text}")
                                                continue

                    # Create blob name and upload to Azure
                    ext = file["file_type"].lower()
                    blob_name = f"{session_id}/{meet.id}/{file['id']}.{ext}"

                    print(f"Uploading to Azure blob: {blob_name}")
                    
                    blob_client = container_client.get_blob_client(blob_name)
                    await blob_client.upload_blob(content, overwrite=True)

                    stored.append({
                        "meeting_id": meet.id,
                        "file_id": file["id"],
                        "blob_path": blob_name,
                        "file_size": len(content)
                    })
                    
                    print(f"Successfully stored file {file['id']} to {blob_name}")
                    
                except Exception as e:
                    print(f"Error processing file {file['id']}: {str(e)}")
                    continue

    if not stored:
        raise HTTPException(status_code=404, detail="No recordings found or uploaded")

    return {"stored": stored}


@app.post("/sessions/{session_id}/download-recordings-local")
async def download_recordings_locally(
    session_id: str,
    db: Session = Depends(get_db)
):
    sess = db.query(ClassSession).filter_by(id=session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get recordings list
    result = await list_recordings(session_id, db)
    recs = result.get("recordings", [])
    if not recs:
        raise HTTPException(status_code=404, detail="No recordings found to download")

    base_dir = os.path.join(r"C:\recordings", session_id)
    os.makedirs(base_dir, exist_ok=True)

    zoom_token = await get_zoom_oauth_token()
    saved = []

    # Try multiple download methods
    async with aiohttp.ClientSession() as client:
        for rec in recs:
            try:
                download_url = rec["download_url"]
                print(f"→ downloading file {rec['id']} from: {download_url}")
                
                data = None
                
                # Method 1: Bearer token in header
                headers_with_auth = {"Authorization": f"Bearer {zoom_token}"}
                async with client.get(download_url, headers=headers_with_auth, allow_redirects=True) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        print(f"✅ Bearer auth worked: {len(data)} bytes")
                    else:
                        print(f"❌ Bearer auth failed: {resp.status}")
                
                # Method 2: download_access_token parameter
                if data is None:
                    download_url_with_token = f"{download_url}?download_access_token={zoom_token}"
                    async with client.get(download_url_with_token, allow_redirects=True) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            print(f"✅ download_access_token worked: {len(data)} bytes")
                        else:
                            print(f"❌ download_access_token failed: {resp.status}")
                
                # Method 3: No authentication (public recordings)
                if data is None:
                    async with aiohttp.ClientSession() as no_auth_client:
                        async with no_auth_client.get(download_url, allow_redirects=True) as resp:
                            if resp.status == 200:
                                data = await resp.read()
                                print(f"✅ No-auth worked: {len(data)} bytes")
                            else:
                                body = await resp.text()
                                print(f"❌ All methods failed. Final error: {resp.status} - {body}")
                                continue

                if data is None:
                    print(f"❌ Could not download file {rec['id']} - all methods failed")
                    continue

                # Save to local file
                meet_dir = os.path.join(base_dir, str(rec["meeting_id"]))
                os.makedirs(meet_dir, exist_ok=True)
                
                ext = rec["file_type"].lower()
                outpath = os.path.join(meet_dir, f"{rec['id']}.{ext}")
                
                async with aiofiles.open(outpath, "wb") as f:
                    await f.write(data)

                print(f"✅ saved {outpath}")
                saved.append(outpath)
                
            except Exception as e:
                print(f"Error downloading file {rec['id']}: {str(e)}")
                continue

    if not saved:
        raise HTTPException(status_code=500, detail="Downloaded 0 files")

    return {"downloaded_files": saved}