from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import uuid4
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.post("/", response_model=schemas.SessionOut)
def create_session(payload: schemas.SessionCreate, db: Session = Depends(get_db)):
    session_id = str(uuid4())
    sess = models.ClassSession(id=session_id, title=payload.title, description=payload.description)
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess

@router.get("/", response_model=list[schemas.SessionOut])
def list_sessions(db: Session = Depends(get_db)):
    return db.query(models.ClassSession).all()

@router.get("/{session_id}", response_model=schemas.SessionOut)
def get_session(session_id: str, db: Session = Depends(get_db)):
    sess = db.query(models.ClassSession).get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    return sess

@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str, db: Session = Depends(get_db)):
    sess = db.query(models.ClassSession).get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    db.delete(sess)
    db.commit()