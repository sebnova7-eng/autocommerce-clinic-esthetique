"""Tests — services/whatsapp_service.py

En l'absence de wa_business_token / wa_phone_id (cas de nos tests),
le service tourne en "mode dev" et ne fait aucun appel réseau — on
verrouille ce comportement pour être sûr qu'aucun test ne déclenche
un vrai appel à l'API Meta par accident.
"""
import pytest

from services.whatsapp_service import send_whatsapp_message, send_whatsapp_template
from config import get_settings


@pytest.mark.asyncio
async def test_send_message_dev_mode_when_no_token_configured():
    settings = get_settings()
    assert not settings.wa_business_token  # confirme qu'on est bien en mode dev
    result = await send_whatsapp_message("+21620000000", "Bonjour")
    assert result["status"] == "dev_mode"


@pytest.mark.asyncio
async def test_send_template_dev_mode_when_no_token_configured():
    result = await send_whatsapp_template("+21620000000", "rdv_confirmation")
    assert result["status"] == "dev_mode"
    assert result["template"] == "rdv_confirmation"
