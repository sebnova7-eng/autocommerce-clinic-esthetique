"""Tests étendus — services/pdf_generator.py"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from services.pdf_generator import generate_invoice_pdf
from models.database import (
    Facture, Patient, StatutFacture
)


@pytest.mark.asyncio
async def test_generate_invoice_pdf_basic(db):
    """Génère un PDF de facture simple."""
    patient = Patient(
        clinic_id=1,
        nom="Dupont",
        prenom="Jean",
        telephone="+216123",
        email="jean@example.com",
    )
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

    clinic_info = {
        "clinic_name": "AutoCommerce Clinic",
        "address": "123 Rue de la Santé, Tunis",
        "phone": "+216 71 123 456",
    }
    
    result = await generate_invoice_pdf(facture, patient, clinic_info)
    assert result is not None
    assert isinstance(result, bytes)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_generate_invoice_pdf_with_discount(db):
    """Génère un PDF de facture avec remise."""
    patient = Patient(
        clinic_id=1,
        nom="Dupont",
        prenom="Jean",
        telephone="+216123",
        email="jean@example.com",
    )
    db.add(patient)
    await db.flush()

    facture = Facture(
        clinic_id=1,
        patient_id=patient.id,
        numero_facture="F-2026-0002",
        date_emission=date.today(),
        actes=[{"nom": "Botox", "prix": "1000.000"}],
        produits=[],
        sous_total=Decimal("1000.000"),
        montant_tva=Decimal("171.000"),
        remise_globale_pct=Decimal("10.00"),
        taux_tva=Decimal("0.190"),
        total_ttc=Decimal("1071.000"),
        statut=StatutFacture.PAYEE.value,
        created_by=1,
    )
    db.add(facture)
    await db.flush()

    clinic_info = {
        "clinic_name": "AutoCommerce Clinic",
        "address": "123 Rue de la Santé, Tunis",
        "phone": "+216 71 123 456",
    }
    
    result = await generate_invoice_pdf(facture, patient, clinic_info)
    assert result is not None
    assert isinstance(result, bytes)


@pytest.mark.asyncio
async def test_generate_invoice_pdf_multiple_actes(db):
    """Génère un PDF de facture avec plusieurs actes."""
    patient = Patient(
        clinic_id=1,
        nom="Dupont",
        prenom="Jean",
        telephone="+216123",
        email="jean@example.com",
    )
    db.add(patient)
    await db.flush()

    facture = Facture(
        clinic_id=1,
        patient_id=patient.id,
        numero_facture="F-2026-0003",
        date_emission=date.today(),
        actes=[
            {"nom": "Botox", "prix": "250.000"},
            {"nom": "Acide Hyaluronique", "prix": "300.000"},
        ],
        produits=[
            {"nom": "Produit X", "prix": "50.000", "quantite": 2},
        ],
        sous_total=Decimal("650.000"),
        montant_tva=Decimal("123.500"),
        remise_globale_pct=Decimal("0.00"),
        taux_tva=Decimal("0.190"),
        total_ttc=Decimal("773.500"),
        statut=StatutFacture.PAYEE.value,
        created_by=1,
    )
    db.add(facture)
    await db.flush()

    clinic_info = {
        "clinic_name": "AutoCommerce Clinic",
        "address": "123 Rue de la Santé, Tunis",
        "phone": "+216 71 123 456",
    }
    
    result = await generate_invoice_pdf(facture, patient, clinic_info)
    assert result is not None
    assert isinstance(result, bytes)


@pytest.mark.asyncio
async def test_generate_invoice_pdf_draft(db):
    """Génère un PDF de devis (brouillon)."""
    patient = Patient(
        clinic_id=1,
        nom="Dupont",
        prenom="Jean",
        telephone="+216123",
        email="jean@example.com",
    )
    db.add(patient)
    await db.flush()

    facture = Facture(
        clinic_id=1,
        patient_id=patient.id,
        numero_facture="D-2026-0001",
        date_emission=date.today(),
        actes=[{"nom": "Botox", "prix": "250.000"}],
        produits=[],
        sous_total=Decimal("250.000"),
        montant_tva=Decimal("47.500"),
        remise_globale_pct=Decimal("0.00"),
        taux_tva=Decimal("0.190"),
        total_ttc=Decimal("297.500"),
        statut=StatutFacture.BROUILLON.value,
        created_by=1,
    )
    db.add(facture)
    await db.flush()

    clinic_info = {
        "clinic_name": "AutoCommerce Clinic",
        "address": "123 Rue de la Santé, Tunis",
        "phone": "+216 71 123 456",
    }
    
    result = await generate_invoice_pdf(facture, patient, clinic_info)
    assert result is not None
    assert isinstance(result, bytes)


@pytest.mark.asyncio
async def test_generate_invoice_pdf_with_notes(db):
    """Génère un PDF de facture avec notes."""
    patient = Patient(
        clinic_id=1,
        nom="Dupont",
        prenom="Jean",
        telephone="+216123",
        email="jean@example.com",
        adresse="123 Avenue Principale, Tunis",
    )
    db.add(patient)
    await db.flush()

    facture = Facture(
        clinic_id=1,
        patient_id=patient.id,
        numero_facture="F-2026-0004",
        date_emission=date.today(),
        actes=[{"nom": "Botox", "prix": "250.000"}],
        produits=[],
        sous_total=Decimal("250.000"),
        montant_tva=Decimal("47.500"),
        remise_globale_pct=Decimal("0.00"),
        taux_tva=Decimal("0.190"),
        total_ttc=Decimal("297.500"),
        statut=StatutFacture.PAYEE.value,
        notes="Merci pour votre confiance ! Paiement reçu le 26/07/2026.",
        created_by=1,
    )
    db.add(facture)
    await db.flush()

    clinic_info = {
        "clinic_name": "AutoCommerce Clinic",
        "address": "123 Rue de la Santé, Tunis",
        "phone": "+216 71 123 456",
    }
    
    result = await generate_invoice_pdf(facture, patient, clinic_info)
    assert result is not None
    assert isinstance(result, bytes)


@pytest.mark.asyncio
async def test_generate_invoice_pdf_with_due_date(db):
    """Génère un PDF de facture avec date d'échéance."""
    patient = Patient(
        clinic_id=1,
        nom="Dupont",
        prenom="Jean",
        telephone="+216123",
        email="jean@example.com",
    )
    db.add(patient)
    await db.flush()

    facture = Facture(
        clinic_id=1,
        patient_id=patient.id,
        numero_facture="F-2026-0005",
        date_emission=date.today(),
        date_echeance=date.today() + timedelta(days=30),
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

    clinic_info = {
        "clinic_name": "AutoCommerce Clinic",
        "address": "123 Rue de la Santé, Tunis",
        "phone": "+216 71 123 456",
    }
    
    result = await generate_invoice_pdf(facture, patient, clinic_info)
    assert result is not None
    assert isinstance(result, bytes)


@pytest.mark.asyncio
async def test_generate_invoice_pdf_high_tva(db):
    """Génère un PDF de facture avec TVA élevée."""
    patient = Patient(
        clinic_id=1,
        nom="Dupont",
        prenom="Jean",
        telephone="+216123",
        email="jean@example.com",
    )
    db.add(patient)
    await db.flush()

    facture = Facture(
        clinic_id=1,
        patient_id=patient.id,
        numero_facture="F-2026-0006",
        date_emission=date.today(),
        actes=[{"nom": "Service Premium", "prix": "1000.000"}],
        produits=[],
        sous_total=Decimal("1000.000"),
        montant_tva=Decimal("330.000"),
        remise_globale_pct=Decimal("0.00"),
        taux_tva=Decimal("0.330"),
        total_ttc=Decimal("1330.000"),
        statut=StatutFacture.PAYEE.value,
        created_by=1,
    )
    db.add(facture)
    await db.flush()

    clinic_info = {
        "clinic_name": "AutoCommerce Clinic",
        "address": "123 Rue de la Santé, Tunis",
        "phone": "+216 71 123 456",
    }
    
    result = await generate_invoice_pdf(facture, patient, clinic_info)
    assert result is not None
    assert isinstance(result, bytes)
