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


# Folder watch Schemas
class FolderWatchCreate(BaseModel):
    folder_path: str


class FolderWatchResponse(BaseModel):
    id: int
    event_id: int
    folder_path: str
    enabled: bool
    created_at: datetime
    last_scan_at: Optional[datetime] = None
    watching: bool = False
    photo_count: int = 0

    class Config:
        from_attributes = True


class RescanResponse(BaseModel):
    uploaded: int


class PhotoIdsRequest(BaseModel):
    photo_ids: List[int]


# Privacy / DPDP Schemas
class ConsentRecord(BaseModel):
    id: int
    ip_address: Optional[str] = None
    consent_version: Optional[str] = None
    consent_text: Optional[str] = None
    user_agent: Optional[str] = None
    consent_timestamp: datetime

    class Config:
        from_attributes = True


class RetentionUpdate(BaseModel):
    # null/None = keep forever; else purge N days after event_date.
    retention_days: Optional[int] = None


class PrivacySummary(BaseModel):
    event_id: int
    consent_count: int
    photos_count: int
    retention_days: Optional[int] = None
    scheduled_purge_at: Optional[datetime] = None


class EraseResponse(BaseModel):
    consents_deleted: int
    downloads_deleted: int
    activity_deleted: int


# API token (desktop agent) Schemas
class ApiTokenCreate(BaseModel):
    name: str = "agent"


class ApiTokenInfo(BaseModel):
    id: int
    name: Optional[str] = None
    token_prefix: Optional[str] = None
    revoked: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApiTokenCreated(ApiTokenInfo):
    token: str  # plaintext — shown exactly once
