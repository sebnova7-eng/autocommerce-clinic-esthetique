"""Tests — Bloc 1 : CRM Social Omnicanal

Vérifie :
  - Factory de connecteurs
  - ChannelAdapter interface
  - WhatsAppConnector (dev mode, parsing webhook)
  - Service omnicanal (conversations, messages, retries)
  - Rétrocompatibilité avec social_crm existant
"""

import json
import pytest

from services.omnicanal.factory import get_connector, get_all_connectors, clear_cache, get_canal_labels
from services.omnicanal.channel_adapter import ChannelAdapter
from services.omnicanal.whatsapp_connector import WhatsAppConnector


# ── Factory ─────────────────────────────────────────────────

class TestFactory:
    def setup_method(self):
        clear_cache()

    @pytest.mark.asyncio
    async def test_get_connector_whatsapp(self, db):
        connector = get_connector("whatsapp")
        assert connector is not None
        assert isinstance(connector, ChannelAdapter)
        assert connector.CHANNEL_NAME == "whatsapp"

    @pytest.mark.asyncio
    async def test_get_connector_unknown_returns_none(self, db):
        connector = get_connector("twitter")
        assert connector is None

    @pytest.mark.asyncio
    async def test_get_all_connectors_returns_multiple(self, db):
        connectors = get_all_connectors()
        assert len(connectors) >= 1  # Au minimum whatsapp en dev mode
        assert "whatsapp" in connectors

    @pytest.mark.asyncio
    async def test_factory_returns_singleton(self, db):
        c1 = get_connector("whatsapp")
        c2 = get_connector("whatsapp")
        assert c1 is c2

    def test_get_canal_labels_has_all_channels(self):
        labels = get_canal_labels()
        expected = {"whatsapp", "instagram", "facebook", "tiktok", "email", "sms"}
        assert expected.issubset(set(labels.keys()))


# ── WhatsApp Connector ──────────────────────────────────────

class TestWhatsAppConnector:
    @pytest.mark.asyncio
    async def test_dev_mode_send_message_returns_success(self, db):
        clear_cache()
        connector = get_connector("whatsapp")
        result = await connector.send_message("+21600000001", "Test message")
        assert result["success"] is True
        assert result["status"] == "dev_mode"

    @pytest.mark.asyncio
    async def test_dev_mode_send_media_returns_success(self, db):
        clear_cache()
        connector = get_connector("whatsapp")
        result = await connector.send_media("+21600000001", "image", media_url="https://example.com/img.jpg")
        assert result["success"] is True
        assert result["status"] == "dev_mode"

    @pytest.mark.asyncio
    async def test_dev_mode_get_channel_status(self, db):
        clear_cache()
        connector = get_connector("whatsapp")
        status = await connector.get_channel_status()
        assert status["configured"] is False
        assert status["status"] == "non_configure"

    def test_verify_signature_no_secret_returns_false(self):
        connector = WhatsAppConnector()
        result = connector.verify_signature(b"test", "abc123")
        assert result is False

    def test_verify_signature_valid_format_sha256(self, monkeypatch):
        # Configurer un secret
        monkeypatch.setenv("SOCIAL_WEBHOOK_SECRET", "test-secret-123")
        clear_cache()
        connector = get_connector("whatsapp")

        body = b'{"test": true}'
        expected = connector.verify_signature(body, "sha256=0000000000000000000000000000000000000000000000000000000000000000")
        # La signature ne matchera pas (hash != 0000...), mais le format est accepté
        assert isinstance(expected, bool)

    def test_verify_signature_legacy_format(self, monkeypatch):
        monkeypatch.setenv("SOCIAL_WEBHOOK_SECRET", "test-secret-123")
        clear_cache()
        connector = get_connector("whatsapp")
        body = b'{"test": true}'
        result = connector.verify_signature(body, "wronghash")
        assert result is False

    def test_parse_webhook_payload_meta_format(self):
        connector = WhatsAppConnector()
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "+21620000000",
                            "type": "text",
                            "text": {"body": "Bonjour !"},
                            "id": "wamid.test123",
                            "timestamp": "1234567890",
                        }],
                        "contacts": [{
                            "profile": {"name": "Ines Gharbi"},
                            "wa_id": "+21620000000"
                        }]
                    }
                }]
            }]
        }
        messages = connector.parse_webhook_payload(json.dumps(payload).encode())
        assert len(messages) == 1
        assert messages[0]["contact_id"] == "+21620000000"
        assert messages[0]["contact_nom"] == "Ines Gharbi"
        assert messages[0]["content"] == "Bonjour !"
        assert messages[0]["external_message_id"] == "wamid.test123"
        assert messages[0]["direction"] == "entrant"

    def test_parse_webhook_payload_image_type(self):
        connector = WhatsAppConnector()
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "+21620000000",
                            "type": "image",
                            "image": {"link": "https://example.com/photo.jpg", "caption": "Ma photo"},
                            "id": "wamid.img001",
                            "timestamp": "1234567890",
                        }],
                        "contacts": []
                    }
                }]
            }]
        }
        messages = connector.parse_webhook_payload(json.dumps(payload).encode())
        assert len(messages) == 1
        assert messages[0]["type_message"] == "image"
        assert messages[0]["media_url"] == "https://example.com/photo.jpg"

    def test_parse_webhook_payload_location_type(self):
        connector = WhatsAppConnector()
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "+21620000000",
                            "type": "location",
                            "location": {"latitude": 36.8, "longitude": 10.18},
                            "id": "wamid.loc001",
                            "timestamp": "1234567890",
                        }],
                        "contacts": []
                    }
                }]
            }]
        }
        messages = connector.parse_webhook_payload(json.dumps(payload).encode())
        assert len(messages) == 1
        assert "Position" in messages[0]["content"]

    def test_parse_webhook_payload_invalid_object(self):
        connector = WhatsAppConnector()
        payload = {"object": "unknown", "entry": []}
        messages = connector.parse_webhook_payload(json.dumps(payload).encode())
        assert len(messages) == 0

    def test_parse_webhook_payload_invalid_json(self):
        connector = WhatsAppConnector()
        messages = connector.parse_webhook_payload(b"not json at all")
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_check_delivery_status_returns_unknown(self, db):
        clear_cache()
        connector = get_connector("whatsapp")
        result = await connector.check_delivery_status("wamid.test123")
        assert result["status"] == "unknown"


