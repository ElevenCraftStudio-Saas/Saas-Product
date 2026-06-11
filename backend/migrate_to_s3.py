import os
import boto3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.models import Photo, Event
from app.services.s3_service import s3_service
from dotenv import load_dotenv

load_dotenv()

# Setup DB
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sql_app.db")
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def migrate_to_s3():
    db = SessionLocal()
    try:
        # 1. Migrate Event QR Codes
        events = db.query(Event).filter(Event.storage_provider == "local").all()
        print(f"Found {len(events)} events to migrate.")
        for event in events:
            if event.qr_code_path and os.path.exists(event.qr_code_path):
                s3_key = f"qr/{event.event_slug}_qr.png"
                with open(event.qr_code_path, "rb") as f:
                    if s3_service.upload_file(f, s3_key, "image/png"):
                        event.storage_provider = "s3"
                        event.storage_key = s3_key
                        event.qr_code_path = s3_key
                        print(f"Migrated Event QR: {event.id}")
        
        # 2. Migrate Photos
        photos = db.query(Photo).filter(Photo.storage_provider == "local").all()
        print(f"Found {len(photos)} photos to migrate.")
        for photo in photos:
            if photo.filepath and os.path.exists(photo.filepath):
                file_ext = photo.filepath.split(".")[-1]
                s3_key = f"events/{photo.event_id}/{os.path.basename(photo.filepath)}"
                
                content_type = "image/jpeg" if file_ext.lower() in ["jpg", "jpeg"] else "image/png"
                
                with open(photo.filepath, "rb") as f:
                    if s3_service.upload_file(f, s3_key, content_type):
                        photo.storage_provider = "s3"
                        photo.storage_key = s3_key
                        photo.filepath = s3_key
                        print(f"Migrated Photo: {photo.id}")
        
        db.commit()
        print("Migration completed successfully.")
    except Exception as e:
        print(f"Migration failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate_to_s3()
