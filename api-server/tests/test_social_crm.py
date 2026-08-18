"""Tests — services/social_crm.py"""
import pytest

from services.social_crm import (
    receive_message, send_reply, list_messages,
    create_post, publier_post, enregistrer_metriques, list_posts, get_analytics,
)


# ── Inbox / réponse automatique ──────────────────────────────

@pytest.mark.asyncio
async def test_receive_message_creates_entry(db):
    result = await receive_message("instagram", "ig_user_42", "Bonjour, vous êtes ouverts ?", db, clinic_id=1)
    assert result["message"].plateforme == "instagram"
    assert result["message"].direction == "entrant"


@pytest.mark.asyncio
async def test_receive_message_rejects_unknown_platform(db):
    with pytest.raises(ValueError, match="non supportée"):
        await receive_message("linkedin", "x", "test", db, clinic_id=1)


@pytest.mark.asyncio
async def test_auto_reply_triggers_on_horaires_keyword(db):
    result = await receive_message("whatsapp", "+21600000010", "Vous êtes ouvert le dimanche ?", db, clinic_id=1)
    assert result["auto_reponse_envoyee"] is False


@pytest.mark.asyncio
async def test_auto_reply_triggers_on_rdv_keyword(db):
    result = await receive_message("whatsapp", "+21600000011", "Je veux prendre un rdv", db, clinic_id=1)
    assert result["auto_reponse_envoyee"] is False


@pytest.mark.asyncio
async def test_auto_reply_matched_but_undelivered_on_unconnected_platform(db):
    """Le mot-clé matche bien, mais Instagram n'étant pas connecté,
    la réponse n'est pas réellement envoyée — pas de faux succès."""
    result = await receive_message("instagram", "ig_9", "Vous êtes ouvert le dimanche ?", db, clinic_id=1)
    assert result["auto_reponse_envoyee"] is False


@pytest.mark.asyncio
async def test_no_auto_reply_for_unmatched_message(db):
    result = await receive_message("instagram", "ig_3", "Message sans mot-clé connu", db, clinic_id=1)
    assert result["auto_reponse_envoyee"] is False


@pytest.mark.asyncio
async def test_receive_message_matches_existing_patient_by_whatsapp(db, patient):
    result = await receive_message("whatsapp", patient.whatsapp_phone, "Bonjour", db, clinic_id=1)
    assert result["message"].patient_id == patient.id


@pytest.mark.asyncio
async def test_receive_message_no_patient_match_for_unknown_contact(db):
    result = await receive_message("whatsapp", "+21699999999", "Bonjour", db, clinic_id=1)
    assert result["message"].patient_id is None


@pytest.mark.asyncio
async def test_whatsapp_reply_not_sent_when_not_configured(db):
    result = await receive_message("whatsapp", "+21600000001", "Quel est le prix du botox ?", db, clinic_id=1)
    assert result["auto_reponse_envoyee"] is False


@pytest.mark.asyncio
async def test_reply_to_unconnected_platform_is_marked_echec(db):
    result = await receive_message("tiktok", "tk_1", "vos horaires ?", db, clinic_id=1)
    messages = await list_messages(db, plateforme="tiktok", clinic_id=1)
    sortant = [m for m in messages if m.direction == "sortant"][0]
    assert sortant.statut == "echec"
    assert result["auto_reponse_envoyee"] is False  # dispatch réel a échoué


@pytest.mark.asyncio
async def test_send_reply_unknown_message_raises(db):
    with pytest.raises(ValueError, match="non trouvé"):
        await send_reply(999999, "réponse", db, clinic_id=1)


@pytest.mark.asyncio
async def test_list_messages_filters_by_statut(db):
    await receive_message("instagram", "ig_a", "message sans mot-clé", db, clinic_id=1)
    nouveaux = await list_messages(db, statut="nouveau", clinic_id=1)
    assert len(nouveaux) == 1


# ── Posts ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_post_with_schedule_date_is_planifie(db):
    from datetime import datetime, timedelta
    post = await create_post({
        "plateforme": "instagram", "contenu": "Promo botox -20%",
        "date_publication_prevue": datetime.utcnow() + timedelta(days=1),
    }, created_by=1, db=db, clinic_id=1)
    assert post.statut == "planifie"


@pytest.mark.asyncio
async def test_create_post_without_schedule_is_brouillon(db):
    post = await create_post({"plateforme": "facebook", "contenu": "Nouveau soin"}, created_by=1, db=db, clinic_id=1)
    assert post.statut == "brouillon"


@pytest.mark.asyncio
async def test_create_post_rejects_unknown_platform(db):
    with pytest.raises(ValueError, match="non supportée"):
        await create_post({"plateforme": "snapchat", "contenu": "x"}, created_by=1, db=db, clinic_id=1)


@pytest.mark.asyncio
async def test_publier_post_on_unconnected_platform_marks_echec_honestly(db):
    post = await create_post({"plateforme": "tiktok", "contenu": "Vidéo avant/après"}, created_by=1, db=db, clinic_id=1)
    published = await publier_post(post.id, db, clinic_id=1)
    assert published.statut == "echec"
    assert "non connectée" in published.erreur


@pytest.mark.asyncio
async def test_publier_post_via_whatsapp_not_configured_fails(db):
    post = await create_post({"plateforme": "whatsapp", "contenu": "Nouvelle offre"}, created_by=1, db=db, clinic_id=1)
    published = await publier_post(post.id, db, clinic_id=1)
    assert published.statut == "echec"
    assert published.date_publication_reelle is None


@pytest.mark.asyncio
async def test_publier_post_twice_raises(db):
    post = await create_post({"plateforme": "whatsapp", "contenu": "x"}, created_by=1, db=db, clinic_id=1)
    first = await publier_post(post.id, db, clinic_id=1)
    assert first.statut == "echec"
    second = await publier_post(post.id, db, clinic_id=1)
    assert second.statut == "echec"


@pytest.mark.asyncio
async def test_enregistrer_metriques_updates_post(db):
    post = await create_post({"plateforme": "instagram", "contenu": "x"}, created_by=1, db=db, clinic_id=1)
    updated = await enregistrer_metriques(post.id, likes=120, commentaires=8, partages=3, impressions=5000, db=db, clinic_id=1)
    assert updated.likes == 120
    assert updated.impressions == 5000


@pytest.mark.asyncio
async def test_list_posts_filters_by_statut(db):
    await create_post({"plateforme": "facebook", "contenu": "a"}, created_by=1, db=db, clinic_id=1)
    p2 = await create_post({"plateforme": "whatsapp", "contenu": "b"}, created_by=1, db=db, clinic_id=1)
    await publier_post(p2.id, db, clinic_id=1)

    publies = await list_posts(db, statut="publie", clinic_id=1)
    assert len(publies) == 0


# ── Analytics ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analytics_aggregates_messages_by_platform_and_statut(db):
    await receive_message("instagram", "a", "sans mot-clé", db, clinic_id=1)
    await receive_message("instagram", "b", "sans mot-clé non plus", db, clinic_id=1)
    stats = await get_analytics(db, clinic_id=1)
    assert stats["messages"]["instagram"]["nouveau"] == 2


@pytest.mark.asyncio
async def test_analytics_sums_published_post_metrics(db):
    post = await create_post({"plateforme": "whatsapp", "contenu": "x"}, created_by=1, db=db, clinic_id=1)
    await publier_post(post.id, db, clinic_id=1)
    await enregistrer_metriques(post.id, likes=10, commentaires=1, partages=0, impressions=100, db=db, clinic_id=1)

    stats = await get_analytics(db, clinic_id=1)
    assert "whatsapp" not in stats["posts"]
