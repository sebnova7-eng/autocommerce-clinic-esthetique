"""
AutoCommerce Clinic — Modèles CRM Omnicanal

Nouveaux modèles pour une structure de conversations omnicanale.
Ces modèles COEXISTENT avec les anciennes tables social_messages / social_posts
qui ne sont jamais supprimées (rétrocompatibilité garantie).

Nouveaux concepts :
  - Conversation : un fil de discussion avec un contact sur un canal donné
  - Message : message individuel dans une conversation, avec type, pièces jointes,
    accusés de réception, retries, événements
  - ChannelConfig : configuration par canal (whatsapp, instagram, facebook, tiktok, email, sms)
  - ChannelEvent : journal des événements (envoyé, lu, échec, retry, etc.)

Migrations : ajoutées dans alembic/versions/ sans toucher aux tables existantes.
"""

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.database import Base, Utilisateur


# ═══════════════════════════════════════════════════════════
# ENUMS OMNICANAUX
# ═══════════════════════════════════════════════════════════

class CanalEnum(str, enum.Enum):
    """Canaux supportés par le CRM omnicanal."""
    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    EMAIL = "email"
    SMS = "sms"


class TypeMessageEnum(str, enum.Enum):
    """Types de messages supportés."""
    TEXTE = "texte"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    PDF = "pdf"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    TEMPLATE = "template"
    CAROUSEL = "carousel"
    BOUTON = "bouton"
    INTERACTIF = "interactif"
    REACTIF = "reactif"


class StatutMessageEnum(str, enum.Enum):
    """Cycle de vie complet d'un message."""
    BROUILLON = "brouillon"
    ENVOI_EN_COURS = "envoi_en_cours"
    ENVOYE = "envoye"
    DELIVRE = "delivre"
    LU = "lu"
    ECHEC = "echec"
    ANNULE = "annule"


class StatutCanalEnum(str, enum.Enum):
    """État de configuration d'un canal."""
    NON_CONFIGURE = "non_configure"
    CONFIGURE = "configure"
    ACTIF = "actif"
    LIMITE = "limite"
    DESACTIVE = "desactive"


# ═══════════════════════════════════════════════════════════
# MODÈLES OMNICANAUX
# ═══════════════════════════════════════════════════════════

class ChannelConfig(Base):
    """Configuration d'un canal de communication."""
    __tablename__ = "channel_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    canal: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    statut: Mapped[str] = mapped_column(String(20), default=StatutCanalEnum.NON_CONFIGURE.value)

    # Credentials chiffrées (Fernet)
    api_key_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    api_secret_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    webhook_verify_token_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Identifiants spécifiques par canal
    account_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    business_account_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sender_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sender_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Paramètres
    config_json: Mapped[Optional[dict]] = mapped_column(Text, nullable=True)  # JSON

    # Limites & quotas
    messages_par_jour: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    messages_envoyes_aujourdhui: Mapped[int] = mapped_column(Integer, default=0)
    derniere_reinitialisation_quota: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Méta
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_channel_configs_clinic_canal", "clinic_id", "canal"),
    )

    # Relations
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation", back_populates="channel_config",
        foreign_keys="Conversation.canal_config_id"
    )


class Conversation(Base):
    """Fil de discussion avec un contact sur un canal donné."""
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    canal_config_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("channel_configs.id", ondelete="SET NULL"), nullable=True
    )
    canal: Mapped[str] = mapped_column(String(20), nullable=False)

    # Contact
    contact_external_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    contact_nom: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Lien patient
    patient_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True
    )

    # Métadonnées conversation
    statut: Mapped[str] = mapped_column(String(20), default="ouverte")  # ouverte | fermee | archivee
    dernier_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nb_messages: Mapped[int] = mapped_column(Integer, default=0)

    # Tags & catégories
    tags: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # JSON list
    assignee_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_conversations_clinic_canal", "clinic_id", "canal"),
        Index("ix_conversations_contact", "contact_external_id"),
        Index("ix_conversations_patient", "patient_id"),
        Index("ix_conversations_statut", "clinic_id", "statut"),
    )

    # Relations
    channel_config: Mapped[Optional["ChannelConfig"]] = relationship(
        "ChannelConfig", back_populates="conversations",
        foreign_keys=[canal_config_id]
    )
    messages: Mapped[List["MessageOmnicanal"]] = relationship(
        "MessageOmnicanal", back_populates="conversation", cascade="all, delete-orphan"
    )


class MessageOmnicanal(Base):
    """Message individuel dans une conversation omnicanale."""
    __tablename__ = "messages_omnicanal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="RESTRICT"), index=True, nullable=False
    )

    # Contenu
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # entrant | sortant
    type_message: Mapped[str] = mapped_column(String(20), default=TypeMessageEnum.TEXTE.value)
    contenu: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Pièces jointes (JSON array)
    pieces_jointes: Mapped[Optional[dict]] = mapped_column(Text, nullable=True)

    # Statut d'envoi
    statut: Mapped[str] = mapped_column(String(20), default=StatutMessageEnum.ENVOYE.value)

    # Référence externe (message ID retourné par le canal)
    external_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Accusés de réception
    delivre_a: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    lu_a: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Retry
    nb_retries: Mapped[int] = mapped_column(Integer, default=0)
    dernier_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    # Réponse automatique
    reponse_auto: Mapped[bool] = mapped_column(Boolean, default=False)

    # Template (WhatsApp templates)
    template_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    template_language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    template_params: Mapped[Optional[dict]] = mapped_column(Text, nullable=True)

    # Erreur
    erreur: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Lien patient
    patient_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True
    )

    # Envoi utilisateur
    envoye_par_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_messages_conversation_statut", "conversation_id", "statut"),
        Index("ix_messages_clinic_date", "clinic_id", "created_at"),
        Index("ix_messages_external_id", "external_message_id"),
        UniqueConstraint("conversation_id", "external_message_id", name="uq_messages_conversation_external_id"),
    )

    # Relations
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages",
        foreign_keys=[conversation_id]
    )
    envoye_par: Mapped[Optional["Utilisateur"]] = relationship(
        "Utilisateur", foreign_keys=[envoye_par_id]
    )
    events: Mapped[List["ChannelEvent"]] = relationship(
        "ChannelEvent", back_populates="message", cascade="all, delete-orphan"
    )


class ChannelEvent(Base):
    """Journal des événements d'un message (envoyé, lu, échec, retry, etc.)"""
    __tablename__ = "channel_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    message_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("messages_omnicanal.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    conversation_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )

    type_evenement: Mapped[str] = mapped_column(String(50), nullable=False)
    # Types : sent | delivered | read | failed | retry | bounce | opened | clicked | replied

    details: Mapped[Optional[dict]] = mapped_column(Text, nullable=True)  # JSON
    raw_payload: Mapped[Optional[dict]] = mapped_column(Text, nullable=True)  # JSON brut de l'API

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_channel_events_message_date", "message_id", "timestamp"),
        Index("ix_channel_events_clinic_date", "clinic_id", "timestamp"),
    )

    # Relations
    message: Mapped["MessageOmnicanal"] = relationship(
        "MessageOmnicanal", back_populates="events",
        foreign_keys=[message_id]
    )