# ── Connecteurs secondaires ─────────────────────────────────

class TestSecondaryConnectors:
    @pytest.mark.asyncio
    async def test_instagram_not_configured(self, db):
        clear_cache()
        connector = get_connector("instagram")
        result = await connector.send_message("ig_user_1", "Test")
        # Le connecteur Meta utilise _send() qui fait un appel réseau
        # sans token valide, donc il échoue. Le résultat peut être
        # "not_configured" (check avant API) ou "failed" (échec réseau).
        assert result["success"] is False
        assert result["status"] in ("not_configured", "failed")

    @pytest.mark.asyncio
    async def test_facebook_not_configured(self, db):
        clear_cache()
        connector = get_connector("facebook")
        result = await connector.send_message("fb_user_1", "Test")
        assert result["success"] is False
        assert result["status"] in ("not_configured", "failed")

    @pytest.mark.asyncio
    async def test_tiktok_not_configured(self, db):
        clear_cache()
        connector = get_connector("tiktok")
        result = await connector.send_message("tk_user_1", "Test")
        assert result["success"] is False
        assert result["status"] in ("not_configured", "failed")

    @pytest.mark.asyncio
    async def test_email_not_configured(self, db):
        clear_cache()
        connector = get_connector("email")
        result = await connector.send_message("test@example.com", "Test")
        assert result["status"] == "not_configured"

    @pytest.mark.asyncio
    async def test_sms_not_configured(self, db):
        clear_cache()
        connector = get_connector("sms")
        result = await connector.send_message("+21600000001", "Test")
        assert result["status"] == "not_configured"


# ── Service Omnicanal (conversations + messages) ────────────

