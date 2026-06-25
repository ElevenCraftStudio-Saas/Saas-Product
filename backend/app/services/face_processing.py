from ..database import SessionLocal
from ..models import models
from .face_engine import face_engine
from .s3_service import s3_service
from ..core.metrics import photos_processed_total, faces_detected_total
import numpy as np
import logging
import os
import uuid

logger = logging.getLogger("wedfind.face")


def process_photo_faces(photo_id: int, raise_on_error: bool = False):
    """Detect faces in a photo and store embeddings.

    Idempotent: clears any existing embeddings for the photo first, so a retry
    (Celery acks_late) never double-inserts. With raise_on_error=True (the Celery
    path) the exception propagates so the task can retry; otherwise it is
    swallowed after marking the photo FAILED (the BackgroundTasks fallback).
    """
    db = SessionLocal()
    temp_path = None
    photo = None
    try:
        photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
        if not photo:
            return

        # Idempotency: drop prior embeddings before re-detecting.
        db.query(models.FaceEmbedding).filter(
            models.FaceEmbedding.photo_id == photo_id
        ).delete(synchronize_session=False)

        photo.processing_status = models.ProcessingStatus.PROCESSING
        db.commit()

        # Handle S3 vs Local
        image_path = photo.filepath
        if photo.storage_provider == "s3":
            # Download to temp file for processing
            from ..config import settings
            temp_dir = os.path.join(settings.UPLOAD_DIR, "temp_processing")
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}.jpg")
            success = s3_service.download_to_temp(photo.storage_key, temp_path)
            if not success:
                raise Exception("Failed to download from S3")
            image_path = temp_path

        faces = face_engine.get_faces(image_path)
        is_pg = db.bind.dialect.name == "postgresql"

        for face in faces:
            embedding_list = face.embedding.tolist()
            bbox_list = face.bbox.tolist()

            db_face = models.FaceEmbedding(
                photo_id=photo_id,
                event_id=photo.event_id,
                embedding=embedding_list,
                face_box=bbox_list
            )
            db.add(db_face)
            db.flush()  # assign db_face.id

            # Populate the pgvector column (PostgreSQL only).
            if is_pg:
                from sqlalchemy import text
                vec = "[" + ",".join(f"{float(x):.8f}" for x in embedding_list) + "]"
                db.execute(
                    text("UPDATE face_embeddings SET embedding_vec = CAST(:v AS vector) WHERE id = :id"),
                    {"v": vec, "id": db_face.id},
                )

        photo.processing_status = models.ProcessingStatus.COMPLETED
        db.commit()
        photos_processed_total.labels("completed").inc()
        faces_detected_total.inc(len(faces))
    except Exception:
        logger.exception("Face processing failed for photo %s", photo_id)
        photos_processed_total.labels("failed").inc()
        if photo is not None:
            try:
                photo.processing_status = models.ProcessingStatus.FAILED
                db.commit()
            except Exception:
                db.rollback()
        if raise_on_error:
            raise
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        db.close()

def get_similarity(feat1, feat2):
    # Cosine similarity
    feat1 = np.array(feat1)
    feat2 = np.array(feat2)
    sim = np.dot(feat1, feat2) / (np.linalg.norm(feat1) * np.linalg.norm(feat2))
    return sim
