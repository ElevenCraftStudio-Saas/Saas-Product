"""Auth router. Identity is handled by Firebase on the client.

The backend only verifies Firebase ID tokens (see routers/deps.py) and
exposes the current user. No passwords are stored.
"""
from fastapi import APIRouter, Depends
from ..models import models
from ..schemas import schemas
from .deps import get_current_user

router = APIRouter()


@router.get("/me", response_model=schemas.UserResponse)
def read_me(current_user: models.User = Depends(get_current_user)):
    """Return the current user, auto-provisioning the row on first login."""
    return current_user
