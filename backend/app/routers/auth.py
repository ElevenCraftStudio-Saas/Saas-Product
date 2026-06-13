"""Auth router. Identity is handled by Firebase on the client.

The backend only verifies Firebase ID tokens (see routers/deps.py) and
exposes the current user. No passwords are stored.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import models
from ..schemas import schemas
from ..services import api_tokens
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


# ---------------------- API tokens (desktop ingest agent) ----------------------

@router.post("/tokens", response_model=schemas.ApiTokenCreated)
def create_api_token(
    body: schemas.ApiTokenCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_studio),
):
    """Create an API key for the desktop agent. Plaintext returned ONCE."""
    row, plaintext = api_tokens.generate_token(db, current_user, body.name)
    return schemas.ApiTokenCreated(
        id=row.id, name=row.name, token_prefix=row.token_prefix,
        revoked=row.revoked, created_at=row.created_at, last_used_at=row.last_used_at,
        token=plaintext,
    )


@router.get("/tokens", response_model=List[schemas.ApiTokenInfo])
def list_api_tokens(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_studio),
):
    return (
        db.query(models.ApiToken)
        .filter(models.ApiToken.user_id == current_user.id)
        .order_by(models.ApiToken.created_at.desc())
        .all()
    )


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_token(
    token_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_studio),
):
    row = (
        db.query(models.ApiToken)
        .filter(models.ApiToken.id == token_id, models.ApiToken.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Token not found")
    row.revoked = True
    db.commit()
    return None
