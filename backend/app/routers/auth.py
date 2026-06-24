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
from .deps import get_current_user, require_admin

router = APIRouter()


class PromoteRequest(BaseModel):
    email: str
    role: str = "user"  # "user" or "pending"


@router.get("/me", response_model=schemas.UserResponse)
def read_me(current_user: models.User = Depends(get_current_user)):
    """Return the current user, auto-provisioning the row on first login."""
    return current_user


@router.post("/promote", response_model=schemas.UserResponse)
def promote_user(
    body: PromoteRequest,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    """Grant/revoke studio access. Admin-only."""
    if body.role not in ("user", "pending"):
        raise HTTPException(status_code=400, detail="role must be 'user' or 'pending'")
    target = db.query(models.User).filter(models.User.email == body.email).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found (must sign in once first)")
    if target.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot change the admin's role")
    target.role = body.role
    db.commit()
    db.refresh(target)
    return target


# ---------------------- API tokens (desktop ingest agent) ----------------------

@router.post("/tokens", response_model=schemas.ApiTokenCreated)
def create_api_token(
    body: schemas.ApiTokenCreate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    """Admin creates an agent API key assigned to a target studio user.

    The agent authenticates AS that user, so it can ingest into the user's
    events. Plaintext returned ONCE.
    """
    target = db.query(models.User).filter(models.User.id == body.user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target user not found")
    if target.role != "user":
        raise HTTPException(status_code=400, detail="Tokens may only be assigned to a 'user' account")
    row, plaintext = api_tokens.generate_token(db, target, body.name)
    return schemas.ApiTokenCreated(
        id=row.id, name=row.name, token_prefix=row.token_prefix,
        revoked=row.revoked, created_at=row.created_at, last_used_at=row.last_used_at,
        token=plaintext,
    )


@router.get("/tokens", response_model=List[schemas.ApiTokenInfo])
def list_api_tokens(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    """Admin lists all agent tokens across users."""
    return (
        db.query(models.ApiToken)
        .order_by(models.ApiToken.created_at.desc())
        .all()
    )


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_token(
    token_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    row = db.query(models.ApiToken).filter(models.ApiToken.id == token_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Token not found")
    row.revoked = True
    db.commit()
    return None
