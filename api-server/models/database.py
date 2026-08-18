"""
AutoCommerce Clinic — Modèles SQLAlchemy 2.0
Style modern mapped_column. Tous les montants en Numeric(10,3).
Données médicales chiffrées suffixe _enc.
Clinic_id=1 partout (préparation multi-clinique).
"""

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


# ═══════════════════════════════════════════════════════════
# Base & Engine
# ═══════════════════════════════════════════════════════════

class Base(DeclarativeBase):
    pass


# ═══════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════

class RoleEnum(str, enum.Enum):
    DIRECTRICE = "directrice"
    MEDECIN = "medecin"
    ESTHETICIENNE = "estheticienne"
    ASSISTANTE = "assistante"
    COMMERCIAL = "commercial"
    ADMIN = "admin"


class StatutRDV(str, enum.Enum):
    PLANIFIE = "planifie"
    CONFIRME = "confirme"
    EN_COURS = "en_cours"
    TERMINE = "termine"
    ANNULE = "annule"
    NO_SHOW = "no_show"


class TypePhoto(str, enum.Enum):
    AVANT = "avant"
    APRES = "apres"
    PROGRESSION = "progression"
    COMPLICATION = "complication"
    AUTRE = "autre"


class StatutLot(str, enum.Enum):
    DISPONIBLE = "disponible"
    QUARANTAINE = "quarantaine"
    EPUISE = "epuise"
    EXPIRE = "expire"
    RETIRE = "retire"


class StatutFacture(str, enum.Enum):
    BROUILLON = "brouillon"
    ENVOYEE = "envoyee"
    PAYEE = "payee"
    PARTIELLEMENT_PAYEE = "partiellement_payee"
    ANNULEE = "annulee"


class StatutCommission(str, enum.Enum):
    EN_ATTENTE = "en_attente"
    VALIDATION_PARTIELLE = "validation_partielle"  # >500 DT, 1 seul validateur pour l'instant
    VALIDEE = "validee"
    PAYEE = "payee"


