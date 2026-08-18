"""Contrôles de sécurité et de compatibilité des deux modes de déploiement."""

from types import SimpleNamespace

import pytest

from config import Settings, _validate_production_secrets
from core.llm_budget import LLMBudgetExceeded, reserve_budget
from services.facture_scanner import _validate_upload


def _production_settings(**overrides) -> Settings:
    values = dict(
        env="production",
        deployment_mode="enterprise",
        clinic_id=None,
        public_routes_enabled=False,
        webhooks_enabled=False,
        teleconsultation_enabled=False,
        public_clinic_id=None,
        social_webhook_clinic_id=None,
        cors_origins="http://clinic.local",
        secret_key="S" * 64,
        fernet_key="fernet-key-" + "a" * 40,
        photo_encryption_key="photo-key-" + "b" * 40,
        database_url="postgresql+asyncpg://app:strong-db-pass@postgres:5432/clinic",
        redis_url="redis://:strong-redis-pass@redis:6379/0",
        llm_enabled=False,
        whatsapp_enabled=False,
        wa_allow_dev_mode=False,
        external_integrations_allowlist="ai,whatsapp",
    )
    values.update(overrides)
    return Settings(**values)


def test_enterprise_mode_accepts_no_global_clinic_id():
    _validate_production_secrets(_production_settings())


def test_internal_mode_requires_positive_clinic_id():
    with pytest.raises(RuntimeError, match="CLINIC_ID"):
        _validate_production_secrets(
            _production_settings(deployment_mode="internal_single_clinic", clinic_id=None)
        )


def test_internal_mode_rejects_public_routes_and_non_allowed_egress():
    with pytest.raises(RuntimeError, match="PUBLIC_ROUTES_ENABLED|intégrations externes"):
        _validate_production_secrets(
            _production_settings(
                deployment_mode="internal_single_clinic",
                clinic_id=1,
                public_routes_enabled=True,
                public_clinic_id=1,
                external_integrations_allowlist="ai,whatsapp,email",
            )
        )


def test_internal_mode_rejects_external_credentials():
    with pytest.raises(RuntimeError, match="credentials Email/SMS/S3/Sentry"):
        _validate_production_secrets(
            _production_settings(
                deployment_mode="internal_single_clinic",
                clinic_id=1,
                smtp_host="smtp.example.test",
            )
        )


def test_internal_allowlist_is_limited_to_ai_and_whatsapp():
    settings = Settings(
        deployment_mode="internal_single_clinic",
        clinic_id=1,
        external_integrations_allowlist="ai,whatsapp",
    )
    assert settings.allowed_external_integrations == {"ai", "whatsapp"}


def test_upload_validation_rejects_non_pdf_or_image():
    with pytest.raises(ValueError, match="Format"):
        _validate_upload(b"not-a-document", "text/plain")


def test_upload_validation_rejects_fake_pdf():
    with pytest.raises(ValueError, match="PDF valide"):
        _validate_upload(b"not-a-pdf", "application/pdf")


@pytest.mark.asyncio
async def test_llm_budget_is_fail_closed_after_limit():
    settings = SimpleNamespace(
        env="development",
        redis_url="",
        clinic_id=1,
        llm_max_requests_per_user_day=1,
        llm_daily_token_budget=10,
        llm_max_requests_per_clinic_day=100,
    )
    subject = "test-budget-dual-mode"
    await reserve_budget(settings, subject, 10)
    with pytest.raises(LLMBudgetExceeded):
        await reserve_budget(settings, subject, 1)
