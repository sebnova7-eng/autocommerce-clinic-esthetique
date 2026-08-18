"""Tests étendus — services/marketing.py avec couverture complète"""

import pytest

from services.marketing import (
    create_campaign, get_campaign, list_campaigns, update_campaign_status,
    delete_campaign, get_target_patients, send_campaign, get_campaign_stats,
    get_overview, _apply_segment_filter
)
from models.database import Patient


@pytest.mark.asyncio
async def test_create_campaign_basic(db):
    """Crée une campagne marketing simple."""
    data = {
        "clinic_id": 1,
        "nom": "Promo Botox Été",
        "type": "whatsapp",
        "message_template": "Bonjour {prenom}, découvrez notre offre spéciale !",
        "created_by": 1,
    }
    campaign = await create_campaign(db, data)
    assert campaign.id is not None
    assert campaign.nom == "Promo Botox Été"
    assert campaign.type == "whatsapp"
    assert campaign.statut == "brouillon"


@pytest.mark.asyncio
async def test_create_campaign_with_segment(db):
    """Crée une campagne avec un segment cible."""
    data = {
        "clinic_id": 1,
        "nom": "Fidèles Gold",
        "type": "sms",
        "message_template": "Offre exclusive pour nos clients VIP",
        "segment_cible": {"niveau_fidelite": "gold", "is_active": True},
        "created_by": 1,
    }
    campaign = await create_campaign(db, data)
    assert campaign.segment_cible == {"niveau_fidelite": "gold", "is_active": True}


@pytest.mark.asyncio
async def test_get_campaign_exists(db):
    """Récupère une campagne existante."""
    data = {
        "clinic_id": 1,
        "nom": "Test Campaign",
        "type": "email",
        "created_by": 1,
    }
    campaign = await create_campaign(db, data)
    retrieved = await get_campaign(campaign.id, db)
    assert retrieved is not None
    assert retrieved.id == campaign.id
    assert retrieved.nom == "Test Campaign"


@pytest.mark.asyncio
async def test_get_campaign_not_found(db):
    """Retourne None pour une campagne inexistante."""
    result = await get_campaign(99999, db)
    assert result is None


@pytest.mark.asyncio
async def test_list_campaigns_empty(db):
    """Liste vide quand aucune campagne."""
    campaigns = await list_campaigns(db, clinic_id=1)
    assert campaigns == []


@pytest.mark.asyncio
async def test_list_campaigns_multiple(db):
    """Liste plusieurs campagnes."""
    for i in range(3):
        await create_campaign(db, {
            "clinic_id": 1,
            "nom": f"Campaign {i}",
            "type": "whatsapp",
            "created_by": 1,
        })
    campaigns = await list_campaigns(db, clinic_id=1)
    assert len(campaigns) == 3


@pytest.mark.asyncio
async def test_list_campaigns_filter_by_status(db):
    """Filtre les campagnes par statut."""
    await create_campaign(db, {
        "clinic_id": 1,
        "nom": "Brouillon",
        "type": "whatsapp",
        "created_by": 1,
    })
    c2 = await create_campaign(db, {
        "clinic_id": 1,
        "nom": "Envoyée",
        "type": "sms",
        "created_by": 1,
    })
    await update_campaign_status(c2.id, "envoyee", db)

    brouillons = await list_campaigns(db, clinic_id=1, statut="brouillon")
    envoyees = await list_campaigns(db, clinic_id=1, statut="envoyee")

    assert len(brouillons) == 1
    assert brouillons[0].nom == "Brouillon"
    assert len(envoyees) == 1
    assert envoyees[0].nom == "Envoyée"


@pytest.mark.asyncio
async def test_update_campaign_status(db):
    """Met à jour le statut d'une campagne."""
    campaign = await create_campaign(db, {
        "clinic_id": 1,
        "nom": "Test",
        "type": "whatsapp",
        "created_by": 1,
    })
    updated = await update_campaign_status(campaign.id, "planifiee", db)
    assert updated.statut == "planifiee"


@pytest.mark.asyncio
async def test_update_campaign_status_not_found(db):
    """Retourne None si campagne introuvable."""
    result = await update_campaign_status(99999, "envoyee", db)
    assert result is None


@pytest.mark.asyncio
async def test_delete_campaign_draft(db):
    """Supprime une campagne en brouillon."""
    campaign = await create_campaign(db, {
        "clinic_id": 1,
        "nom": "À supprimer",
        "type": "whatsapp",
        "created_by": 1,
    })
    success = await delete_campaign(campaign.id, db)
    assert success is True
    retrieved = await get_campaign(campaign.id, db)
    assert retrieved is None


