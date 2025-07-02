from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

def now():
    return datetime.utcnow()

class ClassSession(Base):
    __tablename__ = "class_sessions"
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String)
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
    uuid = Column(String, nullable=False)
    session_id = Column(String, ForeignKey("class_sessions.id"))
    join_url = Column(String, nullable=False)
    scheduled_for = Column(DateTime, nullable=False)
    session = relationship("ClassSession", back_populates="meetings")