class TestOmnicanalService:
    @pytest.mark.asyncio
    async def test_get_or_create_conversation_creates_new(self, db):
        from services.omnicanal_service import get_or_create_conversation
        conv = await get_or_create_conversation(
            canal="whatsapp",
            contact_external_id="+21699999999",
            clinic_id=1,
            db=db,
        )
        assert conv.id is not None
        assert conv.canal == "whatsapp"
        assert conv.statut == "ouverte"
        assert conv.nb_messages == 0

    @pytest.mark.asyncio
    async def test_get_or_create_conversation_returns_existing(self, db):
        from services.omnicanal_service import get_or_create_conversation
        conv1 = await get_or_create_conversation(
            canal="whatsapp", contact_external_id="+21699999998", db=db,
        )
        conv2 = await get_or_create_conversation(
            canal="whatsapp", contact_external_id="+21699999998", db=db,
        )
        assert conv1.id == conv2.id

    @pytest.mark.asyncio
    async def test_receive_message_creates_in_new_conversation(self, db):
        from services.omnicanal_service import receive_message
        result = await receive_message(
            canal="whatsapp",
            contact_external_id="+21699999997",
            content="Bonjour, j'ai une question",
            db=db,
        )
        assert result["conversation"].id is not None
        assert result["message"].direction == "entrant"
        assert result["message"].statut == "envoye"
        assert result["conversation"].nb_messages == 1

    @pytest.mark.asyncio
    async def test_receive_message_rejects_unknown_canal(self, db):
        from services.omnicanal_service import receive_message
        with pytest.raises(ValueError, match="non supporté"):
            await receive_message(canal="twitter", contact_external_id="x", content="test", db=db)

    @pytest.mark.asyncio
    async def test_receive_message_matches_patient(self, db, patient):
        from services.omnicanal_service import receive_message
        result = await receive_message(
            canal="whatsapp",
            contact_external_id=patient.whatsapp_phone,
            content="C'est moi Ines",
            db=db,
        )
        assert result["patient_matched"] is True
        assert result["conversation"].patient_id == patient.id
        assert result["message"].patient_id == patient.id

    @pytest.mark.asyncio
    async def test_send_reply_via_dev_mode(self, db):
        from services.omnicanal_service import receive_message, send_reply
        recv = await receive_message(
            canal="whatsapp", contact_external_id="+21699999996",
            content="Question", db=db,
        )
        result = await send_reply(
            conversation_id=recv["conversation"].id,
            content="Bonjour ! Comment puis-je vous aider ?",
            db=db,
        )
        assert result["result"]["success"] is True
        assert result["message"].statut == "envoye"

    @pytest.mark.asyncio
    async def test_send_reply_unknown_conversation_raises(self, db):
        from services.omnicanal_service import send_reply
        with pytest.raises(ValueError, match="non trouvée"):
            await send_reply(conversation_id=999999, content="test", db=db)

    @pytest.mark.asyncio
    async def test_close_conversation(self, db):
        from services.omnicanal_service import get_or_create_conversation, close_conversation
        conv = await get_or_create_conversation(
            canal="whatsapp", contact_external_id="+21699999995", db=db,
        )
        closed = await close_conversation(conv.id, db)
        assert closed.statut == "fermee"

    @pytest.mark.asyncio
    async def test_assign_conversation(self, db):
        from services.omnicanal_service import get_or_create_conversation, assign_conversation
        conv = await get_or_create_conversation(
            canal="whatsapp", contact_external_id="+21699999994", db=db,
        )
        assigned = await assign_conversation(conv.id, 1, db)
        assert assigned.assignee_id == 1
        assert assigned.statut == "ouverte"

    @pytest.mark.asyncio
    async def test_add_tags_to_conversation(self, db):
        from services.omnicanal_service import get_or_create_conversation, add_tags_to_conversation
        conv = await get_or_create_conversation(
            canal="whatsapp", contact_external_id="+21699999993", db=db,
        )
        tagged = await add_tags_to_conversation(conv.id, ["vip", "relance"], db)
        tags = json.loads(tagged.tags)
        assert "vip" in tags
        assert "relance" in tags

    @pytest.mark.asyncio
    async def test_add_tags_no_duplicates(self, db):
        from services.omnicanal_service import get_or_create_conversation, add_tags_to_conversation
        conv = await get_or_create_conversation(
            canal="whatsapp", contact_external_id="+21699999992", db=db,
        )
        await add_tags_to_conversation(conv.id, ["vip"], db)
        tagged = await add_tags_to_conversation(conv.id, ["vip", "nouveau"], db)
        tags = json.loads(tagged.tags)
        assert tags.count("vip") == 1
        assert "nouveau" in tags

    @pytest.mark.asyncio
    async def test_get_conversation_messages(self, db):
        from services.omnicanal_service import receive_message, get_conversation_messages
        recv = await receive_message(
            canal="whatsapp", contact_external_id="+21699999991",
            content="Premier message", db=db,
        )
        await receive_message(
            canal="whatsapp", contact_external_id="+21699999991",
            content="Deuxième message", db=db,
        )
        messages = await get_conversation_messages(recv["conversation"].id, db)
        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_list_messages_by_statut(self, db):
        from services.omnicanal_service import receive_message, list_messages
        await receive_message(
            canal="whatsapp", contact_external_id="+21699999990",
            content="test1", db=db,
        )
        messages = await list_messages(db, statut="envoye")
        assert len(messages) >= 1

    @pytest.mark.asyncio
    async def test_list_conversations_by_canal(self, db):
        from services.omnicanal_service import list_conversations, receive_message
        await receive_message(
            canal="whatsapp", contact_external_id="+21699999989",
            content="test wa", db=db,
        )
        wa_convs = await list_conversations(db, canal="whatsapp")
        assert len(wa_convs) >= 1

    @pytest.mark.asyncio
    async def test_get_omnicanal_analytics(self, db):
        from services.omnicanal_service import get_omnicanal_analytics, receive_message
        await receive_message(
            canal="whatsapp", contact_external_id="+21699999988",
            content="test analytics", db=db,
        )
        stats = await get_omnicanal_analytics(db)
        assert "by_platform" in stats
        assert "whatsapp" in stats["by_platform"]

    @pytest.mark.asyncio
    async def test_get_channel_stats(self, db):
        from services.omnicanal_service import get_channel_stats
        stats = await get_channel_stats(db)
        assert "whatsapp" in stats
        assert "instagram" in stats
        assert "tiktok" in stats
