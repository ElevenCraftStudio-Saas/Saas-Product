"""Sentry init (web + worker). No-op when SENTRY_DSN is unset."""
import sentry_sdk

from ..config import settings

_SENSITIVE = {"authorization", "x-api-key", "cookie"}


def _scrub(event, hint):
    req = event.get("request") or {}
    headers = req.get("headers")
    if isinstance(headers, dict):
        for h in list(headers):
            if h.lower() in _SENSITIVE:
                headers[h] = "[redacted]"
    return event


def init_sentry(celery: bool = False) -> None:
    if not settings.SENTRY_DSN:
        return
    integrations = []
    try:
        if celery:
            from sentry_sdk.integrations.celery import CeleryIntegration
            integrations = [CeleryIntegration()]
        else:
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            integrations = [FastApiIntegration()]
    except Exception:
        integrations = []
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENV,
        traces_sample_rate=0.1,
        send_default_pii=False,
        integrations=integrations,
        before_send=_scrub,
    )
