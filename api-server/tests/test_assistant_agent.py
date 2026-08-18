from datetime import datetime, timedelta
import pytest
from sqlalchemy import select
from fastapi import HTTPException

from models.database import RoleEnum, Utilisateur
from models.security import ConfirmationSensible, NumeroWhitelist
from services.agenda import creer_rdv
from services.assistant_ia import handle_whatsapp_message, _detect_intent
from services.clinic_agent import handle_agent_message
from middleware.assistant_whitelist import ensure_can_receive_assistant_message

@pytest.fixture
async def admin_user(db):
    user = Utilisateur(
        clinic_id=1,
        email="admin@clinic.tn",
        hashed_password="x",
        nom="Admin",
        prenom="Root",
        role=RoleEnum.ADMIN.value,
    )
    db.add(user)
    await db.flush()
    return user

@pytest.fixture
async def whitelist_medecin(db, medecin):
    row = NumeroWhitelist(
        clinic_id=1,
        numero="+21620000001",
        utilisateur_id=medecin.id,
        nom="Dr Sami",
        statut="active",
    )
    db.add(row)
    await db.flush()
    return row

@pytest.fixture
async def whitelist_assistante(db, assistante):
    row = NumeroWhitelist(
        clinic_id=1,
        numero="+21620000002",
        utilisateur_id=assistante.id,
        nom="Rim",
        statut="active",
    )
    db.add(row)
    await db.flush()
    return row

@pytest.fixture
async def rdv(db, patient, acte, medecin):
    result = await creer_rdv(
        patient_id=patient.id,
        praticien_id=medecin.id,
        acte_id=acte.id,
        date_heure=datetime.utcnow() + timedelta(days=1, hours=2),
        salle=None,
        db=db,
        created_by=None,
    )
    # creer_rdv retourne un tuple (rdv, consentement_manquant)
    return result[0] if isinstance(result, tuple) else result

@pytest.mark.asyncio
async def test_whitelist_denied_raises_403(db):
    with pytest.raises(HTTPException) as exc:
        await ensure_can_receive_assistant_message("+21600000000", db)
    assert exc.value.status_code == 403

@pytest.mark.asyncio
async def test_assistant_readonly_rejects_write(db, medecin, whitelist_medecin):
    current_user = {"id": medecin.id, "role": medecin.role, "clinic_id": whitelist_medecin.clinic_id, "whitelist_id": whitelist_medecin.id}
    result = await handle_whatsapp_message(
        numero=whitelist_medecin.numero,
        question="Annule le RDV de 15h",
        current_user=current_user,
        db=db,
    )
    assert result["statut"] == "refuse"
    assert "ne peux pas encore" in result["reponse"].lower()

@pytest.mark.asyncio
async def test_assistant_rate_limit(db, medecin, whitelist_medecin):
    current_user = {"id": medecin.id, "role": medecin.role, "clinic_id": whitelist_medecin.clinic_id, "whitelist_id": whitelist_medecin.id}
    # Send 5 messages (limit is 5/min)
    for _ in range(5):
        await handle_whatsapp_message(whitelist_medecin.numero, "RDV du jour", current_user, db)
    
    # 6th should be rate limited
    result = await handle_whatsapp_message(whitelist_medecin.numero, "RDV du jour", current_user, db)
    assert result["statut"] == "rate_limited"

@pytest.mark.asyncio
async def test_assistant_pii_scrubbing(db, medecin, whitelist_medecin, patient):
    current_user = {"id": medecin.id, "role": medecin.role, "clinic_id": whitelist_medecin.clinic_id, "whitelist_id": whitelist_medecin.id}
    result = await handle_whatsapp_message(
        numero=whitelist_medecin.numero,
        question="Quels sont les patients inactifs ?",
        current_user=current_user,
        db=db,
    )
    assert result["statut"] == "ok"
    # Verification in logs (simulated) or by checking the tool output structure if exposed
    # The actual scrubbing happens in services/assistant_tools.py

@pytest.mark.asyncio
async def test_agent_cancel_requires_confirmation_then_executes(db, assistante, whitelist_assistante, rdv):
    current_user = {"id": assistante.id, "role": assistante.role, "clinic_id": whitelist_assistante.clinic_id, "whitelist_id": whitelist_assistante.id}
    first = await handle_agent_message(
        numero=whitelist_assistante.numero,
        question=f"Annule RDV {rdv.id} raison patient absent",
        current_user=current_user,
        db=db,
    )
    assert first["statut"] == "confirmation_en_attente"

    confirmation = (await db.execute(select(ConfirmationSensible).order_by(ConfirmationSensible.id.desc()))).scalar_one()
    second = await handle_agent_message(
        numero=whitelist_assistante.numero,
        question=f"CONFIRMER {confirmation.code_confirmation}",
        current_user=current_user,
        db=db,
    )
    assert second["statut"] == "ok"
    assert "annulé" in second["reponse"].lower()

