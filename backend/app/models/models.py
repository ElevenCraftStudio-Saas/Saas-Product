from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, JSON, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import datetime
import enum
from ..database import Base

class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    firebase_uid = Column(String, unique=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, nullable=True)
    role = Column(String, nullable=False, default="user")  # admin | user
    max_events = Column(Integer, nullable=True)        # null = DEFAULT_EVENT_LIMIT
    storage_limit_mb = Column(Integer, nullable=True)  # null = DEFAULT_STORAGE_LIMIT_MB
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    events = relationship("Event", back_populates="photographer")

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    event_date = Column(DateTime)
    event_slug = Column(String, unique=True, index=True)
    qr_code_path = Column(String)
    storage_provider = Column(String, default="local")  # "local" or "s3"
    storage_key = Column(String, nullable=True)
    # DPDP: null = keep forever; else auto-purge photos+faces N days after event_date.
    retention_days = Column(Integer, nullable=True)
    consent_text = Column(String, nullable=True)  # custom consent wording for this event
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    photographer_id = Column(Integer, ForeignKey("users.id"))

    photographer = relationship("User", back_populates="events")
    photos = relationship("Photo", back_populates="event", cascade="all, delete-orphan")

class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), index=True)
    filename = Column(String)
    filepath = Column(String)
    storage_provider = Column(String, default="local") # "local" or "s3"
    storage_key = Column(String, nullable=True)
    processing_status = Column(String, default=ProcessingStatus.PENDING)
    size_bytes = Column(Integer, nullable=True)  # bytes stored, for storage-quota accounting
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    event = relationship("Event", back_populates="photos")
    face_embeddings = relationship("FaceEmbedding", back_populates="photo", cascade="all, delete-orphan")
    downloads = relationship("Download", back_populates="photo", cascade="all, delete-orphan")

class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    photo_id = Column(Integer, ForeignKey("photos.id"), index=True)
    embedding = Column(JSON)  # Store list of floats
    face_box = Column(JSON)   # Store [x1, y1, x2, y2]
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    photo = relationship("Photo", back_populates="face_embeddings")

class Download(Base):
    __tablename__ = "downloads"

    id = Column(Integer, primary_key=True, index=True)
    photo_id = Column(Integer, ForeignKey("photos.id"))
    ip_address = Column(String, nullable=True)
    downloaded_at = Column(DateTime(timezone=True), server_default=func.now())

    photo = relationship("Photo", back_populates="downloads")


class GuestConsent(Base):
    __tablename__ = "guest_consents"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), index=True)
    ip_address = Column(String, nullable=True)
    consent_version = Column(String, default="1.0")
    consent_text = Column(String, nullable=True)   # exact wording the guest agreed to (proof)
    user_agent = Column(String, nullable=True)     # extra evidence
    consent_timestamp = Column(DateTime(timezone=True), server_default=func.now())


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, index=True)  # EVENT_VIEWED, SELFIE_UPLOADED, FACE_MATCH_COMPLETED, PHOTO_DOWNLOADED
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True, index=True)
    photo_id = Column(Integer, ForeignKey("photos.id"), nullable=True)
    ip_address = Column(String, nullable=True)
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ApiToken(Base):
    """Long-lived API key for the desktop ingest agent (non-Firebase auth)."""
    __tablename__ = "api_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    name = Column(String)                 # human label (e.g. "Studio laptop")
    token_prefix = Column(String, index=True)  # first chars, for display + lookup
    token_hash = Column(String, unique=True)   # sha256 of the full token
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")


class FolderWatch(Base):
    __tablename__ = "folder_watches"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), index=True)  # multiple folders per event
    folder_path = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_scan_at = Column(DateTime(timezone=True), nullable=True)
