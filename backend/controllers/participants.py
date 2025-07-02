from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import uuid4
from typing import List
from .. import models, schemas
from ..database import get_db
from ..services.email_service import send_email_with_ics
from ..utils.ics_utils import build_placeholder_ics

router = APIRouter(prefix="/sessions/{session_id}/participants", tags=["participants"])

@router.post("/", response_model=List[schemas.ParticipantOut])
async def add_participants(
    session_id: str,
    payload: schemas.ParticipantCreate,
    db: Session = Depends(get_db)
):
    sess = db.query(models.ClassSession).get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    created = []
    for email in payload.emails:
        pid = str(uuid4())
        p = models.Participant(id=pid, session_id=session_id, email=email, role=payload.role)
        db.add(p)
        created.append(p)
    db.commit()
    ics = build_placeholder_ics(session_id, sess.title, sess.description or "")
    await send_email_with_ics([p.email for p in created], f"Invited to session: {sess.title}",
                              f"You are invited to {sess.title}", ics, "session_invite.ics")
    return created