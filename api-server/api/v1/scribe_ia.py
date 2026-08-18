from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import DossierMedical, Patient, RoleEnum, MedicalScribeSession
from config import get_settings
from core.llm_client import get_llm_client
from core.medical_ai_policy import (
    MedicalAIBlocked,
    require_medical_ai_approval,
    should_store_raw_medical_transcription,
)
from services.audit_medical import log_access

router = APIRouter(prefix="/scribe-ia", tags=["scribe-medical-ia"])

class ScribeGeneratePayload(BaseModel):
    patient_id: int
    dossier_id: Optional[int] = None
    transcription_brute: str = Field(..., min_length=5)

class ScribeResponse(BaseModel):
    scribe_id: int
    transcription_brute: Optional[str] = None
    notes_structurees_soap: dict

@router.post("/transcribe", response_model=dict)
async def transcribe_medical_audio(
    audio: UploadFile = File(...),
    current_user: dict = Depends(require_role(RoleEnum.MEDECIN, RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    """Transcrit un fichier audio médical en texte brut via Whisper."""
    from services.voice_transcription import _SUPPORTED_AUDIO_MIME_EXT
    from core.openai_audio import transcribe_audio_bytes
    settings = get_settings()
    ext = _SUPPORTED_AUDIO_MIME_EXT.get(audio.content_type)
    if not ext:
        raise HTTPException(status_code=415, detail="Format audio non supporté")
    content = await audio.read(25 * 1024 * 1024 + 1)
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio trop volumineux (maximum 25 Mo)")
    try:
        text = await transcribe_audio_bytes(
            settings, content, f"scribe{ext}", language="fr",
            budget_subject=f"clinic:{current_user['clinic_id']}:user:{current_user['id']}",
            budget_clinic_id=current_user["clinic_id"],
            medical_data=True,
        )
        return {"text": text}
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

@router.post("/process", response_model=ScribeResponse)
async def process_medical_scribe(
    payload: ScribeGeneratePayload,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(RoleEnum.MEDECIN, RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    """Transforme une transcription audio brute en notes SOAP structurées par IA."""
    settings = get_settings()
    patient = await db.scalar(select(Patient).where(
        Patient.id == payload.patient_id,
        Patient.clinic_id == current_user["clinic_id"],
    ))
    if not patient:
        raise HTTPException(status_code=404, detail="Patient non trouvé")
    if payload.dossier_id is not None:
        dossier = await db.scalar(select(DossierMedical).where(
            DossierMedical.id == payload.dossier_id,
            DossierMedical.patient_id == payload.patient_id,
            DossierMedical.clinic_id == current_user["clinic_id"],
        ))
        if not dossier:
            raise HTTPException(status_code=404, detail="Dossier non trouvé")

    try:
        require_medical_ai_approval(settings, "scribe_soap")
    except MedicalAIBlocked as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    llm = get_llm_client(settings)

    prompt = f"""
Tu es un assistant médical expert en esthétique et dermatologie. Analyse la transcription brute suivante d'une consultation et structure-la rigoureusement selon la méthode SOAP (Subjective, Objective, Assessment, Plan).

Transcription brute :
\"\"\"{payload.transcription_brute}\"\"\"

Réponds UNIQUEMENT sous forme d'un objet JSON valide contenant exactement ces 4 clés :
- "subjective": plaintes du patient, historique récent.
- "objective": observations cliniques, examens physiques, mesures.
- "assessment": diagnostic ou évaluation esthétique.
- "plan": plan de traitement, actes préconisés, prescriptions, recommandations.
"""

    messages = [
        {"role": "system", "content": "Tu es un scribe médical expert. Réponds exclusivement en JSON valide."},
        {"role": "user", "content": prompt}
    ]

    out = await llm.chat(
        messages,
        max_tokens=1000,
        response_format_json=True,
        budget_subject=f"clinic:{current_user['clinic_id']}:user:{current_user['id']}",
        budget_clinic_id=current_user["clinic_id"],
    )
    if hasattr(out, "reason"):
        raise HTTPException(status_code=503, detail=f"IA indisponible : {out.reason}")

    import json
    soap_data = {}
    try:
        text = out.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        soap_data = json.loads(text.strip())
    except Exception:
        soap_data = {
            "subjective": "Structuration indisponible : revue manuelle requise",
            "objective": "Non spécifié",
            "assessment": "Consultation esthétique générale",
            "plan": "Suivi selon protocole standard"
        }

    store_raw = should_store_raw_medical_transcription(settings)
    session_obj = MedicalScribeSession(
        clinic_id=current_user["clinic_id"],
        dossier_id=payload.dossier_id,
        patient_id=payload.patient_id,
        praticien_id=current_user["id"],
        transcription_brute=payload.transcription_brute if store_raw else None,
        notes_structurees_soap=soap_data,
    )
    db.add(session_obj)
    await db.commit()
    await db.refresh(session_obj)
    await log_access(
        db=db,
        utilisateur_id=current_user["id"],
        patient_id=payload.patient_id,
        action="GENERATE_MEDICAL_SCRIBE",
        resource_type="medical_scribe_session",
        resource_id=session_obj.id,
        clinic_id=current_user["clinic_id"],
        details={
            "provider": settings.llm_provider,
            "model": settings.openai_model if settings.llm_provider == "openai" else None,
            "raw_transcription_stored": store_raw,
        },
    )

    return ScribeResponse(
        scribe_id=session_obj.id,
        transcription_brute=session_obj.transcription_brute,
        notes_structurees_soap=session_obj.notes_structurees_soap
    )
