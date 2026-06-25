"""Firestore-backed role management.

Firestore is the source of truth for user roles.
Each Firebase-authenticated user has a document at:

  users/{uid}

Schema:
  {
    "email": str,
    "display_name": str,
    "role": "admin" | "user",
    "created_at": timestamp,
    "updated_at": timestamp
  }

Requires the Firebase Admin SDK to be initialized with a service-account
key (FIREBASE_CREDENTIALS env var). When no service account is available
the module degrades gracefully: get_user_role returns None and all write
operations are no-ops. This lets the dev/test suite run without a real
Firestore project.
"""
import datetime
import logging
from typing import Optional

logger = logging.getLogger("wedfind.firestore")
audit_log = logging.getLogger("wedfind.audit")

_firestore_client = None


def _get_client():
    """Return the cached Firestore client, or None when Firebase is unavailable.

    Delegates initialization to the single implementation in core.firebase
    (get_firestore_client → init_firebase). Degrades gracefully so the
    dev/test suite runs without a real Firestore project.
    """
    global _firestore_client
    if _firestore_client is not None:
        return _firestore_client
    try:
        from ..core.firebase import get_firestore_client
        _firestore_client = get_firestore_client()
        logger.info("Firestore client ready")
    except Exception as e:
        logger.warning("Firestore unavailable (%s) — reads return None, writes are no-ops", type(e).__name__)
        return None
    return _firestore_client


def _doc_ref(uid: str):
    client = _get_client()
    if client is None:
        return None
    return client.collection("users").document(uid)


def get_user_role(uid: str) -> Optional[str]:
    """Read role from Firestore. Returns None if doc missing or unavailable."""
    audit_log.info("AUDIT firestore: get_user_role called uid=%s", uid)
    ref = _doc_ref(uid)
    if ref is None:
        audit_log.warning("AUDIT firestore: get_user_role ref is None (no Firestore client)")
        return None
    try:
        audit_log.info("AUDIT firestore: get_user_role calling ref.get() for uid=%s", uid)
        doc = ref.get()
        audit_log.info("AUDIT firestore: ref.get() returned exists=%s", doc.exists)
        if doc.exists:
            role = doc.get("role") or "user"
            audit_log.info("AUDIT firestore: get_user_role found uid=%s role=%s", uid, role)
            return role
        audit_log.info("AUDIT firestore: get_user_role doc NOT FOUND for uid=%s", uid)
        return None
    except Exception as e:
        audit_log.error("AUDIT firestore: get_user_role FAILED uid=%s error=%s: %s", uid, type(e).__name__, e)
        logger.exception("Firestore read failed for uid=%s", uid)
        return None


def set_user_role(uid: str, role: str, email: str = "", display_name: str = "") -> bool:
    """Set role on Firestore document. Creates doc if missing."""
    if role not in ("admin", "user"):
        raise ValueError(f"Invalid role: {role}")
    ref = _doc_ref(uid)
    if ref is None:
        logger.warning("Firestore unavailable — role not persisted (uid=%s role=%s)", uid, role)
        return False
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        ref.set({
            "email": email,
            "display_name": display_name,
            "role": role,
            "updated_at": now,
            "created_at": now,
        }, merge=True)
        logger.info("Firestore role set uid=%s role=%s", uid, role)
        return True
    except Exception:
        logger.exception("Firestore write failed for uid=%s", uid)
        return False


def ensure_user_doc(uid: str, email: str, display_name: str) -> str:
    """Ensure a Firestore doc exists for uid. Returns the role.

    If the doc exists, returns its role (default 'user').
    If missing, creates it with role='user' and returns 'user'.
    """
    audit_log.info("AUDIT firestore: ensure_user_doc called uid=%s email=%s", uid, email)
    existing = get_user_role(uid)
    if existing is not None:
        audit_log.info("AUDIT firestore: ensure_user_doc doc exists, role=%s", existing)
        return existing
    audit_log.info("AUDIT firestore: ensure_user_doc doc MISSING, will create")
    ref = _doc_ref(uid)
    if ref is None:
        audit_log.warning("AUDIT firestore: ensure_user_doc ref is None — FALLING BACK to role=user for uid=%s", uid)
        logger.warning("Firestore unavailable — defaulting to role=user for uid=%s", uid)
        return "user"
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        audit_log.info("AUDIT firestore: ensure_user_doc CREATING doc uid=%s email=%s", uid, email)
        ref.set({
            "email": email,
            "display_name": display_name,
            "role": "user",
            "created_at": now,
            "updated_at": now,
        })
        audit_log.info("AUDIT firestore: ensure_user_doc CREATE SUCCESS uid=%s", uid)
        logger.info("Firestore doc created uid=%s role=user", uid)
    except Exception as e:
        audit_log.error("AUDIT firestore: ensure_user_doc CREATE FAILED uid=%s error=%s: %s", uid, type(e).__name__, e)
        logger.exception("Firestore doc creation failed for uid=%s", uid)
    return "user"