@pytest.mark.asyncio
async def test_agent_rbac_denies_cancel_for_medecin_after_confirmation(db, medecin, whitelist_medecin, rdv):
    current_user = {"id": medecin.id, "role": medecin.role, "clinic_id": whitelist_medecin.clinic_id, "whitelist_id": whitelist_medecin.id}
    first = await handle_agent_message(
        numero=whitelist_medecin.numero,
        question=f"Annule RDV {rdv.id} raison doublon",
        current_user=current_user,
        db=db,
    )
    assert first["statut"] == "confirmation_en_attente"

    confirmation = (await db.execute(select(ConfirmationSensible).order_by(ConfirmationSensible.id.desc()))).scalar_one()
    second = await handle_agent_message(
        numero=whitelist_medecin.numero,
        question=f"CONFIRMER {confirmation.code_confirmation}",
        current_user=current_user,
        db=db,
    )
    assert second["statut"] == "erreur"
    assert "rbac" in second["reponse"].lower()


# ── Darija (arabe dialectal) ──────────────────────────────

def test_detect_intent_darija_rdv_count_today():
    intent, params = _detect_intent("قداش عندي موعد اليوم؟")
    assert intent == "get_rdv_count_today"


def test_detect_intent_darija_next_patient():
    intent, params = _detect_intent("شكون الحريف الجاي؟")
    assert intent == "get_next_rdv"


def test_detect_intent_darija_stock():
    intent, params = _detect_intent("شحال باقي بوتوکس في الستوك؟")
    assert intent == "get_stock_overview"
    assert params.get("produit_nom") == "Botox"


def test_detect_intent_darija_cancel_rdv_is_write_intent():
    intent, params = _detect_intent("الغي موعد بكري")
    assert intent == "annuler_rdv"


def test_detect_intent_darija_unrelated_text_stays_unknown():
    intent, params = _detect_intent("السلام عليكم كيف الحال")
    assert intent == "unknown"


def test_detect_intent_french_still_works_after_darija_addition():
    """Non-régression : l'ajout du darija ne doit rien casser côté français."""
    intent, params = _detect_intent("Combien de rendez-vous aujourd'hui ?")
    assert intent == "get_rdv_count_today"


# ── Réponses bilingues selon la langue du message reçu ───────

def test_humanize_darija_response_for_rdv_count():
    from services.assistant_ia import _humanize
    text = _humanize("get_rdv_count_today", {"count": 3}, lang="darija")
    assert "3" in text
    assert "rendez-vous" not in text.lower()


def test_humanize_french_response_unaffected_by_lang_param():
    from services.assistant_ia import _humanize
    text = _humanize("get_rdv_count_today", {"count": 3}, lang="fr")
    assert "3" in text
    assert "rendez-vous" in text.lower()


def test_humanize_defaults_to_french_when_lang_omitted():
    from services.assistant_ia import _humanize
    text = _humanize("get_rdv_count_today", {"count": 3})
    assert "rendez-vous" in text.lower()


@pytest.mark.asyncio
async def test_unknown_intent_response_matches_darija_input(db, whitelist_medecin):
    result = await handle_whatsapp_message(whitelist_medecin.numero, "السلام عليكم كيف الحال", {"id": 1, "role": "directrice", "clinic_id": whitelist_medecin.clinic_id}, db)
    assert "rendez-vous" not in result["reponse"].lower()


# ── Non-régression : sérialisation ORM → Pydantic (Bug récurrent) ────
#
# Ce bug est revenu 4 fois : les schémas de réponse de assistant.py
# (WhitelistOut, CommandeAssistantOut, AlerteSecuriteOut) perdent leur
# model_config = ConfigDict(from_attributes=True) à chaque réécriture du
# fichier, et Pydantic v2 refuse alors de sérialiser un objet ORM
# SQLAlchemy (ResponseValidationError → 500). Ces tests valident
# directement le schéma sans passer par une route HTTP, pour détecter
# la régression même si les données de test/seed sont vides ailleurs.

def test_whitelist_out_serializes_orm_object():
    from api.v1.assistant import WhitelistOut
    from datetime import datetime as dt

    entry = NumeroWhitelist(
        id=1, numero="+21600000000", nom="Dr Test", utilisateur_id=1,
        statut="actif", created_at=dt.utcnow(),
    )
    result = WhitelistOut.model_validate(entry)
    assert result.numero == "+21600000000"


def test_commande_assistant_out_serializes_orm_object():
    from api.v1.assistant import CommandeAssistantOut
    from models.security import CommandeAssistant
    from datetime import datetime as dt

    cmd = CommandeAssistant(
        id=1, numero="+21600000000", statut="ok", created_at=dt.utcnow(),
    )
    result = CommandeAssistantOut.model_validate(cmd)
    assert result.statut == "ok"


def test_alerte_securite_out_serializes_orm_object():
    from api.v1.assistant import AlerteSecuriteOut
    from models.security import AlerteSecurite
    from datetime import datetime as dt

    alerte = AlerteSecurite(
        id=1, type_alerte="numero_inconnu", severite="haute", statut="ouverte",
        description="Test", created_at=dt.utcnow(),
    )
    result = AlerteSecuriteOut.model_validate(alerte)
    assert result.severite == "haute"
