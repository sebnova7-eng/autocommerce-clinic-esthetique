"""
AutoCommerce Clinic — Modèles Workflow Engine (Bloc 6)

Workflow Engine IA capable de déclencher automatiquement :
- Rappel WhatsApp, SMS, email
- Création de tâche
- Relance patient
- Campagne fidélité
- Relance devis
- Anniversaire
- Suivi post-opératoire
- Suivi injection
- Suivi esthétique

Tous les workflows configurables visuellement. Chaque déclenchement automatique
passe par les mêmes tools et le même audit que le Bloc 4 — un workflow n'est pas
un raccourci qui contourne la sécurité.
"""

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.database import Base


class WorkflowTriggerType(str, enum.Enum):
    """Types de déclencheurs pour les workflows."""
    SCHEDULED = "scheduled"  # Calendrier (ex. anniversaire)
    EVENT_BASED = "event_based"  # Basé sur un événement (ex. nouveau patient)
    CONDITION_BASED = "condition_based"  # Basé sur une condition (ex. inactivité)
    MANUAL = "manual"  # Déclenchement manuel


class WorkflowActionType(str, enum.Enum):
    """Types d'actions possibles dans un workflow."""
    SEND_WHATSAPP = "send_whatsapp"
    SEND_SMS = "send_sms"
    SEND_EMAIL = "send_email"
    CREATE_TASK = "create_task"
    UPDATE_PATIENT = "update_patient"
    CREATE_APPOINTMENT = "create_appointment"
    LAUNCH_CAMPAIGN = "launch_campaign"
    ADD_FIDELITE_POINTS = "add_fidelite_points"
    TRIGGER_WORKFLOW = "trigger_workflow"


class WorkflowStatus(str, enum.Enum):
    """Statut d'un workflow."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class WorkflowExecutionStatus(str, enum.Enum):
    """Statut d'exécution d'une instance de workflow."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    AWAITING_APPROVAL = "awaiting_approval"


class Workflow(Base):
    """Définition d'un workflow automatisé."""
    
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    nom: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Type de déclencheur
    trigger_type: Mapped[WorkflowTriggerType] = mapped_column(String(20), nullable=False)
    trigger_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Configuration du déclencheur
    
    # Conditions d'exécution
    conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Conditions logiques
    
    # Actions à exécuter
    actions: Mapped[dict] = mapped_column(JSON, nullable=False)  # Liste des actions
    
    # Configuration
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[WorkflowStatus] = mapped_column(
        String(20), default=WorkflowStatus.DRAFT.value, server_default="draft"
    )
    
    # Planification
    cron_expression: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Pour les workflows planifiés
    next_execution: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Limites
    max_executions_per_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    execution_count_today: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    
    # Audit
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=func.now(),
    )
    
    __table_args__ = (
        Index("ix_workflow_clinic_status", "clinic_id", "status"),
        Index("ix_workflow_clinic_enabled", "clinic_id", "enabled"),
    )

    # Relations
    executions: Mapped[List["WorkflowExecution"]] = relationship("WorkflowExecution", back_populates="workflow")


class WorkflowExecution(Base):
    """Enregistrement d'exécution d'un workflow."""
    
    __tablename__ = "workflow_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    
    # Contexte d'exécution
    patient_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Patient concerné si applicable
    trigger_reason: Mapped[str] = mapped_column(String(200), nullable=False)  # Raison du déclenchement
    
    # Statut et résultat
    status: Mapped[WorkflowExecutionStatus] = mapped_column(String(20), default=WorkflowExecutionStatus.PENDING.value)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Résultat de l'exécution
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Message d'erreur si échoué
    
    # Audit
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_execution_workflow_status", "workflow_id", "status"),
        Index("ix_execution_clinic_date", "clinic_id", "created_at"),
    )

    # Relations
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="executions")


class WorkflowTemplate(Base):
    """Modèles prédéfinis de workflows pour accélération."""
    
    __tablename__ = "workflow_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    nom: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    categorie: Mapped[str] = mapped_column(String(50), nullable=False)  # anniversary, followup, relance, etc.
    
    # Configuration du template
    trigger_type: Mapped[WorkflowTriggerType] = mapped_column(String(20), nullable=False)
    trigger_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    actions: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Métadonnées
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkflowAction(Base):
    """Détail d'une action dans un workflow (pour historique et audit)."""
    
    __tablename__ = "workflow_actions_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    execution_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False
    )
    
    action_type: Mapped[WorkflowActionType] = mapped_column(String(50), nullable=False)
    action_config: Mapped[dict] = mapped_column(JSON, nullable=False)  # Configuration de l'action
    
    # Résultat
    status: Mapped[WorkflowExecutionStatus] = mapped_column(String(20), default=WorkflowExecutionStatus.PENDING.value)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Audit
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_action_execution_type", "execution_id", "action_type"),
    )


class WorkflowAuditLog(Base):
    """Audit log granulaire des exécutions workflow (idempotence + traçabilité).

    Introduit en v1.1.0 patch LLM/Workflow Engine (Bloc 6).
    Toute action exécutée (ou mise en brouillon) écrit ici avec une clé
    ``idempotency_key`` permettant de rejouer le run sans double-exécution.
    """
    __tablename__ = "workflow_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    workflow_id: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_audit_workflow_exec", "workflow_id", "execution_id"),
        Index("ix_audit_clinic_date", "clinic_id", "created_at"),
    )