class NiveauFidelite(str, enum.Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    VIP = "vip"


class StatutDepense(str, enum.Enum):
    EN_ATTENTE = "en_attente"
    TRAITEE_IA = "traitee_ia"
    VALIDEE = "validee"
    REJETEE = "rejetee"


class StatutCandidature(str, enum.Enum):
    RECU = "recu"
    EN_ETUDE = "en_etude"
    ENTRETIEN = "entretien"
    ACCEPTE = "accepte"
    REFUSE = "refuse"


# ═══════════════════════════════════════════════════════════
# MODÈLES (dans l'ordre des dépendances FK)
# ═══════════════════════════════════════════════════════════

class Utilisateur(Base):
    __tablename__ = "utilisateurs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    prenom: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(String(20), nullable=False)
    telephone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    photo_profil_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    taux_commission: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))
    agenda_color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    specialite: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # ── MFA / 2FA ───────────────────────────────────────────
    mfa_secret: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_backup_codes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON de codes hachés
    mfa_setup_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    mfa_failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    mfa_locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_utilisateurs_clinic_email", "clinic_id", "email"),
    )

    # Relations
    patients_commercial: Mapped[List["Patient"]] = relationship(
        "Patient", foreign_keys="Patient.commercial_id", back_populates="commercial"
    )
    rdvs_praticien: Mapped[List["RendezVous"]] = relationship(
        "RendezVous", foreign_keys="RendezVous.praticien_id", back_populates="praticien"
    )
    rdvs_created: Mapped[List["RendezVous"]] = relationship(
        "RendezVous", foreign_keys="RendezVous.created_by", back_populates="createur"
    )
    dossiers_praticien: Mapped[List["DossierMedical"]] = relationship(
        "DossierMedical", foreign_keys="DossierMedical.praticien_id", back_populates="praticien"
    )
    commissions: Mapped[List["Commission"]] = relationship(
        "Commission", foreign_keys="Commission.commercial_id", back_populates="commercial"
    )
    commissions_validees: Mapped[List["Commission"]] = relationship(
        "Commission", foreign_keys="Commission.validee_par_id", back_populates="validateur"
    )
    photos_prise_par: Mapped[List["PhotoClinic"]] = relationship(
        "PhotoClinic", foreign_keys="PhotoClinic.prise_par_id", back_populates="prise_par"
    )
    utilisations_lot: Mapped[List["UtilisationLot"]] = relationship(
        "UtilisationLot", foreign_keys="UtilisationLot.praticien_id", back_populates="praticien"
    )
    mouvements_consommables: Mapped[List["MouvementConsommable"]] = relationship(
        "MouvementConsommable", back_populates="utilisateur"
    )
    factures_created: Mapped[List["Facture"]] = relationship(
        "Facture", foreign_keys="Facture.created_by", back_populates="createur"
    )
    depenses_validees: Mapped[List["Depense"]] = relationship(
        "Depense", foreign_keys="Depense.valide_par_id", back_populates="validateur"
    )
    depenses_created: Mapped[List["Depense"]] = relationship(
        "Depense", foreign_keys="Depense.created_by", back_populates="createur_depense"
    )
    candidatures_evaluees: Mapped[List["Candidature"]] = relationship(
        "Candidature", foreign_keys="Candidature.evaluateur_id", back_populates="evaluateur"
    )
    campagnes_created: Mapped[List["CampagneMarketing"]] = relationship(
        "CampagneMarketing", foreign_keys="CampagneMarketing.created_by", back_populates="createur_campagne"
    )


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    nom: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    prenom: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    date_naissance: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    genre: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    telephone: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    adresse: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    ville: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    groupe_sanguin: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    allergies_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    antecedents_medicaux_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contre_indications_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    note_interne_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_profil_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_acquisition: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    commercial_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    statut: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    whatsapp_phone: Mapped[Optional[str]] = mapped_column(String(20), index=True, nullable=True)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    points_fidelite: Mapped[int] = mapped_column(Integer, default=0)
    niveau_fidelite: Mapped[NiveauFidelite] = mapped_column(
        String(10), default=NiveauFidelite.BRONZE.value
    )
    derniere_visite: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    consentement_rgpd_signe_le: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    consentement_marketing: Mapped[bool] = mapped_column(Boolean, default=False)
    anonymized_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_patients_clinic_nom", "clinic_id", "nom"),
        Index("ix_patients_clinic_telephone", "clinic_id", "telephone"),
        Index("ix_patients_clinic_niveau", "clinic_id", "niveau_fidelite"),
    )

    # Relations
    commercial: Mapped[Optional["Utilisateur"]] = relationship(
        "Utilisateur", foreign_keys=[commercial_id], back_populates="patients_commercial"
    )
    rdvs: Mapped[List["RendezVous"]] = relationship("RendezVous", back_populates="patient")
    dossiers: Mapped[List["DossierMedical"]] = relationship("DossierMedical", back_populates="patient")
    series_photos: Mapped[List["SeriePhotos"]] = relationship("SeriePhotos", back_populates="patient")
    photos: Mapped[List["PhotoClinic"]] = relationship("PhotoClinic", back_populates="patient")
    consentements: Mapped[List["Consentement"]] = relationship("Consentement", back_populates="patient")
    utilisations_lot: Mapped[List["UtilisationLot"]] = relationship("UtilisationLot", back_populates="patient")
    factures: Mapped[List["Facture"]] = relationship("Facture", back_populates="patient")
    commissions: Mapped[List["Commission"]] = relationship("Commission", back_populates="patient")
    fidelite_transactions: Mapped[List["FideliteTransaction"]] = relationship(
        "FideliteTransaction", back_populates="patient"
    )
    parrainages_parrain: Mapped[List["Parrainage"]] = relationship(
        "Parrainage", foreign_keys="Parrainage.parrain_patient_id", back_populates="parrain"
    )
    parrainages_filleul: Mapped[List["Parrainage"]] = relationship(
        "Parrainage", foreign_keys="Parrainage.filleul_patient_id", back_populates="filleul"
    )


class ActeMedical(Base):
    __tablename__ = "actes_medicaux"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    nom: Mapped[str] = mapped_column(String(200), nullable=False)
    categorie: Mapped[str] = mapped_column(String(50), nullable=False)
    duree_minutes: Mapped[int] = mapped_column(Integer, default=30)
    prix_base: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    protocole: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relations
    rdvs: Mapped[List["RendezVous"]] = relationship("RendezVous", back_populates="acte")
    dossiers: Mapped[List["DossierMedical"]] = relationship("DossierMedical", back_populates="acte")
    consentements: Mapped[List["Consentement"]] = relationship("Consentement", back_populates="acte")
    series_photos: Mapped[List["SeriePhotos"]] = relationship("SeriePhotos", back_populates="acte")


