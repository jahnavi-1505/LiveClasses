# backend/controllers/meetings.py

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import timedelta

from ..database import get_db
from .. import models, schemas
from ..services.zoom_service import create_zoom_meeting

router = APIRouter(
    prefix="/sessions/{session_id}/meetings",
    tags=["meetings"],
)

@router.get("/", response_model=List[schemas.MeetingOut])
async def list_meetings(
    session_id: str,
    db: Session = Depends(get_db),
):
    """
    List all meetings for a session.
    """
    sess = db.get(models.ClassSession, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess.meetings


@router.post("/", response_model=schemas.MeetingOut)
async def schedule_meeting(
    session_id: str,
    payload: schemas.MeetingCreate,
    db: Session = Depends(get_db),
):
    """
    Schedule a new Zoom meeting and persist it.
    """
    sess = db.get(models.ClassSession, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    # Create the Zoom meeting
    start = payload.scheduled_for
    end = start + timedelta(hours=1)
    zm = await create_zoom_meeting(sess.title, start, end)

    # Save to our database
    mid = str(zm["id"])
    meeting = models.Meeting(
        id=mid,
        uuid=zm["uuid"],
        session_id=session_id,
        join_url=zm.get("join_url", ""),
        scheduled_for=start,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    return meeting
