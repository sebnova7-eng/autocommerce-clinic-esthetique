"""Tests étendus — services/business_intelligence.py"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from services.business_intelligence import BusinessIntelligenceService
from models.database import (
    Facture, Patient, StatutFacture
)


@pytest.mark.asyncio
async def test_get_revenue_summary_empty(db):
    """Retourne un résumé vide quand aucune facture."""
    result = await BusinessIntelligenceService.get_revenue_summary(db, clinic_id=1, period_days=30)
    assert result["total_revenue"] == 0
    assert result["total_invoices"] == 0


@pytest.mark.asyncio
async def test_get_revenue_summary_single_invoice(db):
    """Calcule le résumé avec une seule facture."""
    patient = Patient(clinic_id=1, nom="Test", prenom="Patient", telephone="+216123")
    db.add(patient)
    await db.flush()

    facture = Facture(
        clinic_id=1,
        patient_id=patient.id,
        numero_facture="F-2026-0001",
        date_emission=date.today(),
        actes=[],
        produits=[],
        sous_total=Decimal("100.000"),
        montant_tva=Decimal("19.000"),
        remise_globale_pct=Decimal("0.00"),
        taux_tva=Decimal("0.190"),
        total_ttc=Decimal("119.000"),
        statut=StatutFacture.PAYEE.value,
        created_by=1,
    )
    db.add(facture)
    await db.flush()

    result = await BusinessIntelligenceService.get_revenue_summary(db, clinic_id=1, period_days=30)
    assert result["total_revenue"] == 119.0
    assert result["total_invoices"] == 1
    assert result["avg_invoice"] == 119.0


@pytest.mark.asyncio
async def test_get_revenue_summary_multiple_invoices(db):
    """Calcule le résumé avec plusieurs factures."""
    patient = Patient(clinic_id=1, nom="Test", prenom="Patient", telephone="+216123")
    db.add(patient)
    await db.flush()

    for i in range(3):
        facture = Facture(
            clinic_id=1,
            patient_id=patient.id,
            numero_facture=f"F-2026-000{i+1}",
            date_emission=date.today(),
            actes=[],
            produits=[],
            sous_total=Decimal("100.000"),
            montant_tva=Decimal("19.000"),
            remise_globale_pct=Decimal("0.00"),
            taux_tva=Decimal("0.190"),
            total_ttc=Decimal("119.000"),
            statut=StatutFacture.PAYEE.value,
            created_by=1,
        )
        db.add(facture)
    await db.flush()

    result = await BusinessIntelligenceService.get_revenue_summary(db, clinic_id=1, period_days=30)
    assert result["total_revenue"] == 357.0  # 119 * 3
    assert result["total_invoices"] == 3
    assert result["avg_invoice"] == 119.0


@pytest.mark.asyncio
async def test_get_revenue_summary_filters_by_period(db):
    """Filtre les factures par période."""
    patient = Patient(clinic_id=1, nom="Test", prenom="Patient", telephone="+216123")
    db.add(patient)
    await db.flush()

    # Facture récente
    facture_recent = Facture(
        clinic_id=1,
        patient_id=patient.id,
        numero_facture="F-2026-0001",
        date_emission=date.today(),
        actes=[],
        produits=[],
        sous_total=Decimal("100.000"),
        montant_tva=Decimal("19.000"),
        remise_globale_pct=Decimal("0.00"),
        taux_tva=Decimal("0.190"),
        total_ttc=Decimal("119.000"),
        statut=StatutFacture.PAYEE.value,
        created_by=1,
    )
    db.add(facture_recent)

    # Facture ancienne (hors période)
    facture_old = Facture(
        clinic_id=1,
        patient_id=patient.id,
        numero_facture="F-2026-0002",
        date_emission=date.today() - timedelta(days=40),
        actes=[],
        produits=[],
        sous_total=Decimal("100.000"),
        montant_tva=Decimal("19.000"),
        remise_globale_pct=Decimal("0.00"),
        taux_tva=Decimal("0.190"),
        total_ttc=Decimal("119.000"),
        statut=StatutFacture.PAYEE.value,
        created_by=1,
    )
    db.add(facture_old)
    await db.flush()

    result = await BusinessIntelligenceService.get_revenue_summary(db, clinic_id=1, period_days=30)
    assert result["total_invoices"] == 1
    assert result["total_revenue"] == 119.0


@pytest.mark.asyncio
async def test_get_revenue_summary_ignores_unpaid(db):
    """Ignore les factures non payées."""
    patient = Patient(clinic_id=1, nom="Test", prenom="Patient", telephone="+216123")
    db.add(patient)
    await db.flush()

    # Facture payée
    facture_paid = Facture(
        clinic_id=1,
        patient_id=patient.id,
        numero_facture="F-2026-0001",
        date_emission=date.today(),
        actes=[],
        produits=[],
        sous_total=Decimal("100.000"),
        montant_tva=Decimal("19.000"),
        remise_globale_pct=Decimal("0.00"),
        taux_tva=Decimal("0.190"),
        total_ttc=Decimal("119.000"),
        statut=StatutFacture.PAYEE.value,
        created_by=1,
    )
    db.add(facture_paid)

    # Facture en brouillon
    facture_draft = Facture(
        clinic_id=1,
        patient_id=patient.id,
        numero_facture="F-2026-0002",
        date_emission=date.today(),
        actes=[],
        produits=[],
        sous_total=Decimal("100.000"),
        montant_tva=Decimal("19.000"),
        remise_globale_pct=Decimal("0.00"),
        taux_tva=Decimal("0.190"),
        total_ttc=Decimal("119.000"),
        statut=StatutFacture.BROUILLON.value,
        created_by=1,
    )
    db.add(facture_draft)
    await db.flush()

    result = await BusinessIntelligenceService.get_revenue_summary(db, clinic_id=1, period_days=30)
    assert result["total_invoices"] == 1
    assert result["total_revenue"] == 119.0


@pytest.mark.asyncio
async def test_get_revenue_summary_by_clinic(db):
    """Filtre les factures par clinique."""
    patient1 = Patient(clinic_id=1, nom="Clinic1", prenom="Patient", telephone="+216123")
    patient2 = Patient(clinic_id=2, nom="Clinic2", prenom="Patient", telephone="+216456")
    db.add(patient1)
    db.add(patient2)
    await db.flush()

    for patient_id, clinic_id in [(patient1.id, 1), (patient2.id, 2)]:
        facture = Facture(
            clinic_id=clinic_id,
            patient_id=patient_id,
            numero_facture=f"F-{clinic_id}-0001",
            date_emission=date.today(),
            actes=[],
            produits=[],
            sous_total=Decimal("100.000"),
            montant_tva=Decimal("19.000"),
            remise_globale_pct=Decimal("0.00"),
            taux_tva=Decimal("0.190"),
            total_ttc=Decimal("119.000"),
            statut=StatutFacture.PAYEE.value,
            created_by=1,
        )
        db.add(facture)
    await db.flush()

    result_clinic1 = await BusinessIntelligenceService.get_revenue_summary(db, clinic_id=1, period_days=30)
    result_clinic2 = await BusinessIntelligenceService.get_revenue_summary(db, clinic_id=2, period_days=30)

    assert result_clinic1["total_invoices"] == 1
    assert result_clinic2["total_invoices"] == 1


@pytest.mark.asyncio
async def test_get_revenue_summary_with_multiple_practitioners(db):
    """Teste le résumé des revenus avec plusieurs praticiens."""
    patient = Patient(clinic_id=1, nom="Test", prenom="Patient", telephone="+216123")
    db.add(patient)
    await db.flush()

    facture = Facture(
        clinic_id=1,
        patient_id=patient.id,
        numero_facture="F-2026-0001",
        date_emission=date.today(),
        actes=[],
        produits=[],
        sous_total=Decimal("100.000"),
        montant_tva=Decimal("19.000"),
        remise_globale_pct=Decimal("0.00"),
        taux_tva=Decimal("0.190"),
        total_ttc=Decimal("119.000"),
        statut=StatutFacture.PAYEE.value,
        created_by=1,
    )
    db.add(facture)
    await db.flush()

    result = await BusinessIntelligenceService.get_revenue_summary(db, clinic_id=1, period_days=30)
    assert result["total_invoices"] == 1


@pytest.mark.asyncio
async def test_get_revenue_summary_revenue_by_practitioner(db):
    """Teste le calcul des revenus par praticien."""
    patient = Patient(clinic_id=1, nom="Test", prenom="Patient", telephone="+216123")
    db.add(patient)
    await db.flush()

    facture = Facture(
        clinic_id=1,
        patient_id=patient.id,
        numero_facture="F-2026-0001",
        date_emission=date.today(),
        actes=[],
        produits=[],
        sous_total=Decimal("100.000"),
        montant_tva=Decimal("19.000"),
        remise_globale_pct=Decimal("0.00"),
        taux_tva=Decimal("0.190"),
        total_ttc=Decimal("119.000"),
        statut=StatutFacture.PAYEE.value,
        created_by=1,
    )
    db.add(facture)
    await db.flush()

    result = await BusinessIntelligenceService.get_revenue_summary(db, clinic_id=1, period_days=30)
    assert "revenue_by_practitioner" in result


@pytest.mark.asyncio
async def test_get_revenue_summary_revenue_by_acte(db):
    """Teste le calcul des revenus par acte."""
    patient = Patient(clinic_id=1, nom="Test", prenom="Patient", telephone="+216123")
    db.add(patient)
    await db.flush()

    facture = Facture(
        clinic_id=1,
        patient_id=patient.id,
        numero_facture="F-2026-0001",
        date_emission=date.today(),
        actes=[{"nom": "Botox", "prix": "250.000"}],
        produits=[],
        sous_total=Decimal("250.000"),
        montant_tva=Decimal("47.500"),
        remise_globale_pct=Decimal("0.00"),
        taux_tva=Decimal("0.190"),
        total_ttc=Decimal("297.500"),
        statut=StatutFacture.PAYEE.value,
        created_by=1,
    )
    db.add(facture)
    await db.flush()

    result = await BusinessIntelligenceService.get_revenue_summary(db, clinic_id=1, period_days=30)
    assert "revenue_by_acte" in result


@pytest.mark.asyncio
async def test_get_revenue_summary_revenue_by_day(db):
    """Teste le calcul des revenus par jour."""
    patient = Patient(clinic_id=1, nom="Test", prenom="Patient", telephone="+216123")
    db.add(patient)
    await db.flush()

    # Créer quelques factures
    for i in range(3):
        facture = Facture(
            clinic_id=1,
            patient_id=patient.id,
            numero_facture=f"F-2026-000{i+1}",
            date_emission=date.today() - timedelta(days=i),
            actes=[],
            produits=[],
            sous_total=Decimal("100.000"),
            montant_tva=Decimal("19.000"),
            remise_globale_pct=Decimal("0.00"),
            taux_tva=Decimal("0.190"),
            total_ttc=Decimal("119.000"),
            statut=StatutFacture.PAYEE.value,
            created_by=1,
        )
        db.add(facture)
    await db.flush()

    result = await BusinessIntelligenceService.get_revenue_summary(db, clinic_id=1, period_days=30)
    assert "revenue_by_day" in result


@pytest.mark.asyncio
async def test_get_revenue_summary_average_calculation(db):
    """Teste le calcul de la moyenne des factures."""
    patient = Patient(clinic_id=1, nom="Test", prenom="Patient", telephone="+216123")
    db.add(patient)
    await db.flush()

    # Créer 2 factures avec des montants différents
    for i, montant in enumerate([Decimal("100.000"), Decimal("200.000")]):
        facture = Facture(
            clinic_id=1,
            patient_id=patient.id,
            numero_facture=f"F-2026-000{i+1}",
            date_emission=date.today(),
            actes=[],
            produits=[],
            sous_total=montant,
            montant_tva=montant * Decimal("0.19"),
            remise_globale_pct=Decimal("0.00"),
            taux_tva=Decimal("0.190"),
            total_ttc=montant * Decimal("1.19"),
            statut=StatutFacture.PAYEE.value,
            created_by=1,
        )
        db.add(facture)
    await db.flush()

    result = await BusinessIntelligenceService.get_revenue_summary(db, clinic_id=1, period_days=30)
    assert result["total_invoices"] == 2
    assert result["avg_invoice"] > 0
