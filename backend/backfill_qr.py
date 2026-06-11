"""One-off backfill: regenerate + upload QR images for events whose S3 object
is missing (created during the silent-swallow era when upload failures were
hidden and qr_code_path was set without the object ever landing).

Run from backend/:  ../.venv/Scripts/python.exe backfill_qr.py
"""
import os
from io import BytesIO
import qrcode
from dotenv import load_dotenv

load_dotenv()

from app.database import SessionLocal
from app.models import models
from app.services.s3_service import s3_service

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


def main():
    db = SessionLocal()
    fixed, ok, failed = 0, 0, 0
    try:
        for event in db.query(models.Event).all():
            key = event.storage_key or event.qr_code_path
            if not key:
                continue
            if s3_service.file_exists(key):
                ok += 1
                continue

            # Missing object — regenerate and upload.
            url = f"{FRONTEND_URL}/event/{event.event_slug}"
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)

            if s3_service.upload_file(buf, key, "image/png"):
                # Ensure DB fields are consistent.
                event.qr_code_path = key
                event.storage_key = key
                event.storage_provider = "s3"
                db.commit()
                print(f"FIXED event id={event.id} slug={event.event_slug} key={key}")
                fixed += 1
            else:
                print(f"FAILED event id={event.id} slug={event.event_slug} key={key}")
                failed += 1
    finally:
        db.close()
    print(f"\nDone. already_ok={ok} fixed={fixed} failed={failed}")


if __name__ == "__main__":
    main()
