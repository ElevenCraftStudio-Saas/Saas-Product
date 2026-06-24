from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import models
from ..core.firebase import verify_token
from ..services import api_tokens
from ..config import settings

# Both optional: a request authenticates via EITHER a Firebase bearer token
# (humans, web app) OR an X-API-Key (desktop ingest agent).
bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


def _auth_exception(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _find_or_create_user(decoded: dict, db: Session) -> models.User:
    uid = decoded.get("uid")
    if not uid:
        raise _auth_exception()

    email = decoded.get("email")
    allowlisted = bool(email) and email.lower() in settings.admin_emails

    user = db.query(models.User).filter(models.User.firebase_uid == uid).first()
    if user:
        # Allowlisted accounts are upgraded to admin on login (never demoted).
        if allowlisted and user.role != "admin":
            user.role = "admin"
            db.commit()
            db.refresh(user)
        return user

    phone = decoded.get("phone_number")
    # Open signup: every new Firebase login is provisioned immediately (no
    # approval workflow). Email in ADMIN_EMAILS => admin, else => studio user.
    user = models.User(
        firebase_uid=uid,
        email=email,
        phone=phone,
        name=decoded.get("name") or email or phone or "User",
        role="admin" if allowlisted else "user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Authenticated user via Firebase bearer OR X-API-Key (desktop agent).

    Auto-provisions a User row on first Firebase call.
    """
    # 1. API key (desktop ingest agent) takes precedence if supplied.
    if api_key:
        user = api_tokens.resolve_token(db, api_key)
        if not user:
            raise _auth_exception("Invalid or revoked API key")
        return user

    # 2. Firebase ID token (web app / humans).
    if cred and cred.credentials:
        try:
            decoded = verify_token(cred.credentials)
        except Exception as e:
            import logging
            logging.getLogger("uvicorn.error").warning(
                "Token verify failed: %s: %s", type(e).__name__, e
            )
            raise _auth_exception("Invalid or expired token")
        return _find_or_create_user(decoded, db)

    raise _auth_exception("Authentication required")


def require_user(current_user: models.User = Depends(get_current_user)) -> models.User:
    """Require a studio user account (event/photo endpoints)."""
    if current_user.role != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Studio access required")
    return current_user


def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    """Require the admin account (all management endpoints)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


# Back-compat alias (all callers migrated to require_user/require_admin in Task 4).
get_current_studio = require_user
