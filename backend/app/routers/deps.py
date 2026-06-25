import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import models
from ..core.firebase import verify_token
from ..services import api_tokens

_audit_log = logging.getLogger("wedfind.audit")

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
    _audit_log.info("AUDIT deps.py: _find_or_create_user called uid=%s", uid)
    if not uid:
        _audit_log.warning("AUDIT deps.py: no uid in decoded token")
        raise _auth_exception()

    email = decoded.get("email") or ""
    phone = decoded.get("phone_number")
    name = decoded.get("name") or email or phone or "User"
    _audit_log.info("AUDIT deps.py: decoded claims uid=%s email=%s name=%s", uid, email, name)

    # Read role from Firestore (source of truth).
    _audit_log.info("AUDIT deps.py: calling ensure_user_doc(uid=%s, email=%s)", uid, email)
    from ..services.firestore_service import ensure_user_doc
    role = ensure_user_doc(uid, email, name)
    _audit_log.info("AUDIT deps.py: ensure_user_doc returned role=%s", role)

    user = db.query(models.User).filter(models.User.firebase_uid == uid).first()
    if user:
        _audit_log.info("AUDIT deps.py: existing PostgreSQL user found uid=%s role=%s, Firestore role=%s", uid, user.role, role)
        # Sync role from Firestore into PostgreSQL if it changed.
        if user.role != role:
            _audit_log.info("AUDIT deps.py: syncing role %s -> %s for uid=%s", user.role, role, uid)
            user.role = role
            db.commit()
            db.refresh(user)
        return user

    _audit_log.info("AUDIT deps.py: creating NEW PostgreSQL user uid=%s email=%s role=%s", uid, email, role)
    user = models.User(
        firebase_uid=uid,
        email=email,
        phone=phone,
        name=name,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _audit_log.info("AUDIT deps.py: PostgreSQL user created uid=%s id=%s role=%s", uid, user.id, user.role)
    return user


def get_current_user(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Authenticated user via Firebase bearer OR X-API-Key (desktop agent).

    Auto-provisions a User row on first Firebase call.
    """
    _audit_log.info("AUDIT deps.py: get_current_user called, has_api_key=%s has_bearer=%s",
                    bool(api_key), bool(cred and cred.credentials))

    # 1. API key (desktop ingest agent) takes precedence if supplied.
    if api_key:
        _audit_log.info("AUDIT deps.py: resolving API key")
        user = api_tokens.resolve_token(db, api_key)
        if not user:
            _audit_log.warning("AUDIT deps.py: API key invalid or revoked")
            raise _auth_exception("Invalid or revoked API key")
        _audit_log.info("AUDIT deps.py: API key resolved to user id=%s", user.id)
        return user

    # 2. Firebase ID token (web app / humans).
    if cred and cred.credentials:
        _audit_log.info("AUDIT deps.py: verifying Firebase token, prefix=%s...",
                        cred.credentials[:20] if len(cred.credentials) > 20 else cred.credentials)
        try:
            decoded = verify_token(cred.credentials)
        except Exception as e:
            _audit_log.error("AUDIT deps.py: token verification FAILED: %s: %s", type(e).__name__, e)
            raise _auth_exception("Invalid or expired token")
        _audit_log.info("AUDIT deps.py: token verified, calling _find_or_create_user")
        return _find_or_create_user(decoded, db)

    _audit_log.warning("AUDIT deps.py: no auth credentials provided")
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