@pytest.mark.asyncio
async def test_delete_campaign_sent_fails(db):
    """Ne peut pas supprimer une campagne envoyée."""
    campaign = await create_campaign(db, {
        "clinic_id": 1,
        "nom": "Envoyée",
        "type": "whatsapp",
        "created_by": 1,
    })
    await update_campaign_status(campaign.id, "envoyee", db)
    success = await delete_campaign(campaign.id, db)
    assert success is False


@pytest.mark.asyncio
async def test_apply_segment_filter_empty(db):
    """Applique un filtre vide (tous les patients actifs)."""
    p1 = Patient(clinic_id=1, nom="A", prenom="B", telephone="+216123", opted_out=False)
    p2 = Patient(clinic_id=1, nom="C", prenom="D", telephone="+216456", opted_out=True)
    db.add(p1)
    db.add(p2)
    await db.flush()

    from sqlalchemy import select
    query = select(Patient)
    query = _apply_segment_filter(query, {}, clinic_id=1)
    result = await db.execute(query)
    patients = list(result.scalars().all())
    assert len(patients) == 1
    assert patients[0].id == p1.id


@pytest.mark.asyncio
async def test_apply_segment_filter_by_loyalty_level(db):
    """Filtre par niveau de fidélité."""
    p1 = Patient(clinic_id=1, nom="Gold", prenom="Client", telephone="+216123",
                 niveau_fidelite="gold", opted_out=False)
    p2 = Patient(clinic_id=1, nom="Bronze", prenom="Client", telephone="+216456",
                 niveau_fidelite="bronze", opted_out=False)
    db.add(p1)
    db.add(p2)
    await db.flush()

    from sqlalchemy import select
    query = select(Patient)
    query = _apply_segment_filter(query, {"niveau_fidelite": "gold"}, clinic_id=1)
    result = await db.execute(query)
    patients = list(result.scalars().all())
    assert len(patients) == 1
    assert patients[0].nom == "Gold"


@pytest.mark.asyncio
async def test_apply_segment_filter_by_source(db):
    """Filtre par source d'acquisition."""
    p1 = Patient(clinic_id=1, nom="Insta", prenom="Client", telephone="+216123",
                 source_acquisition="instagram", opted_out=False)
    p2 = Patient(clinic_id=1, nom="WhatsApp", prenom="Client", telephone="+216456",
                 source_acquisition="whatsapp", opted_out=False)
    db.add(p1)
    db.add(p2)
    await db.flush()

    from sqlalchemy import select
    query = select(Patient)
    query = _apply_segment_filter(query, {"source_acquisition": "instagram"}, clinic_id=1)
    result = await db.execute(query)
    patients = list(result.scalars().all())
    assert len(patients) == 1
    assert patients[0].nom == "Insta"


@pytest.mark.asyncio
async def test_apply_segment_filter_by_city(db):
    """Filtre par ville."""
    p1 = Patient(clinic_id=1, nom="Tunis", prenom="Client", telephone="+216123",
                 ville="Tunis", opted_out=False)
    p2 = Patient(clinic_id=1, nom="Sfax", prenom="Client", telephone="+216456",
                 ville="Sfax", opted_out=False)
    db.add(p1)
    db.add(p2)
    await db.flush()

    from sqlalchemy import select
    query = select(Patient)
    query = _apply_segment_filter(query, {"ville": "Tunis"}, clinic_id=1)
    result = await db.execute(query)
    patients = list(result.scalars().all())
    assert len(patients) == 1
    assert patients[0].ville == "Tunis"


@pytest.mark.asyncio
async def test_apply_segment_filter_by_min_points(db):
    """Filtre par nombre minimum de points."""
    p1 = Patient(clinic_id=1, nom="Rich", prenom="Client", telephone="+216123",
                 points_fidelite=500, opted_out=False)
    p2 = Patient(clinic_id=1, nom="Poor", prenom="Client", telephone="+216456",
                 points_fidelite=50, opted_out=False)
    db.add(p1)
    db.add(p2)
    await db.flush()

    from sqlalchemy import select
    query = select(Patient)
    query = _apply_segment_filter(query, {"min_points": 100}, clinic_id=1)
    result = await db.execute(query)
    patients = list(result.scalars().all())
    assert len(patients) == 1
    assert patients[0].nom == "Rich"


@pytest.mark.asyncio
async def test_get_target_patients_requires_consent(db):
    """Récupère uniquement les patients ayant donné le consentement marketing."""
    p1 = Patient(clinic_id=1, nom="Consent", prenom="Yes", telephone="+216123",
                 consentement_marketing=True, opted_out=False)
    p2 = Patient(clinic_id=1, nom="NoConsent", prenom="No", telephone="+216456",
                 consentement_marketing=False, opted_out=False)
    db.add(p1)
    db.add(p2)
    await db.flush()

    patients = await get_target_patients({}, clinic_id=1, db=db)
    assert len(patients) == 1
    assert patients[0].nom == "Consent"