class BookingRequest(Base):
    """Demande publique en attente de validation clinique.

    Ce modèle est volontairement distinct de RendezVous : la passerelle publique
    ne crée ni patient clinique ni rendez-vous interne avant une décision d’un
    utilisateur authentifié du Private Clinical Core.
    """

    __tablename__ = "booking_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    prenom: Mapped[str] = mapped_column(String(100), nullable=False)
    telephone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    praticien_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=True
    )
    acte_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("actes_medicaux.id", ondelete="RESTRICT"), nullable=False
    )
    date_heure: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    patient_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True
    )
    rendez_vous_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("rendez_vous.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    review_notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="public_gateway")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_booking_requests_clinic_status", "clinic_id", "statut"),
        UniqueConstraint("clinic_id", "request_fingerprint", name="uq_booking_requests_fingerprint"),
    )


class RendezVous(Base):
    __tablename__ = "rendez_vous"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False
    )
    praticien_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False
    )
    acte_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("actes_medicaux.id", ondelete="SET NULL"), nullable=True
    )
    date_heure_debut: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    date_heure_fin: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    salle: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    statut: Mapped[StatutRDV] = mapped_column(String(20), default=StatutRDV.PLANIFIE.value)
    notes_pre_acte: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes_post_acte: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rappel_j1_envoye: Mapped[bool] = mapped_column(Boolean, default=False)
    rappel_h2_envoye: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_rdv_praticien_date", "praticien_id", "date_heure_debut"),
        Index("ix_rdv_patient_date", "patient_id", "date_heure_debut"),
        Index("ix_rdv_clinic_date", "clinic_id", "date_heure_debut"),
    )

    # Relations
    patient: Mapped["Patient"] = relationship("Patient", back_populates="rdvs")
    praticien: Mapped["Utilisateur"] = relationship(
        "Utilisateur", foreign_keys=[praticien_id], back_populates="rdvs_praticien"
    )
    acte: Mapped[Optional["ActeMedical"]] = relationship("ActeMedical", back_populates="rdvs")
    createur: Mapped[Optional["Utilisateur"]] = relationship(
        "Utilisateur", foreign_keys=[created_by], back_populates="rdvs_created"
    )
    dossier: Mapped[Optional["DossierMedical"]] = relationship("DossierMedical", back_populates="rdv")
    facture: Mapped[Optional["Facture"]] = relationship("Facture", back_populates="rdv")
    teleconsultation: Mapped[Optional["Teleconsultation"]] = relationship("Teleconsultation", back_populates="rdv")


class DossierMedical(Base):
    __tablename__ = "dossiers_medicaux"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    praticien_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False
    )
    rdv_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("rendez_vous.id", ondelete="SET NULL"), nullable=True
    )
    acte_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("actes_medicaux.id", ondelete="SET NULL"), nullable=True
    )
    date_acte: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    zones_traitees: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    produits_utilises: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    observations_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    effets_secondaires: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    satisfaction_patient: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    suivi_requis: Mapped[bool] = mapped_column(Boolean, default=False)
    date_suivi_recommandee: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    statut_facturation: Mapped[str] = mapped_column(String(20), default="en_attente")
    actes_details: Mapped[Optional[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_dossier_patient_date", "patient_id", "date_acte"),
    )

    # Relations
    patient: Mapped["Patient"] = relationship("Patient", back_populates="dossiers")
    praticien: Mapped["Utilisateur"] = relationship(
        "Utilisateur", foreign_keys=[praticien_id], back_populates="dossiers_praticien"
    )
    rdv: Mapped[Optional["RendezVous"]] = relationship("RendezVous", back_populates="dossier")
    acte: Mapped[Optional["ActeMedical"]] = relationship("ActeMedical", back_populates="dossiers")
    photos: Mapped[List["PhotoClinic"]] = relationship("PhotoClinic", back_populates="dossier")
    utilisations_lot: Mapped[List["UtilisationLot"]] = relationship("UtilisationLot", back_populates="dossier")


class SeriePhotos(Base):
    __tablename__ = "series_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    nom_serie: Mapped[str] = mapped_column(String(200), nullable=False)
    zone_anatomique: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    acte_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("actes_medicaux.id", ondelete="SET NULL"), nullable=True
    )
    date_debut: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_fin: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relations
    patient: Mapped["Patient"] = relationship("Patient", back_populates="series_photos")
    acte: Mapped[Optional["ActeMedical"]] = relationship("ActeMedical", back_populates="series_photos")
    photos: Mapped[List["PhotoClinic"]] = relationship("PhotoClinic", back_populates="serie")


