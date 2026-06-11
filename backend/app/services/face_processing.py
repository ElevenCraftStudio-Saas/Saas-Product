from ..database import SessionLocal
from ..models import models
from .face_engine import face_engine
from .s3_service import s3_service
import numpy as np
import os
import uuid

def process_photo_faces(photo_id: int):
    db = SessionLocal()
    temp_path = None
    try:
        photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
        if not photo:
            return

        photo.processing_status = models.ProcessingStatus.PROCESSING
        db.commit()

        # Handle S3 vs Local
        image_path = photo.filepath
        if photo.storage_provider == "s3":
            # Download to temp file for processing
            temp_dir = os.path.join(os.getenv("UPLOAD_DIR", "../uploads"), "temp_processing")
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}.jpg")
            success = s3_service.download_to_temp(photo.storage_key, temp_path)
            if not success:
                raise Exception("Failed to download from S3")
            image_path = temp_path

        faces = face_engine.get_faces(image_path)
        
        for face in faces:
            embedding_list = face.embedding.tolist()
            bbox_list = face.bbox.tolist()
            
            db_face = models.FaceEmbedding(
                photo_id=photo_id,
                embedding=embedding_list,
                face_box=bbox_list
            )
            db.add(db_face)
        
        photo.processing_status = models.ProcessingStatus.COMPLETED
        db.commit()
    except Exception as e:
        print(f"Error processing photo {photo_id}: {e}")
        if photo:
            photo.processing_status = models.ProcessingStatus.FAILED
            db.commit()
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
