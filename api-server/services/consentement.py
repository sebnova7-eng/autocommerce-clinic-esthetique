"""
AutoCommerce Clinic — Gestion des consentements
Signature tactile, PDF archivé, validité 12 mois
"""

import io
from datetime import datetime, timedelta
from typing import Optional

ALLOWED_CONSENT_TYPES = {"general", "acte_medical", "simulation_ia"}

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from models.database import Consentement, Patient, ActeMedical
from config import get_settings
from services.clinic_settings import _resolve_clinic_id
from services.branding import get_branding_context

settings = get_settings()


async def verify_consent(
    patient_id: int,
    acte_id: Optional[int],
    db: AsyncSession,
    type_consentement: Optional[str] = None,
    clinic_id: Optional[int] = None,
) -> bool | Consentement:
    """Vérifie si un consentement valide existe pour ce patient et cet acte/type.

    Contrat historique conservé pour les tests/services existants :
    - sans ``type_consentement`` explicite, retourne un booléen ;
    - avec ``type_consentement`` explicite, retourne l'objet Consentement
      correspondant (ou ``False`` si absent) pour les services qui ont besoin
      de son ``id``.
    """
    clinic_id = _resolve_clinic_id(clinic_id)
    limit_date = datetime.utcnow() - timedelta(days=365)  # 12 mois

    query = select(Consentement).where(
        and_(
            Consentement.patient_id == patient_id,
            Consentement.clinic_id == clinic_id,
            Consentement.est_valide,
            Consentement.signe_le >= limit_date,
        )
    )

    if type_consentement:
        query = query.where(Consentement.type_consentement == type_consentement)
    elif acte_id is not None:
        query = query.where(Consentement.acte_id == acte_id)
    else:
        query = query.where(Consentement.type_consentement == "general")

    result = await db.execute(query.limit(1))
    consentement = result.scalar_one_or_none()

    if type_consentement:
        return consentement or False
    return consentement is not None


async def sign_consent(
    patient_id: int,
    acte_id: Optional[int],
    signature_b64: str,
    method: str,
    ip_address: Optional[str],
    db: AsyncSession,
    type_consentement: Optional[str] = None,
    clinic_id: Optional[int] = None,
) -> Consentement:
    """Signe un consentement.

    Sauvegarde signature base64.
    Génère PDF consentement signé.
    Marque est_valide=True.
    """
    clinic_id = _resolve_clinic_id(clinic_id)

    # Récupérer infos
    patient_result = await db.execute(select(Patient).where(
        Patient.id == patient_id, Patient.clinic_id == clinic_id
    ))
    patient = patient_result.scalar_one_or_none()
    if not patient:
        raise ValueError("Patient non trouvé")

    acte = None
    if acte_id:
        acte_result = await db.execute(select(ActeMedical).where(
            ActeMedical.id == acte_id, ActeMedical.clinic_id == clinic_id
        ))
        acte = acte_result.scalar_one_or_none()
        if not acte:
            raise ValueError("Acte médical non trouvé")

    consent_type = type_consentement or ("acte_medical" if acte else "general")
    if consent_type not in ALLOWED_CONSENT_TYPES:
        raise ValueError("Type de consentement invalide")
    if consent_type == "acte_medical" and not acte_id:
        raise ValueError("Un consentement acte_medical requiert un acte_id")

    # Contenu du consentement
    contenu = _generate_consent_content(patient, acte, consent_type)

    consentement = Consentement(
        clinic_id=clinic_id,
        patient_id=patient_id,
        acte_id=acte_id,
        type_consentement=consent_type,
        contenu_signe=contenu,
        signe_le=datetime.utcnow(),
        methode_signature=method,
        signature_base64=signature_b64,
        ip_address=ip_address,
        est_valide=True,
    )
    db.add(consentement)
    await db.flush()

    # Générer PDF
    branding = await get_branding_context(db, clinic_id=clinic_id)
    pdf_bytes = _generate_consent_pdf(consentement, patient, acte, branding["clinic_name"])

    # Sauvegarder PDF
    import os
    pdf_path = f"{settings.data_dir}/uploads/consentement_{consentement.id}.pdf"
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    # Mettre à jour patient
    if not patient.consentement_rgpd_signe_le:
        patient.consentement_rgpd_signe_le = datetime.utcnow()

    return consentement


def _generate_consent_content(
    patient: Patient,
    acte: Optional[ActeMedical],
    consent_type: str,
) -> str:
    """Génère le texte du consentement."""
    if consent_type == "simulation_ia":
        return f"""CONSENTEMENT SPÉCIFIQUE — SIMULATION IA

Je soussigné(e) {patient.prenom} {patient.nom}, né(e) le {patient.date_naissance or 'N/A'},
accepte la génération d'une simulation visuelle par intelligence artificielle à partir
de mes photographies médicales.

Je reconnais que cette simulation est non contractuelle, purement illustrative et ne
constitue ni une promesse de résultat ni un acte médical.

J'ai été informé(e) des finalités de traitement, des limites techniques du rendu et de
mes droits relatifs à mes données de santé et à mes images.

Date : {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}
"""

    acte_nom = acte.nom if acte else "les actes médicaux esthétiques"

    return f"""CONSENTEMENT ÉCLAIRÉ

Je soussigné(e) {patient.prenom} {patient.nom}, né(e) le {patient.date_naissance or 'N/A'},
déclare avoir été informé(e) par le praticien des risques, bénéfices et alternatives
concernant {acte_nom}.

J'ai eu l'occasion de poser toutes les questions nécessaires et j'ai reçu des réponses
satisfaisantes.

Je consens librement et en pleine connaissance de cause à recevoir {acte_nom}.

Date : {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}
"""


def _generate_consent_pdf(
    consentement: Consentement,
    patient: Patient,
    acte: Optional[ActeMedical],
    clinic_name: str,
) -> bytes:
    """Génère le PDF du consentement signé."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # En-tête
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, 27*cm, "CONSENTEMENT ÉCLAIRÉ")
    c.line(2*cm, 26.5*cm, 19*cm, 26.5*cm)

    # Contenu
    c.setFont("Helvetica", 11)
    y = 25*cm
    lines = consentement.contenu_signe.split("\n")
    for line in lines:
        c.drawString(2*cm, y, line)
        y -= 0.6*cm

    # Signature
    y -= 1*cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2*cm, y, "Signature :")

    # Décoder et afficher la signature base64
    try:
        import base64
        sig_data = base64.b64decode(consentement.signature_base64.split(",")[-1])
        sig_img = io.BytesIO(sig_data)
        c.drawImage(sig_img, 2*cm, y - 4*cm, width=8*cm, height=3*cm, preserveAspectRatio=True)
    except Exception:
        c.setFont("Helvetica", 10)
        c.drawString(2*cm, y - 1*cm, "[Signature numérique enregistrée]")

    # Footer
    c.setFont("Helvetica", 8)
    c.drawString(2*cm, 1.5*cm, f"Document généré le {consentement.signe_le.strftime('%d/%m/%Y %H:%M')} — ID: {consentement.id}")
    c.drawString(2*cm, 1*cm, f"{clinic_name} — Document confidentiel")

    c.save()
    buf.seek(0)
    return buf.getvalue()