class PhotoClinic(Base):
    __tablename__ = "photos_clinic"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    dossier_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("dossiers_medicaux.id", ondelete="SET NULL"), nullable=True
    )
    serie_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("series_photos.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[TypePhoto] = mapped_column(String(20), nullable=False)
    date_prise: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    zone_anatomique: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    angle_prise: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    url_stockage: Mapped[str] = mapped_column(String(500), nullable=False)
    url_thumbnail: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    hash_fichier: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    taille_octets: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    visible_patient: Mapped[bool] = mapped_column(Boolean, default=False)
    visible_marketing: Mapped[bool] = mapped_column(Boolean, default=False)
    filigrane_applique: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prise_par_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    raison_suppression: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_photo_patient_type", "patient_id", "type"),
        Index("ix_photo_patient_zone", "patient_id", "zone_anatomique"),
    )

    # Relations
    patient: Mapped["Patient"] = relationship("Patient", back_populates="photos")
    dossier: Mapped[Optional["DossierMedical"]] = relationship("DossierMedical", back_populates="photos")
    serie: Mapped[Optional["SeriePhotos"]] = relationship("SeriePhotos", back_populates="photos")
    prise_par: Mapped[Optional["Utilisateur"]] = relationship(
        "Utilisateur", foreign_keys=[prise_par_id], back_populates="photos_prise_par"
    )


class Consentement(Base):
    __tablename__ = "consentements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    acte_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("actes_medicaux.id", ondelete="SET NULL"), nullable=True
    )
    type_consentement: Mapped[str] = mapped_column(String(50), nullable=False)
    contenu_signe: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signe_le: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    methode_signature: Mapped[str] = mapped_column(String(50), nullable=False)
    signature_base64: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    est_valide: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relations
    patient: Mapped["Patient"] = relationship("Patient", back_populates="consentements")
    acte: Mapped[Optional["ActeMedical"]] = relationship("ActeMedical", back_populates="consentements")


class ProduitInjectable(Base):
    __tablename__ = "produits_injectables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    nom: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    fabricant: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    categorie: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_fabricant: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    unite: Mapped[str] = mapped_column(String(20), nullable=False)
    prix_achat: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"))
    prix_vente: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"))
    stock_actuel: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    stock_minimum: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    stock_alerte: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    temperature_conservation: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    conditions_stockage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    duree_effet_jours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=90, server_default="90"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relations
    lots: Mapped[List["LotInjectable"]] = relationship("LotInjectable", back_populates="produit")


class LotInjectable(Base):
    __tablename__ = "lots_injectables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    produit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("produits_injectables.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    numero_lot: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    date_fabrication: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_expiration: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    quantite_initiale: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantite_restante: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    fournisseur: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    date_reception: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    prix_achat_lot: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"))
    certificat_conformite_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    qr_code_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    barcode_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    label_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    statut: Mapped[StatutLot] = mapped_column(
        String(20), default=StatutLot.DISPONIBLE.value
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_lot_expiration_statut", "date_expiration", "statut"),
    )

    # Relations
    produit: Mapped["ProduitInjectable"] = relationship("ProduitInjectable", back_populates="lots")
    utilisations: Mapped[List["UtilisationLot"]] = relationship("UtilisationLot", back_populates="lot")
    depenses: Mapped[List["Depense"]] = relationship("Depense", back_populates="lot_injectable")


