from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
from ..models.models import ProcessingStatus

# User Schemas
class UserResponse(BaseModel):
    id: int
    firebase_uid: Optional[str] = None
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

# Event Schemas
class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    event_date: datetime

class EventCreate(EventBase):
    pass

class EventResponse(EventBase):
    id: int
    event_slug: str
    qr_code_path: Optional[str] = None
    url: Optional[str] = None  # presigned S3 url for the QR image
    created_at: datetime
    photographer_id: int

    class Config:
        from_attributes = True

# Photo Schemas
class PhotoResponse(BaseModel):
    id: int
    event_id: int
    filename: str
    filepath: str
    url: Optional[str] = None
    processing_status: str
    uploaded_at: datetime

    class Config:
        from_attributes = True

# Guest flow Schemas
class GuestEventResponse(EventBase):
    id: int
    event_slug: str
    qr_code_path: Optional[str] = None
    url: Optional[str] = None  # presigned QR/banner url

    class Config:
        from_attributes = True


class GuestPhoto(BaseModel):
    id: int
    filename: str
    url: str


class SelfieMatchResponse(BaseModel):
    count: int
    photos: List[GuestPhoto]


class DownloadResponse(BaseModel):
    url: str
    expires_in: int
