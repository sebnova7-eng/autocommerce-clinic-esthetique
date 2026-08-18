"""
AutoCommerce Clinic — Modèles Sécurité Enterprise (Blocs 2, 3 et 4)

Modèles pour :
  - whitelist WhatsApp liée à un utilisateur interne,
  - sessions sécurisées multi-tours,
  - journal d'audit assistant / agent,
  - confirmations obligatoires pour opérations sensibles,
  - alertes de sécurité,
  - tâches internes créées par l'agent.

Ces tables s'ajoutent à l'existant sans casser les tables métier.
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base


class StatutWhitelistEnum(str, enum.Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class StatutSessionEnum(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class StatutConfirmationEnum(str, enum.Enum):
    EN_ATTENTE = "en_attente"
    CONFIRMEE = "confirmee"
    REFUSEE = "refusee"
    EXPIREE = "expiree"


class StatutAlerteEnum(str, enum.Enum):
    NOUVELLE = "nouvelle"
    EN_COURS = "en_cours"
    RESOLUE = "resolue"
    FAUSSE_ALARME = "fausse_alarme"


class TypeAlerteEnum(str, enum.Enum):
    NUMERO_NON_AUTORISE = "numero_non_autorise"
    ECHECS_REPETES = "echecs_repetes"
    VOLUME_ANORMAL = "volume_anormal"
    ACCESS_SANS_MFA = "access_sans_mfa"
    SESSION_SUSPECTE = "session_suspecte"
    TOKEN_ROTATION = "token_rotation"


class TypeCommandeAssistantEnum(str, enum.Enum):
    CONSULTER_AGENDA = "consulter_agenda"
    CONSULTER_PATIENT = "consulter_patient"
    CONSULTER_RDV = "consulter_rdv"
    CONSULTER_STOCK = "consulter_stock"
    CONSULTER_FACTURE = "consulter_facture"
    CONSULTER_FIDELITE = "consulter_fidelite"
    CONSULTER_INFOS_CLINIQUE = "consulter_infos_clinique"
    ECRITURE_AGENT = "ecriture_agent"
    HORS_PERIMETRE = "hors_perimetre"


class StatutTacheInterneEnum(str, enum.Enum):
    A_FAIRE = "a_faire"
    EN_COURS = "en_cours"
    TERMINEE = "terminee"
    ANNULEE = "annulee"


class NumeroWhitelist(Base):
    __tablename__ = "numeros_whitelist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    numero: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    nom: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    utilisateur_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    statut: Mapped[str] = mapped_column(String(20), default=StatutWhitelistEnum.ACTIVE.value)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    raison_revocation: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    last_key_rotation: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    permissions_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_whitelist_clinic_numero", "clinic_id", "numero"),
        Index("ix_whitelist_clinic_statut", "clinic_id", "statut"),
    )


class SessionAssistant(Base):
    __tablename__ = "sessions_assistant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    whitelist_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("numeros_whitelist.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    utilisateur_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    numero: Mapped[str] = mapped_column(String(20), nullable=False)
    statut: Mapped[str] = mapped_column(String(20), default=StatutSessionEnum.ACTIVE.value)
    token_session: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nb_tours: Mapped[int] = mapped_column(Integer, default=0)
    nb_erreurs: Mapped[int] = mapped_column(Integer, default=0)
    derniere_activite: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    contexte_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_mfa_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_sessions_assistant_token", "token_session"),
        Index("ix_sessions_assistant_statut", "clinic_id", "statut"),
        Index("ix_sessions_assistant_numero", "clinic_id", "numero"),
    )


class CommandeAssistant(Base):
    __tablename__ = "commandes_assistant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    session_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sessions_assistant.id", ondelete="SET NULL"), nullable=True
    )
    whitelist_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("numeros_whitelist.id", ondelete="SET NULL"), nullable=True
    )
    utilisateur_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    numero: Mapped[str] = mapped_column(String(20), nullable=False)
    type_commande: Mapped[str] = mapped_column(String(50), nullable=False)
    question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reponse: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intent_detecte: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    outil_appele: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    role_applique: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="executed")
    raison_refus: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parametres_appel: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    erreur_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contexte_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_commandes_assistant_numero", "clinic_id", "numero"),
        Index("ix_commandes_assistant_date", "clinic_id", "created_at"),
        Index("ix_commandes_assistant_utilisateur", "clinic_id", "utilisateur_id"),
        Index("ix_commandes_assistant_outil", "clinic_id", "outil_appele"),
    )


class ConfirmationSensible(Base):
    __tablename__ = "confirmations_sensibles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    utilisateur_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    session_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sessions_assistant.id", ondelete="SET NULL"), nullable=True
    )
    numero: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    type_operation: Mapped[str] = mapped_column(String(50), nullable=False)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default=StatutConfirmationEnum.EN_ATTENTE.value)
    code_confirmation: Mapped[str] = mapped_column(String(8), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    confirme_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_confirmations_clinic_date", "clinic_id", "created_at"),
        Index("ix_confirmations_clinic_statut", "clinic_id", "statut"),
        Index("ix_confirmations_session", "session_id"),
    )


class AlerteSecurite(Base):
    __tablename__ = "alertes_securite"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    type_alerte: Mapped[str] = mapped_column(String(50), nullable=False)
    severite: Mapped[str] = mapped_column(String(20), nullable=False)
    statut: Mapped[str] = mapped_column(String(20), default=StatutAlerteEnum.NOUVELLE.value)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    numero_concerne: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    utilisateur_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    resolue_par_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    resolue_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_alertes_clinic_type", "clinic_id", "type_alerte"),
        Index("ix_alertes_clinic_statut", "clinic_id", "statut"),
        Index("ix_alertes_clinic_severite", "clinic_id", "severite"),
        Index("ix_alertes_date", "clinic_id", "created_at"),
    )


class TacheInterneAssistant(Base):
    __tablename__ = "taches_internes_assistant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    creee_par_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    assignee_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    patient_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True
    )
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priorite: Mapped[str] = mapped_column(String(20), default="normale")
    statut: Mapped[str] = mapped_column(String(20), default=StatutTacheInterneEnum.A_FAIRE.value)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_taches_assistant_clinic_statut", "clinic_id", "statut"),
        Index("ix_taches_assistant_assignee", "assignee_id"),
        Index("ix_taches_assistant_patient", "patient_id"),
    )


class RefreshTokenSession(Base):
    """État serveur d'un refresh token JWT.

    Le JWT reste stateless pour l'accès, mais chaque refresh token est suivi
    côté serveur afin de permettre rotation, révocation et détection de replay.
    Aucun token brut n'est persisté : seul son hash SHA-256 est conservé.
    """

    __tablename__ = "refresh_token_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    family_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    replaced_by_jti: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reuse_detected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_refresh_sessions_user_family", "utilisateur_id", "family_id"),
        Index("ix_refresh_sessions_active_expiry", "expires_at", "revoked_at"),
    )