class UtilisationLot(Base):
    __tablename__ = "utilisations_lot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    lot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lots_injectables.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    dossier_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("dossiers_medicaux.id", ondelete="SET NULL"), nullable=True
    )
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    praticien_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False
    )
    date_utilisation: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    quantite_utilisee: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unite: Mapped[str] = mapped_column(String(20), nullable=False)
    type_injection: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prochaine_injection_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    prochaine_injection_envoyee: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    # Relations
    lot: Mapped["LotInjectable"] = relationship("LotInjectable", back_populates="utilisations")
    dossier: Mapped[Optional["DossierMedical"]] = relationship("DossierMedical", back_populates="utilisations_lot")
    patient: Mapped["Patient"] = relationship("Patient", back_populates="utilisations_lot")
    praticien: Mapped["Utilisateur"] = relationship(
        "Utilisateur", foreign_keys=[praticien_id], back_populates="utilisations_lot"
    )


class Facture(Base):
    __tablename__ = "factures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    rdv_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("rendez_vous.id", ondelete="SET NULL"), nullable=True
    )
    numero_facture: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    date_emission: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    date_echeance: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    actes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    produits: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    sous_total: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"))
    taux_tva: Mapped[Decimal] = mapped_column(Numeric(5, 3), default=Decimal("0.190"))
    montant_tva: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"))
    total_ttc: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"))
    remise_globale_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))
    statut: Mapped[StatutFacture] = mapped_column(
        String(20), default=StatutFacture.BROUILLON.value
    )
    mode_paiement: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_facture_clinic_date", "clinic_id", "date_emission"),
        Index("ix_facture_clinic_statut", "clinic_id", "statut"),
    )

    # Relations
    patient: Mapped["Patient"] = relationship("Patient", back_populates="factures")
    rdv: Mapped[Optional["RendezVous"]] = relationship("RendezVous", back_populates="facture")
    createur: Mapped[Optional["Utilisateur"]] = relationship(
        "Utilisateur", foreign_keys=[created_by], back_populates="factures_created"
    )
    commissions: Mapped[List["Commission"]] = relationship("Commission", back_populates="facture")


class Commission(Base):
    __tablename__ = "commissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    commercial_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False
    )
    facture_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("factures.id", ondelete="RESTRICT"), nullable=False
    )
    montant_ca: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    taux_commission: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    montant_commission: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    statut: Mapped[StatutCommission] = mapped_column(
        String(20), default=StatutCommission.EN_ATTENTE.value
    )
    periode_mois: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    validee_par_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Deuxième validateur, requis uniquement au-delà de COMMISSION_VALIDATION_SEUIL
    # (500 DT) — doit être une personne différente du premier validateur.
    validee_par_id_2: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    validated_at_2: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    date_paiement: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relations
    commercial: Mapped["Utilisateur"] = relationship(
        "Utilisateur", foreign_keys=[commercial_id], back_populates="commissions"
    )
    patient: Mapped["Patient"] = relationship("Patient", back_populates="commissions")
    facture: Mapped["Facture"] = relationship("Facture", back_populates="commissions")
    validateur: Mapped[Optional["Utilisateur"]] = relationship(
        "Utilisateur", foreign_keys=[validee_par_id], back_populates="commissions_validees"
    )


class FideliteTransaction(Base):
    __tablename__ = "fidelite_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # gain | depense | expiration
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    solde_apres: Mapped[int] = mapped_column(Integer, nullable=False)
    motif: Mapped[str] = mapped_column(String(100), nullable=False)
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relations
    patient: Mapped["Patient"] = relationship("Patient", back_populates="fidelite_transactions")


class CategorieDepense(Base):
    __tablename__ = "categories_depenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    icone: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    couleur: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    budget_mensuel: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relations
    depenses: Mapped[List["Depense"]] = relationship("Depense", back_populates="categorie")


