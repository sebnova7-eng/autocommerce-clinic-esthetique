"""Tests — services/commissions.py"""
from decimal import Decimal

import pytest

from services.commissions import create_commission, valider_commission, marquer_payee, total_du_par_commercial
from models.database import Utilisateur, RoleEnum, StatutCommission


@pytest.fixture
async def commercial_avec_taux(db):
    u = Utilisateur(clinic_id=1, email="commercial@clinic.tn", hashed_password="x",
                     nom="Ben Salah", prenom="Nour", role=RoleEnum.COMMERCIAL.value,
                     taux_commission=Decimal("10.00"))
    db.add(u)
    await db.flush()
    return u


@pytest.mark.asyncio
async def test_create_commission_computes_amount(db, commercial_avec_taux, patient):
    commission = await create_commission(
        commercial_avec_taux.id, patient.id, facture_id=1, montant_ca=Decimal("500.000"), db=db,
    )
    assert commission.montant_commission == Decimal("50.000")
    assert commission.statut == StatutCommission.EN_ATTENTE.value


@pytest.mark.asyncio
async def test_create_commission_returns_none_for_zero_rate(db, patient, medecin):
    # medecin fixture n'a pas de taux_commission défini -> 0 par défaut
    commission = await create_commission(medecin.id, patient.id, facture_id=1,
                                          montant_ca=Decimal("500.000"), db=db)
    assert commission is None


@pytest.mark.asyncio
async def test_valider_commission_sets_statut_and_validateur(db, commercial_avec_taux, patient):
    commission = await create_commission(commercial_avec_taux.id, patient.id, 1, Decimal("100.000"), db)
    validated = await valider_commission(commission.id, validateur_id=99, db=db)
    assert validated.statut == StatutCommission.VALIDEE.value
    assert validated.validee_par_id == 99


@pytest.mark.asyncio
async def test_valider_commission_twice_raises(db, commercial_avec_taux, patient):
    commission = await create_commission(commercial_avec_taux.id, patient.id, 1, Decimal("100.000"), db)
    await valider_commission(commission.id, 99, db)
    with pytest.raises(ValueError, match="[Ss]tatut invalide"):
        await valider_commission(commission.id, 99, db)


@pytest.mark.asyncio
async def test_marquer_payee_requires_validated_first(db, commercial_avec_taux, patient):
    from datetime import date
    commission = await create_commission(commercial_avec_taux.id, patient.id, 1, Decimal("100.000"), db)
    with pytest.raises(ValueError, match="validée avant"):
        await marquer_payee(commission.id, date.today(), db)


@pytest.mark.asyncio
async def test_marquer_payee_after_validation_succeeds(db, commercial_avec_taux, patient):
    from datetime import date
    commission = await create_commission(commercial_avec_taux.id, patient.id, 1, Decimal("100.000"), db)
    await valider_commission(commission.id, 99, db)
    paid = await marquer_payee(commission.id, date.today(), db)
    assert paid.statut == StatutCommission.PAYEE.value


@pytest.mark.asyncio
async def test_commission_above_seuil_requires_two_validators(db, commercial_avec_taux, patient):
    # 10% de 6000 = 600 DT > COMMISSION_VALIDATION_SEUIL (500 DT)
    commission = await create_commission(commercial_avec_taux.id, patient.id, 1, Decimal("6000.000"), db)

    partial = await valider_commission(commission.id, validateur_id=1, db=db)
    assert partial.statut == StatutCommission.VALIDATION_PARTIELLE.value
    assert partial.validee_par_id == 1
    assert partial.validee_par_id_2 is None

    final = await valider_commission(commission.id, validateur_id=2, db=db)
    assert final.statut == StatutCommission.VALIDEE.value
    assert final.validee_par_id_2 == 2


@pytest.mark.asyncio
async def test_commission_above_seuil_rejects_same_validator_twice(db, commercial_avec_taux, patient):
    commission = await create_commission(commercial_avec_taux.id, patient.id, 1, Decimal("6000.000"), db)
    await valider_commission(commission.id, validateur_id=1, db=db)
    with pytest.raises(ValueError, match="personne différente"):
        await valider_commission(commission.id, validateur_id=1, db=db)


@pytest.mark.asyncio
async def test_total_du_excludes_paid_commissions(db, commercial_avec_taux, patient):
    from datetime import date
    await create_commission(commercial_avec_taux.id, patient.id, 1, Decimal("100.000"), db)
    c2 = await create_commission(commercial_avec_taux.id, patient.id, 2, Decimal("200.000"), db)
    await valider_commission(c2.id, 99, db)
    await marquer_payee(c2.id, date.today(), db)

    total = await total_du_par_commercial(commercial_avec_taux.id, db)
    assert total == Decimal("10.000")  # seule c1 (10% de 100) reste due
