from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import os
import uuid
import shutil
import numpy as np
from ..database import get_db
from ..models import models
from ..schemas import schemas
from ..services.face_engine import face_engine
from ..services.face_processing import get_similarity
from .deps import get_current_user

from ..services.s3_service import s3_service

router = APIRouter()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "../uploads")
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", 0.6))

@router.post("/selfie/{event_slug}")
async def match_selfie(
    event_slug: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    event = db.query(models.Event).filter(models.Event.event_slug == event_slug).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Save temporary selfie locally for face detection
    temp_dir = os.path.join(UPLOAD_DIR, "temp_selfies")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{file.filename}")
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # Get face from selfie
        faces = face_engine.get_faces(temp_path)
        if not faces:
            raise HTTPException(status_code=400, detail="No face detected in selfie")
        
        guest_embedding = faces[0].embedding
        
        photo_ids = [p.id for p in db.query(models.Photo).filter(models.Photo.event_id == event.id).all()]
        all_embeddings = db.query(models.FaceEmbedding).filter(models.FaceEmbedding.photo_id.in_(photo_ids)).all()
        
        matched_photo_ids = set()
        for db_face in all_embeddings:
            sim = get_similarity(guest_embedding, db_face.embedding)
            if sim >= MATCH_THRESHOLD:
                matched_photo_ids.add(db_face.photo_id)
        
        matched_photos = db.query(models.Photo).filter(models.Photo.id.in_(list(matched_photo_ids))).all()
        
        # Generate URLs for matched photos
        for photo in matched_photos:
            if photo.storage_provider == "s3":
                photo.url = s3_service.generate_presigned_url(photo.storage_key)
            else:
                photo.url = f"/uploads/{photo.filepath.replace('../uploads/', '')}"
        
        return matched_photos
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
