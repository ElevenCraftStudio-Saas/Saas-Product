"""Firebase ID token verification and Admin SDK initialization.

Supports three credential discovery methods (checked in order):
  A. GOOGLE_APPLICATION_CREDENTIALS env var pointing to a JSON file.
  B. FIREBASE_SERVICE_ACCOUNT_B64 env var (base64-encoded JSON).
  C. FIREBASE_CREDENTIALS env var (legacy) → default "firebase-service-account.json".

Token verification uses Google's public x509 certs and needs NO credentials,
so the app works in dev even without a service account. Firestore operations
gracefully degrade when no credentials are available.
"""
import base64
import logging
import os
import json
import threading
import time
import urllib.request
from datetime import timedelta
from pathlib import Path

import jwt
from cryptography.x509 import load_pem_x509_certificate

from ..config import settings

log = logging.getLogger("wedfind.firebase")
audit_log = logging.getLogger("wedfind.audit")

_LEEWAY = timedelta(seconds=30)

PROJECT_ID = settings.FIREBASE_PROJECT_ID
_CERT_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "securetoken@system.gserviceaccount.com"
)
_ISSUER = f"https://securetoken.google.com/{PROJECT_ID}"

# ---------------------------------------------------------------------------
# Firebase Admin SDK initialization — explicit, idempotent, thread-safe.
# Discovery methods (checked in order): GOOGLE_APPLICATION_CREDENTIALS,
# FIREBASE_SERVICE_ACCOUNT_B64, FIREBASE_CREDENTIALS / default file.
# ---------------------------------------------------------------------------
_init_lock = threading.Lock()


def _resolve_credential_path() -> str | None:
    """Find a service-account JSON file and return its path, or None."""

    # --- Method A: GOOGLE_APPLICATION_CREDENTIALS ---
    gac = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if gac:
        gac_path = Path(gac)
        if gac_path.is_file():
            audit_log.info("firebase: using GOOGLE_APPLICATION_CREDENTIALS path=%s", gac)
            return str(gac_path.resolve())
        audit_log.warning("firebase: GOOGLE_APPLICATION_CREDENTIALS set but file not found at %s", gac)

    # --- Method B: base64-encoded JSON in env var ---
    b64 = settings.FIREBASE_SERVICE_ACCOUNT_B64
    if b64:
        target = Path("/app/firebase-service-account.json")
        try:
            decoded = base64.b64decode(b64).decode("utf-8")
            # Validate it's parseable JSON before writing.
            json.loads(decoded)
            target.write_text(decoded, encoding="utf-8")
            target.chmod(0o600)
            audit_log.info("firebase: decoded FIREBASE_SERVICE_ACCOUNT_B64 -> %s", target)
            return str(target)
        except Exception as exc:
            audit_log.error("firebase: FIREBASE_SERVICE_ACCOUNT_B64 decode FAILED: %s: %s", type(exc).__name__, exc)

    # --- Method C: legacy FIREBASE_CREDENTIALS env / default filename ---
    legacy = os.getenv("FIREBASE_CREDENTIALS", "firebase-service-account.json")
    legacy_path = Path(legacy)
    if legacy_path.is_file():
        audit_log.info("firebase: using FIREBASE_CREDENTIALS path=%s", legacy)
        return str(legacy_path.resolve())

    audit_log.warning("firebase: no service account file found via any method — Admin SDK init skipped")
    return None


def init_firebase() -> bool:
    """Initialize the Firebase Admin SDK. Idempotent + thread-safe.

    Safe to call any number of times and from any thread. Returns True if the
    Admin SDK is initialized (now or already), False if no credentials were
    found — token verification still works via Google's public certs either way.
    Never raises on missing credentials; logs a full traceback on real failure.
    """
    import firebase_admin

    # Fast path: already initialized.
    if firebase_admin._apps:
        log.debug("Firebase Admin already initialized — skipping (apps=%s)",
                  list(firebase_admin._apps))
        return True

    with _init_lock:
        if firebase_admin._apps:  # re-check under lock (another thread won the race)
            return True

        cred_path = _resolve_credential_path()
        if not cred_path:
            log.warning(
                "Firebase: no service-account credentials found (project=%s) — "
                "Admin SDK not initialized; token verification still works via public certs",
                PROJECT_ID,
            )
            return False

        try:
            from firebase_admin import credentials
            log.info("Firebase: initializing Admin SDK project=%s credential=%s", PROJECT_ID, cred_path)
            firebase_admin.initialize_app(
                credentials.Certificate(cred_path),
                {"projectId": PROJECT_ID},
            )
            log.info("Firebase Admin initialized — project=%s", PROJECT_ID)
            return True
        except Exception:
            log.exception(
                "Firebase Admin SDK initialization failed (project=%s credential=%s)",
                PROJECT_ID, cred_path,
            )
            return False


def get_firestore_client():
    """Return a Firestore client, initializing Firebase on demand.

    The single entry point for Firestore — nothing else should call
    firestore.client() directly. Raises RuntimeError if Firebase cannot be
    initialized (no credentials); callers that must degrade gracefully
    (firestore_service) catch it and return None.
    """
    import firebase_admin

    if not firebase_admin._apps:
        init_firebase()
    if not firebase_admin._apps:
        raise RuntimeError(
            "Firebase Admin SDK is not initialized (no service-account credentials)"
        )
    from firebase_admin import firestore
    return firestore.client()


# Cache of {kid: public_key} plus expiry epoch.
_certs_cache: dict[str, object] = {}
_certs_expiry: float = 0.0


def _load_public_keys() -> dict[str, object]:
    global _certs_cache, _certs_expiry
    now = time.time()
    if _certs_cache and now < _certs_expiry:
        return _certs_cache

    req = urllib.request.Request(_CERT_URL, headers={"User-Agent": "wedfind"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read()
        cache_control = resp.headers.get("Cache-Control", "")

    certs = json.loads(raw)
    keys: dict[str, object] = {}
    for kid, pem in certs.items():
        cert = load_pem_x509_certificate(pem.encode("utf-8"))
        keys[kid] = cert.public_key()

    # Respect max-age from Cache-Control, default 1h.
    max_age = 3600
    for part in cache_control.split(","):
        part = part.strip()
        if part.startswith("max-age="):
            try:
                max_age = int(part.split("=", 1)[1])
            except ValueError:
                pass

    _certs_cache = keys
    _certs_expiry = now + max_age
    return keys


def verify_token(id_token: str) -> dict:
    """Verify a Firebase ID token. Raises on invalid/expired token.

    Returns the decoded claims with a normalized 'uid' key (== 'sub').
    """
    audit_log.info("firebase: verify_token called, token_prefix=%s...", id_token[:20] if len(id_token) > 20 else id_token)
    header = jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    audit_log.info("firebase: token header kid=%s alg=%s", kid, header.get("alg"))
    keys = _load_public_keys()
    public_key = keys.get(kid)
    if public_key is None:
        audit_log.info("firebase: key not found in cache, refreshing certs")
        global _certs_expiry
        _certs_expiry = 0.0
        public_key = _load_public_keys().get(kid)
    if public_key is None:
        audit_log.error("firebase: no matching public key for kid=%s", kid)
        raise ValueError("No matching public key for token")

    claims = jwt.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=PROJECT_ID,
        issuer=_ISSUER,
        leeway=_LEEWAY,
    )
    if not claims.get("sub"):
        raise ValueError("Token missing subject")
    claims["uid"] = claims["sub"]
    audit_log.info("firebase: token verified, uid=%s email=%s", claims["uid"], claims.get("email", "N/A"))
    return claims
