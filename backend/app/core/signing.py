"""HMAC-signed guest download tokens.

A token authorizes downloading ONE photo from ONE event, and expires.
Tokens are minted only for photos a guest's selfie actually matched —
closing the sequential-photo-id gallery-scrape hole (a bare
GET /photos/{id}/download would otherwise let anyone with the event slug
enumerate the entire gallery).

Token format: "<exp_unix>.<hex hmac-sha256 of 'event_id.photo_id.exp'>".
"""
import hashlib
import hmac
import logging
import secrets
import time

from ..config import settings

logger = logging.getLogger("wedfind.signing")

DEFAULT_TTL = 6 * 3600  # guests keep the gallery tab open for a while

if settings.SECRET_KEY:
    _SECRET = settings.SECRET_KEY.encode()
else:
    # Ephemeral key: tokens stop working across restarts/replicas. Fine for
    # dev/test; set SECRET_KEY in production.
    _SECRET = secrets.token_bytes(32)
    logger.warning(
        "SECRET_KEY not set — using ephemeral signing key; "
        "download tokens will not survive restarts or scale past one process"
    )


def _sig(msg: str) -> str:
    return hmac.new(_SECRET, msg.encode(), hashlib.sha256).hexdigest()


def sign_download(event_id: int, photo_id: int, ttl: int = DEFAULT_TTL) -> str:
    exp = int(time.time()) + ttl
    return f"{exp}.{_sig(f'{event_id}.{photo_id}.{exp}')}"


def verify_download(token: str, event_id: int, photo_id: int) -> bool:
    try:
        exp_str, sig = token.split(".", 1)
        exp = int(exp_str)
    except (AttributeError, ValueError):
        return False
    if exp < time.time():
        return False
    return hmac.compare_digest(sig, _sig(f"{event_id}.{photo_id}.{exp}"))
