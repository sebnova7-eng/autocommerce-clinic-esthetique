"""Tests — services/recrutement.py"""
import pytest

from services.recrutement import create_candidature, changer_statut, list_candidatures
from models.database import StatutCandidature


@pytest.mark.asyncio
async def test_create_candidature_defaults_to_recu(db):
    c = await create_candidature({
        "poste": "Assistante médicale", "nom_candidat": "Salma Jendoubi", "email": "s@x.tn",
    }, db)
    assert c.statut == StatutCandidature.RECU.value


@pytest.mark.asyncio
async def test_changer_statut_valid_transition(db):
    c = await create_candidature({"poste": "Médecin", "nom_candidat": "X", "email": "x@x.tn"}, db)
    updated = await changer_statut(c.id, StatutCandidature.EN_ETUDE.value, evaluateur_id=1, db=db)
    assert updated.statut == StatutCandidature.EN_ETUDE.value


@pytest.mark.asyncio
async def test_changer_statut_rejects_invalid_transition(db):
    c = await create_candidature({"poste": "Médecin", "nom_candidat": "X", "email": "x@x.tn"}, db)
    with pytest.raises(ValueError, match="invalide"):
        await changer_statut(c.id, StatutCandidature.ACCEPTE.value, evaluateur_id=1, db=db)


@pytest.mark.asyncio
async def test_changer_statut_rejects_transition_from_terminal_state(db):
    c = await create_candidature({"poste": "Médecin", "nom_candidat": "X", "email": "x@x.tn"}, db)
    await changer_statut(c.id, StatutCandidature.REFUSE.value, evaluateur_id=1, db=db)
    with pytest.raises(ValueError, match="invalide"):
        await changer_statut(c.id, StatutCandidature.EN_ETUDE.value, evaluateur_id=1, db=db)


@pytest.mark.asyncio
async def test_changer_statut_unknown_id_raises(db):
    with pytest.raises(ValueError, match="non trouvée"):
        await changer_statut(999999, StatutCandidature.EN_ETUDE.value, evaluateur_id=1, db=db)


@pytest.mark.asyncio
async def test_list_candidatures_filters_by_poste(db):
    await create_candidature({"poste": "Médecin", "nom_candidat": "A", "email": "a@x.tn"}, db)
    await create_candidature({"poste": "Assistante", "nom_candidat": "B", "email": "b@x.tn"}, db)
    resultats = await list_candidatures(db, poste="Médecin")
    assert len(resultats) == 1
    assert resultats[0].nom_candidat == "A"
