"""Tests — services/facture_scanner.py (valider_depense, _encode_image)

N'exerce PAS extract_facture_ia / upload_facture : ces fonctions
appellent OpenAI Vision et Celery et nécessitent des identifiants
externes réels — hors de portée de tests unitaires sans mocks dédiés.
"""
from datetime import date
from decimal import Decimal

import pytest

from services.facture_scanner import valider_depense, _encode_image
from models.database import Depense, StatutDepense


def test_encode_image_returns_base64_string():
    encoded = _encode_image(b"donnee-binaire")
    import base64
    assert base64.b64decode(encoded) == b"donnee-binaire"


@pytest.mark.asyncio
async def test_valider_depense_applies_corrections(db):
    depense = Depense(
        clinic_id=1, titre="Achat initial", montant_ht=Decimal("0.000"),
        montant_tva=Decimal("0.000"), montant_ttc=Decimal("0.000"),
        date_depense=date.today(), periode_comptable=date.today(),
        facture_scan_statut=StatutDepense.EN_ATTENTE.value,
    )
    db.add(depense)
    await db.flush()

    updated, medicaments = await valider_depense(
        depense_id=depense.id, validateur_id=1,
        corrections={"fournisseur": "Pharma Tunisie", "montant_ttc": 150.5},
        db=db,
    )

    assert updated.fournisseur == "Pharma Tunisie"
    assert updated.montant_ttc == Decimal("150.5")
    assert updated.facture_scan_statut == StatutDepense.VALIDEE.value
    assert medicaments == []


@pytest.mark.asyncio
async def test_valider_depense_autofills_from_ia_extraction(db):
    depense = Depense(
        clinic_id=1, titre="", montant_ht=Decimal("0.000"),
        montant_tva=Decimal("0.000"), montant_ttc=Decimal("0.000"),
        date_depense=date.today(), periode_comptable=date.today(),
        facture_scan_statut=StatutDepense.TRAITEE_IA.value,
        extraction_ia={
            "fournisseur_nom": "Fournisseur IA",
            "numero_facture": "F-2026-001",
            "total_ht": 100.0, "total_tva": 19.0, "total_ttc": 119.0,
            "lignes": [{"description": "Botox", "est_medicament": True}],
        },
    )
    db.add(depense)
    await db.flush()

    updated, medicaments = await valider_depense(
        depense_id=depense.id, validateur_id=1, corrections=None, db=db,
    )

    assert updated.fournisseur == "Fournisseur IA"
    assert updated.montant_ttc == Decimal("119.0")
    assert updated.titre == "Facture F-2026-001"
    assert len(medicaments) == 1


@pytest.mark.asyncio
async def test_valider_depense_corrections_take_priority_over_ia(db):
    depense = Depense(
        clinic_id=1, titre="", montant_ht=Decimal("0.000"),
        montant_tva=Decimal("0.000"), montant_ttc=Decimal("0.000"),
        date_depense=date.today(), periode_comptable=date.today(),
        facture_scan_statut=StatutDepense.EN_ATTENTE.value,
        extraction_ia={"fournisseur_nom": "Fournisseur IA", "total_ttc": 50.0},
    )
    db.add(depense)
    await db.flush()

    updated, _ = await valider_depense(
        depense_id=depense.id, validateur_id=1,
        corrections={"fournisseur": "Fournisseur Corrigé"},
        db=db,
    )
    # La correction manuelle doit primer sur l'auto-remplissage IA
    assert updated.fournisseur == "Fournisseur Corrigé"


@pytest.mark.asyncio
async def test_valider_depense_rejects_invalid_statut(db):
    depense = Depense(
        clinic_id=1, titre="x", montant_ht=Decimal("0.000"),
        montant_tva=Decimal("0.000"), montant_ttc=Decimal("0.000"),
        date_depense=date.today(), periode_comptable=date.today(),
        facture_scan_statut=StatutDepense.VALIDEE.value,
    )
    db.add(depense)
    await db.flush()

    with pytest.raises(ValueError, match="[Ss]tatut invalide"):
        await valider_depense(depense_id=depense.id, validateur_id=1, corrections=None, db=db)


@pytest.mark.asyncio
async def test_valider_depense_unknown_id_raises(db):
    with pytest.raises(ValueError, match="non trouvée"):
        await valider_depense(depense_id=999999, validateur_id=1, corrections=None, db=db)