class Depense(Base):
    __tablename__ = "depenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    categorie_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories_depenses.id", ondelete="SET NULL"), nullable=True
    )
    fournisseur: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    titre: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    montant_ht: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"))
    taux_tva: Mapped[Decimal] = mapped_column(Numeric(5, 3), default=Decimal("0.190"))
    montant_tva: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"))
    montant_ttc: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"))
    date_depense: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    periode_comptable: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    mode_paiement: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_paiement: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    facture_scan_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    facture_scan_statut: Mapped[StatutDepense] = mapped_column(
        String(20), default=StatutDepense.EN_ATTENTE.value
    )
    extraction_ia: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    lot_injectable_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("lots_injectables.id", ondelete="SET NULL"), nullable=True
    )
    valide_par_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relations
    categorie: Mapped[Optional["CategorieDepense"]] = relationship("CategorieDepense", back_populates="depenses")
    lot_injectable: Mapped[Optional["LotInjectable"]] = relationship("LotInjectable", back_populates="depenses")
    validateur: Mapped[Optional["Utilisateur"]] = relationship(
        "Utilisateur", foreign_keys=[valide_par_id], back_populates="depenses_validees"
    )
    createur_depense: Mapped[Optional["Utilisateur"]] = relationship(
        "Utilisateur", foreign_keys=[created_by], back_populates="depenses_created"
    )


class Candidature(Base):
    __tablename__ = "candidatures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    poste: Mapped[str] = mapped_column(String(200), nullable=False)
    nom_candidat: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    telephone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    cv_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    lettre_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    statut: Mapped[StatutCandidature] = mapped_column(
        String(20), default=StatutCandidature.RECU.value
    )
    notes_rh: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date_entretien: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    evaluateur_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relations
    evaluateur: Mapped[Optional["Utilisateur"]] = relationship(
        "Utilisateur", foreign_keys=[evaluateur_id], back_populates="candidatures_evaluees"
    )


class Consommable(Base):
    __tablename__ = "consommables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    nom: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    categorie: Mapped[str] = mapped_column(String(100), nullable=False)
    unite: Mapped[str] = mapped_column(String(50), nullable=False)  # piece, boite, paquet
    stock_actuel: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    seuil_alerte: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    stock_minimum: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    prix_unitaire: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"))
    fournisseur_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relations
    mouvements: Mapped[List["MouvementConsommable"]] = relationship("MouvementConsommable", back_populates="consommable")


class MouvementConsommable(Base):
    __tablename__ = "mouvements_consommables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    consommable_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("consommables.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # entree, sortie
    quantite: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    date_mouvement: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    utilisateur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False
    )
    motif: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relations
    consommable: Mapped["Consommable"] = relationship("Consommable", back_populates="mouvements")
    utilisateur: Mapped["Utilisateur"] = relationship("Utilisateur", back_populates="mouvements_consommables")


class Teleconsultation(Base):
    __tablename__ = "teleconsultations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    rdv_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rendez_vous.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    lien_visio: Mapped[str] = mapped_column(String(500), nullable=False)
    statut: Mapped[str] = mapped_column(String(20), default="planifiee")  # planifiee, en_cours, terminee
    duree_reelle: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # en minutes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relations
    rdv: Mapped["RendezVous"] = relationship("RendezVous", back_populates="teleconsultation")


class Parrainage(Base):
    __tablename__ = "parrainages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parrain_patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    filleul_patient_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True
    )
    code_parrain: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    statut: Mapped[str] = mapped_column(String(20), default="actif")  # actif, utilise
    date_parrainage: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    recompense_attribuee: Mapped[bool] = mapped_column(Boolean, default=False)
    recompense_utilisee: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relations
    parrain: Mapped["Patient"] = relationship("Patient", foreign_keys=[parrain_patient_id], back_populates="parrainages_parrain")
    filleul: Mapped[Optional["Patient"]] = relationship("Patient", foreign_keys=[filleul_patient_id], back_populates="parrainages_filleul")


class AuditLogMedical(Base):
    __tablename__ = "audit_logs_medicaux"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    utilisateur_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    patient_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_audit_patient_date", "patient_id", "created_at"),
        Index("ix_audit_user_date", "utilisateur_id", "created_at"),
    )


class ClinicSetting(Base):
    __tablename__ = "clinic_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False)
    key: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    __table_args__ = (
        UniqueConstraint("clinic_id", "key", name="uq_clinic_settings_clinic_key"),
    )
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class SocialMessage(Base):
    """Message entrant/sortant sur un canal social (inbox unifié).
    plateforme : whatsapp | instagram | facebook | tiktok"""
    __tablename__ = "social_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    plateforme: Mapped[str] = mapped_column(String(20), nullable=False)
    contact_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    contact_nom: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # entrant | sortant
    contenu: Mapped[str] = mapped_column(Text, nullable=False)
    statut: Mapped[str] = mapped_column(String(20), default="nouveau")  # nouveau|traite|repondu
    reponse_auto_envoyee: Mapped[bool] = mapped_column(Boolean, default=False)
    patient_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_social_messages_clinic_plateforme", "clinic_id", "plateforme"),
        Index("ix_social_messages_clinic_statut", "clinic_id", "statut"),
    )


