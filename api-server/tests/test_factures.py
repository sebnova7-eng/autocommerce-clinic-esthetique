"""Tests — services/factures.py"""
from decimal import Decimal

import pytest

import services.factures as factures_module
from services.factures import create_facture, marquer_payee, annuler_facture, list_factures
from models.database import StatutFacture, Utilisateur, RoleEnum, Facture


@pytest.mark.asyncio
async def test_create_facture_retries_on_numero_collision(db, patient, monkeypatch):
    """Simule deux créations concurrentes qui calculeraient le même numéro
    (race condition sur le COUNT) : la contrainte unique doit déclencher
    un nouvel essai plutôt qu'une erreur 500."""
    calls = {"n": 0}
    real_generate = factures_module._generate_numero_facture

    async def flaky_generate(db_arg):
        calls["n"] += 1
        if calls["n"] == 1:
            return "F-COLLISION-0001"
        return await real_generate(db_arg)

    # Pré-insère une facture avec le numéro que le premier essai va reproduire
    db.add(Facture(
        clinic_id=1, patient_id=patient.id, numero_facture="F-COLLISION-0001",
        actes=[], produits=[], sous_total=Decimal("0"), montant_tva=Decimal("0"),
        remise_globale_pct=Decimal("0"), taux_tva=Decimal("0.190"), total_ttc=Decimal("0"),
        created_by=1, statut=StatutFacture.BROUILLON.value,
    ))
    await db.flush()

    monkeypatch.setattr(factures_module, "_generate_numero_facture", flaky_generate)
    facture = await create_facture({"patient_id": patient.id, "actes": []}, created_by=1, db=db)
    assert facture.numero_facture != "F-COLLISION-0001"
    assert calls["n"] >= 2


@pytest.mark.asyncio
async def test_create_facture_computes_totals(db, patient):
    facture = await create_facture({
        "patient_id": patient.id,
        "actes": [{"description": "Botox", "prix": "250.000", "quantite": 1}],
    }, created_by=1, db=db)
    assert facture.sous_total == Decimal("250.000")
    assert facture.montant_tva == Decimal("47.500")
    assert facture.total_ttc == Decimal("297.500")
    assert facture.statut == StatutFacture.BROUILLON.value


@pytest.mark.asyncio
async def test_create_facture_applies_remise(db, patient):
    facture = await create_facture({
        "patient_id": patient.id,
        "actes": [{"description": "Botox", "prix": "1000.000", "quantite": 1}],
        "remise_globale_pct": "10.00",
        "taux_tva": "0.190",
    }, created_by=1, db=db)
    # sous_total = avant remise ; remise puis TVA appliquées seulement au total_ttc
    # 1000 - 10% = 900, + 19% TVA = 1071
    assert facture.sous_total == Decimal("1000.000")
    assert facture.total_ttc == Decimal("1071.000")


@pytest.mark.asyncio
async def test_create_facture_numbers_sequentially(db, patient):
    f1 = await create_facture({"patient_id": patient.id, "actes": []}, created_by=1, db=db)
    f2 = await create_facture({"patient_id": patient.id, "actes": []}, created_by=1, db=db)
    assert f1.numero_facture != f2.numero_facture
    assert f1.numero_facture.startswith("F-")


@pytest.mark.asyncio
async def test_create_facture_unknown_patient_raises(db):
    with pytest.raises(ValueError, match="non trouvé"):
        await create_facture({"patient_id": 999999, "actes": []}, created_by=1, db=db)


@pytest.mark.asyncio
async def test_marquer_payee_sets_statut_and_awards_points(db, patient):
    facture = await create_facture({
        "patient_id": patient.id,
        "actes": [{"description": "Acide hyaluronique", "prix": "500.000", "quantite": 1}],
        "taux_tva": "0.00",
    }, created_by=1, db=db)

    result = await marquer_payee(facture.id, "carte", db)
    assert result["facture"].statut == StatutFacture.PAYEE.value
    assert result["points_gagnes"] == 50  # 500 / 10

    await db.refresh(patient)
    assert patient.points_fidelite == 50


@pytest.mark.asyncio
async def test_marquer_payee_generates_commission_when_commercial_assigned(db, patient):
    commercial = Utilisateur(clinic_id=1, email="com@clinic.tn", hashed_password="x",
                              nom="A", prenom="B", role=RoleEnum.COMMERCIAL.value,
                              taux_commission=Decimal("15.00"))
    db.add(commercial)
    await db.flush()
    patient.commercial_id = commercial.id
    await db.flush()

    facture = await create_facture({
        "patient_id": patient.id,
        "actes": [{"description": "Botox", "prix": "1000.000", "quantite": 1}],
        "taux_tva": "0.00",
    }, created_by=1, db=db)

    result = await marquer_payee(facture.id, "especes", db)
    assert result["commission"] is not None
    assert result["commission"].montant_commission == Decimal("150.000")


@pytest.mark.asyncio
async def test_marquer_payee_twice_returns_same(db, patient):
    facture = await create_facture({"patient_id": patient.id, "actes": []}, created_by=1, db=db)
    await marquer_payee(facture.id, "carte", db)
    # La fonction DOIT lever ValueError si la facture est déjà payée
    with pytest.raises(ValueError, match="déjà marquée comme payée"):
        await marquer_payee(facture.id, "especes", db)


@pytest.mark.asyncio
async def test_annuler_facture_blocks_if_already_paid(db, patient):
    facture = await create_facture({"patient_id": patient.id, "actes": []}, created_by=1, db=db)
    await marquer_payee(facture.id, "carte", db)
    with pytest.raises(ValueError, match="avoir"):
        await annuler_facture(facture.id, "erreur", db)


@pytest.mark.asyncio
async def test_annuler_facture_succeeds_on_draft(db, patient):
    facture = await create_facture({"patient_id": patient.id, "actes": []}, created_by=1, db=db)
    annulee = await annuler_facture(facture.id, "patient a annulé", db)
    assert annulee.statut == StatutFacture.ANNULEE.value


@pytest.mark.asyncio
async def test_list_factures_filters_by_patient(db, patient):
    await create_facture({"patient_id": patient.id, "actes": []}, created_by=1, db=db)
    factures, total = await list_factures(db, patient_id=patient.id)
    assert len(factures) == 1
    assert total == 1


@pytest.mark.asyncio
async def test_list_factures_pagination(db, patient):
    for _ in range(3):
        await create_facture({"patient_id": patient.id, "actes": []}, created_by=1, db=db)

    page1, total = await list_factures(db, patient_id=patient.id, skip=0, limit=2)
    assert len(page1) == 2
    assert total == 3

    page2, total2 = await list_factures(db, patient_id=patient.id, skip=2, limit=2)
    assert len(page2) == 1
    assert total2 == 3
