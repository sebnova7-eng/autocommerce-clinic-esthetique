"""
AutoCommerce Clinic — Dossier médical chiffré
Chiffrement Fernet, timeline, export PDF
"""

import io
from datetime import datetime
from typing import List, Optional

from cryptography.fernet import Fernet
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import get_settings
from models.database import (
    DossierMedical, Patient, Utilisateur, ActeMedical,
    PhotoClinic, Consentement, UtilisationLot, LotInjectable,
    ProduitInjectable,
)
from services.consentement import verify_consent
from services.audit_medical import log_access
from services.branding import get_branding_context

settings = get_settings()


def _resolve_clinic(clinic_id: int | None) -> int:
    if clinic_id and clinic_id > 0:
        return int(clinic_id)
    if settings.env in {"test", "development"}:
        return int(settings.clinic_id or 1)
    if settings.is_internal_single_clinic and settings.clinic_id:
        return int(settings.clinic_id)
    raise ValueError("Contexte clinique obligatoire")


def get_fernet() -> Fernet:
    """Retourne une instance Fernet pour le chiffrement."""
    if not settings.fernet_key:
        raise ValueError("FERNET_KEY non configurée")
    return Fernet(settings.fernet_key.encode())


def encrypt_field(plaintext: str) -> str:
    """Chiffre un champ texte avec Fernet."""
    if not plaintext:
        return ""
    f = get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_field(ciphertext: str) -> str:
    """Déchiffre un champ texte avec Fernet."""
    if not ciphertext:
        return ""
    f = get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


