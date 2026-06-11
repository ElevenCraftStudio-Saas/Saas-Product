from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import models
from ..core.firebase import verify_token

bearer_scheme = HTTPBearer(auto_error=True)


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

    user = db.query(models.User).filter(models.User.firebase_uid == uid).first()
    if user:
        return user

    email = decoded.get("email")
    phone = decoded.get("phone_number")
    # Phone-only sign-in (no email) => guest. Otherwise studio.
    role = "guest" if phone and not email else "studio"
    user = models.User(
        firebase_uid=uid,
        email=email,
        phone=phone,
        name=decoded.get("name") or email or phone or "User",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Any authenticated Firebase user. Auto-provisions a User row on first call."""
    try:
        decoded = verify_token(cred.credentials)
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").warning(
            "Token verify failed: %s: %s", type(e).__name__, e
        )
        raise _auth_exception("Invalid or expired token")
    return _find_or_create_user(decoded, db)


def get_current_studio(current_user: models.User = Depends(get_current_user)) -> models.User:
    """Require a studio/photographer account (dashboard endpoints)."""
    if current_user.role != "studio":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Studio access required")
    return current_user
