"""Implémentation backend-validée des tools Bloc 4."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.clinic_rbac import check_permission
from config import get_settings
from models.database import ActeMedical, CampagneMarketing, Patient, RendezVous, StatutRDV
from models.security import TacheInterneAssistant
from services.agenda import annuler_rdv, creer_rdv, get_disponibilites
from services.assistant_tools import get_revenue_summary, send_daily_report
from services.clinic_agent_tools_schema import lookup_tool
from services.omnicanal.email_connector import EmailConnector
from services.omnicanal_service import get_or_create_conversation, send_reply
from services.patients import list_patients


class ToolNotAllowed(Exception):
    pass


class ToolPermissionDenied(Exception):
    pass


async def _get_patient(patient_id: int, db: AsyncSession, clinic_id: int) -> Patient:
    result = await db.execute(select(Patient).where(
        Patient.id == patient_id,
        Patient.clinic_id == clinic_id,
    ))
    patient = result.scalar_one_or_none()
    if not patient:
        raise ValueError("Patient introuvable")
    return patient


async def _get_rdv(rdv_id: int, db: AsyncSession, clinic_id: int) -> RendezVous:
    result = await db.execute(select(RendezVous).where(
        RendezVous.id == rdv_id,
        RendezVous.clinic_id == clinic_id,
    ))
    rdv = result.scalar_one_or_none()
    if not rdv:
        raise ValueError("RDV introuvable")
    return rdv


async def search_patient(current_user: dict[str, Any], db: AsyncSession, query: str) -> dict[str, Any]:
    patients = await list_patients(current_user, db, search=query, limit=10)
    return {"count": len(patients), "items": patients[:10]}


async def create_rdv_tool(current_user: dict[str, Any], db: AsyncSession, **kwargs) -> dict[str, Any]:
    dt = datetime.fromisoformat(kwargs["date_heure"])
    rdv, consent_missing = await creer_rdv(
        patient_id=kwargs["patient_id"],
        praticien_id=kwargs["praticien_id"],
        acte_id=kwargs["acte_id"],
        date_heure=dt,
        salle=kwargs.get("salle"),
        db=db,
        created_by=current_user.get("id"),
        clinic_id=current_user.get("clinic_id"),
    )
    return {
        "id": rdv.id,
        "patient_id": rdv.patient_id,
        "praticien_id": rdv.praticien_id,
        "acte_id": rdv.acte_id,
        "date_heure": rdv.date_heure_debut.isoformat(),
        "statut": rdv.statut,
        "consentement_manquant": consent_missing,
    }


async def update_rdv_tool(current_user: dict[str, Any], db: AsyncSession, **kwargs) -> dict[str, Any]:
    rdv = await _get_rdv(kwargs["rdv_id"], db, current_user["clinic_id"])
    if kwargs.get("date_heure"):
        nouvelle_date = datetime.fromisoformat(kwargs["date_heure"])
        if rdv.acte_id:
            acte_res = await db.execute(select(ActeMedical).where(ActeMedical.id == rdv.acte_id))
            acte = acte_res.scalar_one_or_none()
            duree = acte.duree_minutes if acte else 30
        else:
            duree = 30
        dispo = await get_disponibilites(
            rdv.praticien_id,
            nouvelle_date.date(),
            duree,
            db,
            clinic_id=current_user.get("clinic_id"),
        )
        if not any(slot["heure"] == nouvelle_date.strftime("%H:%M") for slot in dispo):
            raise ValueError("Créneau indisponible pour ce praticien")
        rdv.date_heure_debut = nouvelle_date
        rdv.date_heure_fin = nouvelle_date + timedelta(minutes=duree)
    if kwargs.get("statut"):
        valeurs_valides = [s.value for s in StatutRDV]
        if kwargs["statut"] not in valeurs_valides:
            raise ValueError(f"statut invalide, doit être l'un de : {', '.join(valeurs_valides)}")
        rdv.statut = kwargs["statut"]
    if "notes_pre_acte" in kwargs:
        rdv.notes_pre_acte = kwargs.get("notes_pre_acte")
    if "notes_post_acte" in kwargs:
        rdv.notes_post_acte = kwargs.get("notes_post_acte")
    if "salle" in kwargs:
        rdv.salle = kwargs.get("salle")
    await db.flush()
    return {
        "id": rdv.id,
        "statut": rdv.statut,
        "date_heure": rdv.date_heure_debut.isoformat(),
        "salle": rdv.salle,
    }


async def cancel_rdv_tool(current_user: dict[str, Any], db: AsyncSession, **kwargs) -> dict[str, Any]:
    rdv = await annuler_rdv(
        kwargs["rdv_id"],
        kwargs["raison"],
        db,
        clinic_id=current_user.get("clinic_id"),
    )
    return {"id": rdv.id, "statut": rdv.statut, "raison": kwargs["raison"]}


async def send_whatsapp_tool(current_user: dict[str, Any], db: AsyncSession, **kwargs) -> dict[str, Any]:
    patient = await _get_patient(kwargs["patient_id"], db, current_user["clinic_id"])
    if not patient.whatsapp_phone:
        raise ValueError("Ce patient n'a pas de numéro WhatsApp")
    if patient.opted_out:
        raise ValueError("Le patient a refusé les communications WhatsApp")
    conversation = await get_or_create_conversation(
        canal="whatsapp",
        contact_external_id=patient.whatsapp_phone,
        contact_nom=f"{patient.prenom} {patient.nom}",
        patient_id=patient.id,
        db=db,
        clinic_id=current_user["clinic_id"],
    )
    result = await send_reply(
        conversation_id=conversation.id,
        content=kwargs["message"],
        db=db,
        envoye_par_id=current_user.get("id"),
        clinic_id=current_user["clinic_id"],
    )
    message = result["message"]
    return {
        "conversation_id": conversation.id,
        "message_id": message.id,
        "statut": message.statut,
        "patient_id": patient.id,
    }


async def send_email_tool(current_user: dict[str, Any], db: AsyncSession, **kwargs) -> dict[str, Any]:
    patient = await _get_patient(kwargs["patient_id"], db, current_user["clinic_id"])
    if not patient.email:
        raise ValueError("Ce patient n'a pas d'adresse email")
    connector = EmailConnector()
    result = await connector.send_message(
        contact_id=patient.email,
        content=kwargs["message"],
        subject=kwargs["subject"],
    )
    return {
        "patient_id": patient.id,
        "email": patient.email,
        "statut": result.get("status"),
        "success": result.get("success", False),
        "details": result.get("details"),
    }


async def launch_campaign_tool(current_user: dict[str, Any], db: AsyncSession, **kwargs) -> dict[str, Any]:
    clinic_id = current_user.get("clinic_id")
    if clinic_id is None:
        raise ValueError("Contexte clinique absent")
    campagne = CampagneMarketing(
        clinic_id=clinic_id,
        nom=kwargs["nom"],
        type=kwargs["type"],
        segment_cible={"label": kwargs.get("segment_label") or "non_precise"},
        message_template=kwargs["message_template"],
        statut="brouillon_confirme",
        created_by=current_user.get("id"),
    )
    db.add(campagne)
    await db.flush()
    return {
        "id": campagne.id,
        "nom": campagne.nom,
        "type": campagne.type,
        "statut": campagne.statut,
    }


async def get_statistics_tool(current_user: dict[str, Any], db: AsyncSession, **kwargs) -> dict[str, Any]:
    return await get_revenue_summary(current_user, db, periode=kwargs.get("periode", "semaine"))


async def create_internal_task_tool(current_user: dict[str, Any], db: AsyncSession, **kwargs) -> dict[str, Any]:
    clinic_id = current_user.get("clinic_id")
    if clinic_id is None:
        raise ValueError("Contexte clinique absent")
    task = TacheInterneAssistant(
        clinic_id=clinic_id,
        creee_par_id=current_user.get("id"),
        assignee_id=kwargs.get("assignee_id") or current_user.get("id"),
        patient_id=kwargs.get("patient_id"),
        titre=kwargs["titre"],
        description=kwargs.get("description"),
        priorite=kwargs.get("priorite") or "normale",
    )
    db.add(task)
    await db.flush()
    return {
        "id": task.id,
        "titre": task.titre,
        "statut": task.statut,
        "assignee_id": task.assignee_id,
    }


async def summarize_day_tool(current_user: dict[str, Any], db: AsyncSession, **kwargs) -> dict[str, Any]:
    return await send_daily_report(current_user, db)


async def run_tool(tool_name: str, parameters: dict[str, Any], current_user: dict[str, Any], db: AsyncSession) -> dict[str, Any]:
    settings = get_settings()
    external_channel = {"send_whatsapp": "whatsapp", "send_email": "email"}.get(tool_name)
    if external_channel and external_channel not in settings.allowed_external_integrations:
        raise ToolNotAllowed(f"Canal externe désactivé par la configuration : {external_channel}")
    spec = lookup_tool(tool_name)
    if not spec:
        raise ToolNotAllowed(f"Tool inconnu: {tool_name}")
    if not check_permission(current_user.get("role", ""), spec["resource"], spec["action"]):
        raise ToolPermissionDenied(
            f"Rôle '{current_user.get('role')}' non autorisé pour {spec['resource']}:{spec['action']}"
        )

    if tool_name == "search_patient":
        return await search_patient(current_user, db, parameters["query"])
    if tool_name == "create_rdv":
        return await create_rdv_tool(current_user, db, **parameters)
    if tool_name == "update_rdv":
        return await update_rdv_tool(current_user, db, **parameters)
    if tool_name == "cancel_rdv":
        return await cancel_rdv_tool(current_user, db, **parameters)
    if tool_name == "send_whatsapp":
        return await send_whatsapp_tool(current_user, db, **parameters)
    if tool_name == "send_email":
        return await send_email_tool(current_user, db, **parameters)
    if tool_name == "launch_campaign":
        return await launch_campaign_tool(current_user, db, **parameters)
    if tool_name == "get_statistics":
        return await get_statistics_tool(current_user, db, **parameters)
    if tool_name == "create_internal_task":
        return await create_internal_task_tool(current_user, db, **parameters)
    if tool_name == "summarize_day":
        return await summarize_day_tool(current_user, db, **parameters)
    raise ToolNotAllowed(f"Tool non câblé: {tool_name}")