class SocialPost(Base):
    """Post planifié/publié sur un canal social, avec métriques d'engagement."""
    __tablename__ = "social_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    plateforme: Mapped[str] = mapped_column(String(20), nullable=False)
    contenu: Mapped[str] = mapped_column(Text, nullable=False)
    media_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    date_publication_prevue: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    date_publication_reelle: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="brouillon")  # brouillon|planifie|publie|echec
    erreur: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    plateforme_post_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    commentaires: Mapped[int] = mapped_column(Integer, default=0)
    partages: Mapped[int] = mapped_column(Integer, default=0)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_social_posts_clinic_plateforme", "clinic_id", "plateforme"),
        Index("ix_social_posts_clinic_statut", "clinic_id", "statut"),
    )


class CampagneMarketing(Base):
    __tablename__ = "campagnes_marketing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    nom: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    segment_cible: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    message_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date_envoi_planifiee: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="brouillon")
    nb_envoyes: Mapped[int] = mapped_column(Integer, default=0)
    nb_ouverts: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relations
    createur_campagne: Mapped[Optional["Utilisateur"]] = relationship(
        "Utilisateur", foreign_keys=[created_by], back_populates="campagnes_created"
    )


class EquipeMessage(Base):
    """Messagerie interne entre membres de l'équipe clinique."""
    __tablename__ = "equipe_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    expediteur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False
    )
    destinataire_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False
    )
    sujet: Mapped[str] = mapped_column(String(200), nullable=False)
    contenu: Mapped[str] = mapped_column(Text, nullable=False)
    lu: Mapped[bool] = mapped_column(Boolean, default=False)
    lu_a: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cree_a: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_equipe_messages_clinic_expediteur", "clinic_id", "expediteur_id"),
        Index("ix_equipe_messages_clinic_destinataire", "clinic_id", "destinataire_id"),
        Index("ix_equipe_messages_destinataire_lu", "destinataire_id", "lu"),
    )

    # Relations
    expediteur: Mapped["Utilisateur"] = relationship(
        "Utilisateur", foreign_keys=[expediteur_id], backref="messages_envoyes"
    )
    destinataire: Mapped["Utilisateur"] = relationship(
        "Utilisateur", foreign_keys=[destinataire_id], backref="messages_recus"
    )


# ═══════════════════════════════════════════════════════════
# Helpers moteurs
# ═══════════════════════════════════════════════════════════

def get_async_engine(database_url: str):
    """Retourne le moteur async SQLAlchemy."""
    return create_async_engine(database_url, echo=False, future=True)


