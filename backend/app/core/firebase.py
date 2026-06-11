"""Firebase ID token verification.

Verifies tokens directly against Google's public x509 certs — this needs NO
service-account credentials, so it works in dev out of the box. If a service
account JSON is present (FIREBASE_CREDENTIALS), the Admin SDK is also
initialized for future admin-only ops (custom claims, revocation, etc.).
"""
import os
import json
import time
import urllib.request

import jwt
from cryptography.x509 import load_pem_x509_certificate
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "saas-139a7")
_CRED_PATH = os.getenv("FIREBASE_CREDENTIALS", "firebase-service-account.json")
_CERT_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "securetoken@system.gserviceaccount.com"
)
_ISSUER = f"https://securetoken.google.com/{PROJECT_ID}"

# Optional Admin SDK init (only if a service account file exists).
try:
    if os.path.exists(_CRED_PATH):
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            firebase_admin.initialize_app(
                credentials.Certificate(_CRED_PATH), {"projectId": PROJECT_ID}
            )
except Exception:  # admin init is non-fatal; verification below is independent
    pass

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
    header = jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    keys = _load_public_keys()
    public_key = keys.get(kid)
    if public_key is None:
        # Cert rotation — refresh once and retry.
        global _certs_expiry
        _certs_expiry = 0.0
        public_key = _load_public_keys().get(kid)
    if public_key is None:
        raise ValueError("No matching public key for token")

    claims = jwt.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=PROJECT_ID,
        issuer=_ISSUER,
    )
    if not claims.get("sub"):
        raise ValueError("Token missing subject")
    claims["uid"] = claims["sub"]
    return claims
