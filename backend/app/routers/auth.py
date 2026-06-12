"""Auth router. Identity is handled by Firebase on the client.

The backend only verifies Firebase ID tokens (see routers/deps.py) and
exposes the current user. No passwords are stored.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import models
from ..schemas import schemas
from .deps import get_current_user, get_current_studio

router = APIRouter()


class PromoteRequest(BaseModel):
    email: str
    role: str = "studio"  # "studio" or "guest"


@router.get("/me", response_model=schemas.UserResponse)
def read_me(current_user: models.User = Depends(get_current_user)):
    """Return the current user, auto-provisioning the row on first login."""
    return current_user


@router.post("/promote", response_model=schemas.UserResponse)
def promote_user(
    body: PromoteRequest,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_studio),
):
    """Grant/revoke studio access. Studio-only (the bootstrap studio acts as admin)."""
    if body.role not in ("studio", "guest"):
        raise HTTPException(status_code=400, detail="role must be 'studio' or 'guest'")
    target = db.query(models.User).filter(models.User.email == body.email).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found (must sign in once first)")
    target.role = body.role
    db.commit()
    db.refresh(target)
    return target