async def create_dossier(
    patient_id: int,
    praticien_id: int,
    rdv_id: Optional[int],
    data: dict,
    db: AsyncSession,
    clinic_id: int | None = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> DossierMedical:
    """Crée un dossier médical.

    Vérifie consentement signé valide avant création.
    Chiffre les observations.
    Crée log audit.
    """
    clinic_id = _resolve_clinic(clinic_id)
    # Vérifier consentement dans la même clinique.
    acte_id = data.get("acte_id")
    has_consent = await verify_consent(patient_id, acte_id, db, clinic_id=clinic_id)
    if not has_consent:
        raise ValueError("Consentement non signé ou expiré pour cet acte")

    # Chiffrer observations
    observations = data.get("observations", "")
    observations_enc = encrypt_field(observations) if observations else None

    dossier = DossierMedical(
        clinic_id=clinic_id,
        patient_id=patient_id,
        praticien_id=praticien_id,
        rdv_id=rdv_id,
        acte_id=acte_id,
        date_acte=data.get("date_acte", datetime.utcnow()),
        zones_traitees=data.get("zones_traitees"),
        produits_utilises=data.get("produits_utilises"),
        observations_enc=observations_enc,
        effets_secondaires=data.get("effets_secondaires"),
        satisfaction_patient=data.get("satisfaction_patient"),
        suivi_requis=data.get("suivi_requis", False),
        date_suivi_recommandee=data.get("date_suivi_recommandee"),
        actes_details=data.get("actes_details", []),
        statut_facturation="en_attente",
    )
    db.add(dossier)
    await db.flush()

    # Log audit
    await log_access(
        db=db,
        utilisateur_id=praticien_id,
        patient_id=patient_id,
        action="CREATE_DOSSIER",
        resource_type="dossier",
        resource_id=dossier.id,
        ip_address=ip_address,
        user_agent=user_agent,
        clinic_id=clinic_id,
        details={"acte_id": acte_id, "rdv_id": rdv_id},
    )

    return dossier


async def get_timeline_patient(
    patient_id: int,
    db: AsyncSession,
    utilisateur_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_role: Optional[str] = None,
    clinic_id: int | None = None
) -> List[dict]:
    """Timeline chronologique de tous les dossiers avec photos et produits."""
    clinic_id = _resolve_clinic(clinic_id)
    if utilisateur_id:
        await log_access(
            db=db, utilisateur_id=utilisateur_id, patient_id=patient_id,
            action="READ_TIMELINE", resource_type="dossier_timeline", resource_id=patient_id,
            ip_address=ip_address,
            clinic_id=clinic_id,
        )

    result = await db.execute(
        select(DossierMedical, ActeMedical, Utilisateur)
        .join(ActeMedical, DossierMedical.acte_id == ActeMedical.id, isouter=True)
        .join(Utilisateur, DossierMedical.praticien_id == Utilisateur.id)
        .where(DossierMedical.patient_id == patient_id)
        .where(DossierMedical.clinic_id == clinic_id)
        .order_by(DossierMedical.date_acte.desc())
    )

    timeline = []
    for dossier, acte, praticien in result.all():
        # Photos associées
        photos_result = await db.execute(
            select(PhotoClinic)
            .where(PhotoClinic.dossier_id == dossier.id)
            .where(not PhotoClinic.is_deleted)
        )
        photos = [
            {"id": p.id, "type": p.type, "zone": p.zone_anatomique, "url": p.url_thumbnail}
            for p in photos_result.scalars().all()
        ]

        # Produits injectés (traçabilité)
        utilisations_result = await db.execute(
            select(UtilisationLot, LotInjectable, ProduitInjectable)
            .join(LotInjectable, UtilisationLot.lot_id == LotInjectable.id)
            .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
            .where(UtilisationLot.dossier_id == dossier.id)
        )
        produits = [
            {
                "produit": p.nom,
                "lot": lot.numero_lot,
                "quantite": float(u.quantite_utilisee),
                "unite": u.unite,
            }
            for u, lot, p in utilisations_result.all()
        ]

        # Déchiffrer observations (SAUF pour DIRECTRICE)
        if user_role == "directrice":
            observations = "[ACCÈS MÉDICAL RÉSERVÉ]"
        else:
            observations = decrypt_field(dossier.observations_enc) if dossier.observations_enc else ""

        timeline.append({
            "dossier_id": dossier.id,
            "date": dossier.date_acte.isoformat(),
            "acte": acte.nom if acte else "Non spécifié",
            "praticien": f"{praticien.prenom} {praticien.nom}",
            "observations": observations,
            "zones_traitees": dossier.zones_traitees,
            "produits_utilises": produits,
            "effets_secondaires": dossier.effets_secondaires if user_role != "directrice" else "[ACCÈS RÉSERVÉ]",
            "satisfaction": dossier.satisfaction_patient,
            "photos": photos if user_role != "directrice" else [],
        })

    return timeline


async def export_dossier_pdf(
    patient_id: int,
    db: AsyncSession,
    user_role: Optional[str] = None,
    clinic_id: int | None = None
) -> bytes:
    """Génère un PDF complet du dossier patient.

    Inclut :
    - Infos patient (déchiffrées)
    - Timeline actes
    - Produits injectés avec lots
    - Miniatures photos (si visible_patient=True)
    - Consentements signés
    """
    clinic_id = _resolve_clinic(clinic_id)
    # Récupérer patient
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id).where(Patient.clinic_id == clinic_id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise ValueError("Patient non trouvé")

    # Créer PDF
    branding = await get_branding_context(db, clinic_id=clinic_id)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    # Titre
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor(branding["primary_color"]),
        spaceAfter=20,
    )
    story.append(Paragraph(f"{branding['clinic_name']} — Dossier Médical — {patient.prenom} {patient.nom}", title_style))
    story.append(Spacer(1, 0.3*cm))

    # Infos patient
    story.append(Paragraph("<b>Informations patient</b>", styles["Heading2"]))
    
    # Masquage des données sensibles pour DIRECTRICE
    if user_role == "directrice":
        allergies = "[ACCÈS RÉSERVÉ]"
        antecedents = "[ACCÈS RÉSERVÉ]"
    else:
        allergies = decrypt_field(patient.allergies_enc) if patient.allergies_enc else "N/A"
        antecedents = decrypt_field(patient.antecedents_medicaux_enc) if patient.antecedents_medicaux_enc else "N/A"

    info_data = [
        ["Nom", f"{patient.prenom} {patient.nom}"],
        ["Date de naissance", str(patient.date_naissance) if patient.date_naissance else "N/A"],
        ["Téléphone", patient.telephone],
        ["Email", patient.email or "N/A"],
        ["Allergies", allergies],
        ["Antécédents", antecedents],
    ]
    info_table = Table(info_data, colWidths=[4*cm, 12*cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.5*cm))

    # Timeline
    story.append(Paragraph("<b>Historique des actes</b>", styles["Heading2"]))
    timeline = await get_timeline_patient(patient_id, db, user_role=user_role, clinic_id=clinic_id)

    for entry in timeline:
        story.append(Paragraph(f"<b>{entry['date'][:10]}</b> — {entry['acte']}", styles["Heading3"]))
        story.append(Paragraph(f"Praticien : {entry['praticien']}", styles["Normal"]))
        if entry['observations']:
            story.append(Paragraph(f"Observations : {entry['observations']}", styles["Normal"]))
        if entry['produits_utilises']:
            produits_text = ", ".join([
                f"{p['produit']} ({p['quantite']} {p['unite']}) — Lot {p['lot']}"
                for p in entry['produits_utilises']
            ])
            story.append(Paragraph(f"Produits : {produits_text}", styles["Normal"]))
        story.append(Spacer(1, 0.2*cm))

    # Consentements
    consent_result = await db.execute(
        select(Consentement)
        .where(Consentement.patient_id == patient_id)
        .where(Consentement.est_valide)
        .order_by(Consentement.signe_le.desc())
    )
    consentements = consent_result.scalars().all()

    if consentements:
        story.append(Paragraph("<b>Consentements signés</b>", styles["Heading2"]))
        for c in consentements:
            story.append(Paragraph(
                f"{c.type_consentement} — signé le {c.signe_le.strftime('%d/%m/%Y')} via {c.methode_signature}",
                styles["Normal"]
            ))

    # Footer RGPD
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(
        f"<i>{branding['clinic_name']} — Ce document est confidentiel et protégé par le secret médical. "
        "Conformément au RGPD, vous disposez d'un droit d'accès, de rectification et de suppression de vos données.</i>",
        styles["Italic"]
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