class WorkflowSchedule(Base):
    """Planification des workflows récurrents."""
    
    __tablename__ = "workflow_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    
    # Planification
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    
    # Limites
    max_executions_per_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    execution_count_today: Mapped[int] = mapped_column(
        Integer, default=0
    )
    last_execution: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_execution: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Statut
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


# ═══════════════════════════════════════════════════════════
# Prédéfinitions de templates de workflows
# ═══════════════════════════════════════════════════════════

WORKFLOW_TEMPLATES_PREDEFINED = [
    {
        "nom": "Rappel Anniversaire",
        "description": "Envoyer un message d'anniversaire au patient",
        "categorie": "anniversary",
        "trigger_type": WorkflowTriggerType.SCHEDULED.value,
        "trigger_config": {
            "type": "birthday",
            "days_before": 0,  # Le jour même
        },
        "actions": [
            {
                "type": WorkflowActionType.SEND_WHATSAPP.value,
                "config": {
                    "template": "birthday_greeting",
                    "personalization": True,
                }
            },
            {
                "type": WorkflowActionType.ADD_FIDELITE_POINTS.value,
                "config": {
                    "points": 50,
                    "reason": "Bonus anniversaire"
                }
            }
        ]
    },
    {
        "nom": "Suivi Post-Opératoire",
        "description": "Suivi automatique après un acte médical",
        "categorie": "followup",
        "trigger_type": WorkflowTriggerType.EVENT_BASED.value,
        "trigger_config": {
            "type": "appointment_completed",
            "delay_hours": 24,  # 24h après l'acte
        },
        "actions": [
            {
                "type": WorkflowActionType.SEND_WHATSAPP.value,
                "config": {
                    "template": "postop_followup",
                    "personalization": True,
                }
            },
            {
                "type": WorkflowActionType.CREATE_TASK.value,
                "config": {
                    "title": "Suivi patient post-opératoire",
                    "priority": "medium",
                }
            }
        ]
    },
    {
        "nom": "Relance Patient Inactif",
        "description": "Relancer les patients inactifs depuis 3 mois",
        "categorie": "relance",
        "trigger_type": WorkflowTriggerType.CONDITION_BASED.value,
        "trigger_config": {
            "type": "patient_inactive",
            "days": 90,
        },
        "conditions": {
            "patient_status": "active",
            "opted_out": False,
        },
        "actions": [
            {
                "type": WorkflowActionType.SEND_EMAIL.value,
                "config": {
                    "template": "relance_inactif",
                    "subject": "Nous vous manquez !",
                }
            },
            {
                "type": WorkflowActionType.SEND_WHATSAPP.value,
                "config": {
                    "template": "relance_inactif_wa",
                }
            }
        ]
    },
    {
        "nom": "Relance Devis Non Accepté",
        "description": "Relancer les devis non acceptés après 7 jours",
        "categorie": "relance",
        "trigger_type": WorkflowTriggerType.CONDITION_BASED.value,
        "trigger_config": {
            "type": "quote_not_accepted",
            "days": 7,
        },
        "actions": [
            {
                "type": WorkflowActionType.SEND_EMAIL.value,
                "config": {
                    "template": "relance_devis",
                }
            }
        ]
    },
    {
        "nom": "Suivi Injection",
        "description": "Suivi des patients après injection",
        "categorie": "followup",
        "trigger_type": WorkflowTriggerType.EVENT_BASED.value,
        "trigger_config": {
            "type": "injection_completed",
            "delay_days": 3,  # 3 jours après
        },
        "actions": [
            {
                "type": WorkflowActionType.SEND_WHATSAPP.value,
                "config": {
                    "template": "suivi_injection",
                }
            },
            {
                "type": WorkflowActionType.CREATE_APPOINTMENT.value,
                "config": {
                    "days_from_now": 14,
                    "acte_name": "Suivi injection",
                }
            }
        ]
    },
    {
        "nom": "Suivi Esthétique",
        "description": "Suivi des traitements esthétiques",
        "categorie": "followup",
        "trigger_type": WorkflowTriggerType.EVENT_BASED.value,
        "trigger_config": {
            "type": "aesthetic_treatment_completed",
            "delay_days": 7,
        },
        "actions": [
            {
                "type": WorkflowActionType.SEND_WHATSAPP.value,
                "config": {
                    "template": "suivi_esthetique",
                }
            },
            {
                "type": WorkflowActionType.SEND_SMS.value,
                "config": {
                    "template": "suivi_esthetique_sms",
                }
            }
        ]
    },
    {
        "nom": "Campagne Fidélité",
        "description": "Campagne spéciale pour les clients fidèles",
        "categorie": "loyalty",
        "trigger_type": WorkflowTriggerType.SCHEDULED.value,
        "trigger_config": {
            "type": "monthly",
            "day_of_month": 1,
        },
        "conditions": {
            "loyalty_level": ["gold", "vip"],
        },
        "actions": [
            {
                "type": WorkflowActionType.SEND_EMAIL.value,
                "config": {
                    "template": "campagne_fidelite",
                }
            },
            {
                "type": WorkflowActionType.ADD_FIDELITE_POINTS.value,
                "config": {
                    "points": 100,
                    "reason": "Bonus fidélité mensuel"
                }
            }
        ]
    },
]
