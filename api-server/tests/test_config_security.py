"""Tests — config.py (_validate_production_secrets)

Vérifie le garde-fou qui empêche de démarrer en production avec des
secrets par défaut ou absents.
"""
import pytest

from config import Settings, _validate_production_secrets, DEFAULT_SECRET_KEY


def _settings(**overrides):
    base = dict(
        env="production",
        clinic_id=None,
        public_clinic_id=1,
        secret_key="S" * 64,
        fernet_key="ZmVybmV0LWtleS1kZS10ZXN0LTMyLWJ5dGVzLW9r",
        photo_encryption_key="cGhvdG8ta2V5LWRlLXRlc3QtMzItYnl0ZXMtb2s=",
        database_url="postgresql+asyncpg://real_user:real_pass@db.clinic.tn:5432/clinic",
        redis_url="redis://:real_redis_key@redis.clinic.tn:6379/0",
        social_webhook_clinic_id=1,
        cors_origins="https://app.clinic.tn",
    )
    base.update(overrides)
    return Settings(**base)


def test_valid_production_config_passes():
    _validate_production_secrets(_settings())  # ne doit pas lever


def test_default_secret_key_rejected_in_production():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _validate_production_secrets(_settings(secret_key=DEFAULT_SECRET_KEY))


def test_short_secret_key_rejected_in_production():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _validate_production_secrets(_settings(secret_key="trop-court"))


def test_missing_fernet_key_rejected_in_production():
    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        _validate_production_secrets(_settings(fernet_key=""))


def test_missing_photo_encryption_key_rejected_in_production():
    with pytest.raises(RuntimeError, match="PHOTO_ENCRYPTION_KEY"):
        _validate_production_secrets(_settings(photo_encryption_key=""))


def test_photo_encryption_key_same_as_fernet_key_rejected():
    with pytest.raises(RuntimeError, match="PHOTO_ENCRYPTION_KEY"):
        _validate_production_secrets(_settings(
            photo_encryption_key="ZmVybmV0LWtleS1kZS10ZXN0LTMyLWJ5dGVzLW9r"
        ))


def test_default_database_credentials_rejected_in_production():
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        _validate_production_secrets(_settings(
            database_url="postgresql+asyncpg://clinic_admin:changeme@localhost:5432/autocommerce_clinic"
        ))


def test_development_env_skips_validation():
    """En dev/test, on ne bloque jamais — sinon on casse le développement local."""
    _validate_production_secrets(_settings(env="development", secret_key=DEFAULT_SECRET_KEY, fernet_key=""))


def test_all_errors_reported_together():
    with pytest.raises(RuntimeError) as exc:
        _validate_production_secrets(_settings(secret_key=DEFAULT_SECRET_KEY, fernet_key=""))
    assert "SECRET_KEY" in str(exc.value)
    assert "FERNET_KEY" in str(exc.value)


def test_placeholder_redis_credentials_rejected_in_production():
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        _validate_production_secrets(_settings(
            redis_url="redis://:password@example-redis:6379/0"
        ))


def test_placeholder_critical_key_rejected_in_production():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _validate_production_secrets(_settings(
            secret_key="your-secret-key-please-change-1234567890"
        ))


def test_whatsapp_dev_mode_rejected_in_production():
    with pytest.raises(RuntimeError, match="WA_ALLOW_DEV_MODE"):
        _validate_production_secrets(_settings(wa_allow_dev_mode=True))
