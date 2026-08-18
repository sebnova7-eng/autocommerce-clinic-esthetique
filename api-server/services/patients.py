"""
AutoCommerce Clinic — Service Patients

Gère le chiffrement des champs sensibles (allergies, antécédents,
contre-indications, notes internes — mêmes garanties que
dossier_medical.py), le scoping "un commercial ne voit que ses
patientes", et l'anonymisation RGPD (droit à l'oubli).
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Patient
from services.dossier_medical import encrypt_field, decrypt_field
from services.access_control import clinic_id_for, ensure_patient_ownership

ENCRYPTED_FIELDS = ["allergies", "antecedents_medicaux", "contre_indications", "note_interne"]


def _apply_encrypted_input(patient: Patient, data: dict) -> None:
    for field in ENCRYPTED_FIELDS:
        if field in data and data[field] is not None:
            setattr(patient, f"{field}_enc", encrypt_field(data[field]))


def _serialize(patient: Patient, include_sensitive: bool = True, include_antecedents: bool = True) -> dict:
    out = {
        "id": patient.id,
        "nom": patient.nom,
        "prenom": patient.prenom,
        "date_naissance": patient.date_naissance,
        "genre": patient.genre,
        "telephone": patient.telephone,
        "email": patient.email,
        "adresse": patient.adresse,
        "ville": patient.ville,
        "groupe_sanguin": patient.groupe_sanguin,
        "statut": patient.statut,
        "is_active": patient.is_active,
        "points_fidelite": patient.points_fidelite,
        "niveau_fidelite": patient.niveau_fidelite,
        "derniere_visite": patient.derniere_visite,
        "commercial_id": patient.commercial_id,
        "consentement_marketing": patient.consentement_marketing,
        "anonymized_at": patient.anonymized_at,
        "date_inscription": patient.created_at,
    }
    if include_sensitive:
        # Allergies et contre-indications restent visibles pour l'esthéticienne
        # (nécessaires pour la sécurité de l'acte) — voir clinic_rbac.py.
        out.update({
            "allergies": decrypt_field(patient.allergies_enc) if patient.allergies_enc else None,
            "contre_indications": decrypt_field(patient.contre_indications_enc) if patient.contre_indications_enc else None,
        })
        if include_antecedents:
            # PAS antécédents pour l'esthéticienne (matrice RBAC,
            # middleware/clinic_rbac.py) : cette clé est absente de la
            # réponse plutôt que masquée, pour ne pas juste la cacher côté
            # frontend en laissant la donnée transiter par le réseau.
            out.update({
                "antecedents_medicaux": decrypt_field(patient.antecedents_medicaux_enc) if patient.antecedents_medicaux_enc else None,
                "note_interne": decrypt_field(patient.note_interne_enc) if patient.note_interne_enc else None,
            })
    return out


async def create_patient(data: dict, db: AsyncSession, current_user: Optional[dict] = None) -> dict:
    clinic_id = clinic_id_for(current_user)
    existing = await db.execute(select(Patient).where(
        Patient.telephone == data["telephone"], Patient.clinic_id == clinic_id
    ))
    if existing.scalar_one_or_none():
        raise ValueError("Un patient avec ce numéro de téléphone existe déjà")

    patient = Patient(
        clinic_id=clinic_id,
        nom=data["nom"], prenom=data["prenom"],
        date_naissance=data.get("date_naissance"),
        genre=data.get("genre"), telephone=data["telephone"],
        email=data.get("email"), adresse=data.get("adresse"), ville=data.get("ville"),
        groupe_sanguin=data.get("groupe_sanguin"),
        source_acquisition=data.get("source_acquisition"),
        commercial_id=data.get("commercial_id"),
        whatsapp_phone=data.get("whatsapp_phone") or data["telephone"],
        consentement_marketing=data.get("consentement_marketing", False),
    )
    _apply_encrypted_input(patient, data)
    db.add(patient)
    await db.flush()
    role = (current_user or {}).get("role")
    include_sensitive = role not in ("commercial", "assistante", "directrice")
    include_antecedents = role not in ("commercial", "assistante", "estheticienne", "directrice")
    return _serialize(patient, include_sensitive=include_sensitive, include_antecedents=include_antecedents)


async def get_patient(patient_id: int, current_user: dict, db: AsyncSession) -> dict:
    result = await db.execute(select(Patient).where(
        Patient.id == patient_id, Patient.clinic_id == clinic_id_for(current_user)
    ))
    patient = result.scalar_one_or_none()
    if not patient:
        raise ValueError("Patient non trouvé")
    ensure_patient_ownership(patient, current_user)

    role = current_user.get("role")
    include_sensitive = role not in ("commercial", "assistante", "directrice")
    include_antecedents = role not in ("commercial", "assistante", "estheticienne", "directrice")
    return _serialize(patient, include_sensitive=include_sensitive, include_antecedents=include_antecedents)


async def list_patients(current_user: dict, db: AsyncSession, search: Optional[str] = None,
                         skip: int = 0, limit: int = 50) -> list[dict]:
    query = select(Patient).where(
        Patient.anonymized_at.is_(None), Patient.clinic_id == clinic_id_for(current_user)
    )

    if current_user.get("role") == "commercial":
        query = query.where(Patient.commercial_id == current_user.get("id"))

    if search:
        like = f"%{search}%"
        query = query.where(or_(Patient.nom.ilike(like), Patient.prenom.ilike(like), Patient.telephone.ilike(like)))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    patients = result.scalars().all()

    role = current_user.get("role")
    include_sensitive = role not in ("commercial", "assistante", "directrice")
    include_antecedents = role not in ("commercial", "assistante", "estheticienne", "directrice")
    return [_serialize(p, include_sensitive=include_sensitive, include_antecedents=include_antecedents) for p in patients]


async def update_patient(patient_id: int, data: dict, current_user: dict, db: AsyncSession) -> dict:
    result = await db.execute(select(Patient).where(
        Patient.id == patient_id, Patient.clinic_id == clinic_id_for(current_user)
    ))
    patient = result.scalar_one_or_none()
    if not patient:
        raise ValueError("Patient non trouvé")
    ensure_patient_ownership(patient, current_user)

    for field in ("nom", "prenom", "date_naissance", "genre", "email", "adresse",
                  "ville", "groupe_sanguin", "statut", "consentement_marketing"):
        if field in data and data[field] is not None:
            setattr(patient, field, data[field])

    _apply_encrypted_input(patient, data)
    await db.flush()
    role = current_user.get("role")
    include_sensitive = role not in ("commercial", "assistante", "directrice")
    include_antecedents = role not in ("commercial", "assistante", "estheticienne", "directrice")
    return _serialize(patient, include_sensitive=include_sensitive, include_antecedents=include_antecedents)


async def anonymize_patient(patient_id: int, db: AsyncSession, current_user: Optional[dict] = None) -> dict:
    """Droit à l'oubli RGPD avec contrôle de clinique et d'ownership."""
    current_user = current_user or {"role": "admin", "id": None, "clinic_id": 1}
    result = await db.execute(select(Patient).where(
        Patient.id == patient_id, Patient.clinic_id == clinic_id_for(current_user)
    ))
    patient = result.scalar_one_or_none()
    if not patient:
        raise ValueError("Patient non trouvé")
    ensure_patient_ownership(patient, current_user)

    patient.nom = "Anonymisé"
    patient.prenom = f"Patient #{patient.id}"
    patient.email = None
    patient.adresse = None
    patient.telephone = f"anonymise-{patient.id}"
    patient.whatsapp_phone = None
    patient.allergies_enc = None
    patient.antecedents_medicaux_enc = None
    patient.contre_indications_enc = None
    patient.note_interne_enc = None
    patient.is_active = False
    patient.consentement_marketing = False
    patient.anonymized_at = datetime.utcnow()

    await db.flush()
    return _serialize(patient)
