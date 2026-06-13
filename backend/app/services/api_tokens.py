"""API token generation + verification for the desktop ingest agent.

Tokens are shown to the user exactly once; only a sha256 hash is stored.
Format: wfa_<43 url-safe base64 chars>.
"""
import hashlib
import secrets
from typing import Optional

from sqlalchemy.orm import Session

from ..models import models

TOKEN_PREFIX = "wfa_"
PREFIX_DISPLAY_LEN = 12  # chars stored for display/lookup (incl. "wfa_")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_token(db: Session, user: models.User, name: str) -> tuple[models.ApiToken, str]:
    """Create a token row, return (row, plaintext). Plaintext is NOT stored."""
    plaintext = TOKEN_PREFIX + secrets.token_urlsafe(32)
    row = models.ApiToken(
        user_id=user.id,
        name=name or "agent",
        token_prefix=plaintext[:PREFIX_DISPLAY_LEN],
        token_hash=_hash(plaintext),
        revoked=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, plaintext


def resolve_token(db: Session, plaintext: str) -> Optional[models.User]:
    """Return the owning user for a valid, non-revoked token, else None."""
    if not plaintext or not plaintext.startswith(TOKEN_PREFIX):
        return None
    row = (
        db.query(models.ApiToken)
        .filter(models.ApiToken.token_hash == _hash(plaintext), models.ApiToken.revoked.is_(False))
        .first()
    )
    if not row:
        return None
    from sqlalchemy.sql import func
    row.last_used_at = func.now()
    db.commit()
    return db.query(models.User).filter(models.User.id == row.user_id).first()