def get_async_sessionmaker(engine):
    """Retourne la factory de sessions async."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class PlateformeAvis(str, enum.Enum):
    """Plateformes d'avis supportées (correctif Bug #8 audit).

    Enum côté Python pour valider les valeurs en API + CHECK constraint
    côté SQL pour rejeter toute insertion hors-énumération. Le rapport
    d'audit soulignait que ``String(20)`` acceptait n'importe quelle
    chaîne (ex: ``FACEBOOK`` au lieu de ``facebook``), cassant les
    filtres et l'auto-reply IA. On conserve la valeur technique en
    minuscule pour cohérence avec le reste de la base.
    """
    GOOGLE = "google"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"


class AvisClient(Base):
    """Avis clients récoltés (Google, Instagram, Facebook)."""
    __tablename__ = "avis_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Bug #8 (audit) : la plateforme reste en String(20) pour rester
    # compatible avec les INSERT legacy, mais est désormais validée par
    # un CheckConstraint côté SQL + par PlateformeAvis côté Python. Les
    # futurs inserts passeront par la couche PydanticAvisClientIn qui
    # valide la valeur côté routeur (cf. api/v1/social.py).
    plateforme: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    texte: Mapped[str] = mapped_column(Text, nullable=False)
    auteur_nom: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    reponse_suggeree_ia: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reponse_publiee: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="nouveau")  # nouveau|suggere|valide|publie
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_avis_clinic_plateforme", "clinic_id", "plateforme"),
        Index("ix_avis_clinic_statut", "clinic_id", "statut"),
        CheckConstraint(
            "plateforme IN ('google', 'instagram', 'facebook')",
            name="ck_avis_plateforme_enum",
        ),
    )

class SimulationIA(Base):
    """Simulations de résultats générées par IA."""
    __tablename__ = "simulations_ia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    photo_source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("photos_clinic.id", ondelete="CASCADE"), nullable=False
    )
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    zone_anatomique: Mapped[str] = mapped_column(String(50), nullable=False)
    url_resultat: Mapped[str] = mapped_column(String(500), nullable=False)
    consentement_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("consentements.id", ondelete="RESTRICT"), nullable=False
    )
    genere_par_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relations
    photo_source: Mapped["PhotoClinic"] = relationship("PhotoClinic")
    patient: Mapped["Patient"] = relationship("Patient")
    consentement: Mapped["Consentement"] = relationship("Consentement")
    createur: Mapped["Utilisateur"] = relationship("Utilisateur")


# ── QMS & Scribe IA Extensions (Niveau 9+) ──────────────────────────────

class QMSDocument(Base):
    __tablename__ = "qms_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    categorie: Mapped[str] = mapped_column(String(100), nullable=False) # "Protocole Clinique", "Hygiène", "Réglementaire"
    version: Mapped[str] = mapped_column(String(50), default="1.0")
    contenu_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fichier_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    statut: Mapped[str] = mapped_column(String(50), default="actif")
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("utilisateurs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MedicalScribeSession(Base):
    __tablename__ = "medical_scribe_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    dossier_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("dossiers_medicaux.id"), nullable=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id"), nullable=False)
    praticien_id: Mapped[int] = mapped_column(Integer, ForeignKey("utilisateurs.id"), nullable=False)
    audio_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    transcription_brute: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes_structurees_soap: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class AuditLogFinancial(Base):
    __tablename__ = "audit_logs_financial"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    entite_type: Mapped[str] = mapped_column(String(50), nullable=False) # "facture", "depense", "commission"
    entite_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False) # "creation", "modification", "annulation", "paiement"
    valeur_avant: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    valeur_apres: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    modifie_par_id: Mapped[int] = mapped_column(Integer, ForeignKey("utilisateurs.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    modifie_par: Mapped["Utilisateur"] = relationship("Utilisateur")

# ── Module Délégués Médicaux & Laboratoires (Niveau 9+ Extension) ────────

class LaboratoirePartenaire(Base):
    __tablename__ = "laboratoires_partenaires"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    nom: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_nom: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    telephone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    adresse: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    site_web: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    delegues: Mapped[List["DelegueMedical"]] = relationship("DelegueMedical", back_populates="laboratoire")

class DelegueMedical(Base):
    __tablename__ = "delegues_medicaux"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    labo_id: Mapped[int] = mapped_column(Integer, ForeignKey("laboratoires_partenaires.id"), nullable=False)
    nom: Mapped[str] = mapped_column(String(200), nullable=False)
    prenom: Mapped[str] = mapped_column(String(200), nullable=False)
    telephone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    specialite: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    laboratoire: Mapped["LaboratoirePartenaire"] = relationship("LaboratoirePartenaire", back_populates="delegues")
    visites: Mapped[List["VisiteDelegue"]] = relationship("VisiteDelegue", back_populates="delegue")

class VisiteDelegue(Base):
    __tablename__ = "visites_delegues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    delegue_id: Mapped[int] = mapped_column(Integer, ForeignKey("delegues_medicaux.id"), nullable=False)
    medecin_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("utilisateurs.id"), nullable=True)
    date_visite: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    objet: Mapped[str] = mapped_column(String(255), nullable=False) # "Présentation Produit", "Dotation", "Formation"
    compte_rendu: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    echantillons_recus: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # JSON list of {produit, quantite}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    delegue: Mapped["DelegueMedical"] = relationship("DelegueMedical", back_populates="visites")
    medecin: Mapped[Optional["Utilisateur"]] = relationship("Utilisateur")
