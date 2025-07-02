from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime

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

    class Config:
        orm_mode = True

class MeetingOut(BaseModel):
    id: str
    join_url: str
    scheduled_for: datetime

    class Config:
        orm_mode = True

class SessionOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    created_at: datetime
    participants: List[ParticipantOut]
    meetings: List[MeetingOut]

    class Config:
        orm_mode = True