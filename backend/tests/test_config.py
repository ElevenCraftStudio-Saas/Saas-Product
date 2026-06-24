"""Fail-fast configuration: missing required vars must abort; parsing works."""
import pytest
import pydantic

from app.config import Settings

_REQUIRED = ["DATABASE_URL", "REDIS_URL", "AWS_REGION", "S3_BUCKET", "AWS_BUCKET_NAME",
             "FIREBASE_PROJECT_ID", "SECRET_KEY", "ADMIN_EMAILS"]

_VALID = dict(DATABASE_URL="sqlite://", REDIS_URL="redis://x", AWS_REGION="r",
              S3_BUCKET="b", FIREBASE_PROJECT_ID="p", SECRET_KEY="s", ADMIN_EMAILS="")


def test_settings_fail_fast_on_missing(monkeypatch):
    for k in _REQUIRED:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(pydantic.ValidationError):
        Settings(_env_file=None)  # no .env, no env → required vars missing


def test_no_sqlite_default():
    # DATABASE_URL has no default — it is a required field.
    assert "DATABASE_URL" in Settings.model_fields
    assert Settings.model_fields["DATABASE_URL"].is_required()


def test_admin_emails_parsing():
    s = Settings(_env_file=None, **{**_VALID, "ADMIN_EMAILS": "A@x.com, b@Y.com ,"})
    assert s.admin_emails == {"a@x.com", "b@y.com"}


def test_s3_bucket_accepts_legacy_alias(monkeypatch):
    # Clear env so only the init kwarg supplies the bucket via its legacy alias.
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.delenv("AWS_BUCKET_NAME", raising=False)
    s = Settings(_env_file=None, **{k: v for k, v in _VALID.items() if k != "S3_BUCKET"},
                 AWS_BUCKET_NAME="legacy-bucket")
    assert s.S3_BUCKET == "legacy-bucket"


def test_is_production_flag():
    assert Settings(_env_file=None, ENV="production", **_VALID).is_production is True
    assert Settings(_env_file=None, ENV="test", **_VALID).is_production is False