@pytest.mark.asyncio
async def test_send_campaign_no_patients(db):
    """Annule la campagne si aucun patient ciblé."""
    campaign = await create_campaign(db, {
        "clinic_id": 1,
        "nom": "Personne à cibler",
        "type": "whatsapp",
        "segment_cible": {"custom_ids": [99999]},
        "created_by": 1,
    })

    result = await send_campaign(campaign.id, db)
    assert result["statut"] == "annulee"
    assert result["nb_envoyes"] == 0


@pytest.mark.asyncio
async def test_send_campaign_with_mock_sender(db):
    """Envoie une campagne avec une fonction d'envoi mockée."""
    p1 = Patient(clinic_id=1, nom="Alice", prenom="Test", telephone="+216123",
                 whatsapp_phone="+216123", consentement_marketing=True, opted_out=False)
    p2 = Patient(clinic_id=1, nom="Bob", prenom="Test", telephone="+216456",
                 whatsapp_phone="+216456", consentement_marketing=True, opted_out=False)
    db.add(p1)
    db.add(p2)
    await db.flush()

    campaign = await create_campaign(db, {
        "clinic_id": 1,
        "nom": "Test Send",
        "type": "whatsapp",
        "message_template": "Bonjour {prenom}",
        "created_by": 1,
    })

    sent_to = []

    async def mock_sender(channel, to, content):
        sent_to.append(to)
        return {"success": True}

    result = await send_campaign(campaign.id, db, send_fn=mock_sender)
    assert result["nb_envoyes"] == 2
    assert result["nb_echecs"] == 0
    assert len(sent_to) == 2


@pytest.mark.asyncio
async def test_send_campaign_personalization(db):
    """Vérifie la personnalisation du message."""
    p = Patient(clinic_id=1, nom="Dupont", prenom="Jean", telephone="+216123",
                whatsapp_phone="+216123", consentement_marketing=True, opted_out=False)
    db.add(p)
    await db.flush()

    campaign = await create_campaign(db, {
        "clinic_id": 1,
        "nom": "Perso Test",
        "type": "whatsapp",
        "message_template": "Bonjour {prenom} {nom}",
        "created_by": 1,
    })

    received_content = []

    async def mock_sender(channel, to, content):
        received_content.append(content)
        return {"success": True}

    await send_campaign(campaign.id, db, send_fn=mock_sender)
    assert "Jean" in received_content[0]
    assert "Dupont" in received_content[0]


@pytest.mark.asyncio
async def test_get_campaign_stats(db):
    """Récupère les statistiques d'une campagne."""
    campaign = await create_campaign(db, {
        "clinic_id": 1,
        "nom": "Stats Test",
        "type": "email",
        "created_by": 1,
    })
    campaign.nb_envoyes = 100
    campaign.nb_ouverts = 25
    await db.flush()

    stats = await get_campaign_stats(campaign.id, db)
    assert stats["nb_envoyes"] == 100
    assert stats["nb_ouverts"] == 25
    assert stats["taux_ouverture"] == 25.0


@pytest.mark.asyncio
async def test_get_campaign_stats_not_found(db):
    """Retourne une erreur si campagne introuvable."""
    stats = await get_campaign_stats(99999, db)
    assert "error" in stats


@pytest.mark.asyncio
async def test_get_overview(db):
    """Récupère un aperçu des campagnes marketing."""
    for i in range(3):
        await create_campaign(db, {
            "clinic_id": 1,
            "nom": f"Campaign {i}",
            "type": "whatsapp",
            "created_by": 1,
        })

    overview = await get_overview(db, clinic_id=1)
    assert overview["total_campaigns"] == 3
    assert overview["brouillons"] == 3
    assert overview["envoyees"] == 0


@pytest.mark.asyncio
async def test_send_campaign_invalid_status(db):
    """Refuse d'envoyer une campagne avec un statut invalide."""
    campaign = await create_campaign(db, {
        "clinic_id": 1,
        "nom": "Invalid",
        "type": "whatsapp",
        "created_by": 1,
    })
    await update_campaign_status(campaign.id, "envoyee", db)

    with pytest.raises(ValueError, match="ne peut pas être envoyée"):
        await send_campaign(campaign.id, db)


@pytest.mark.asyncio
async def test_send_campaign_not_found(db):
    """Lève une erreur si campagne introuvable."""
    with pytest.raises(ValueError, match="introuvable"):
        await send_campaign(99999, db)
