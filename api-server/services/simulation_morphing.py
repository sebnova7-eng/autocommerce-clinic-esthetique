"""
AutoCommerce Clinic — Simulation IA / Morphing
Génération de résultats simulés avec filigrane obligatoire et chiffrement.
"""

import asyncio
import base64
import io
import os
from datetime import datetime
from typing import Any, Optional

import requests
from PIL import Image as PILImage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from core.llm_budget import reserve_budget
from core.medical_ai_policy import require_medical_ai_approval
from models.database import Patient, PhotoClinic, SimulationIA
from services.audit_medical import log_access
from services.consentement import verify_consent
from services.photos_clinic import (
    _add_watermark,
    _create_thumbnail,
    _decrypt_file,
    _encrypt_file,
    _save_signed_jpeg,
)

settings = get_settings()
SIMULATION_SEMAPHORE = asyncio.Semaphore(1)


OPENAI_IMAGE_EDIT_ENDPOINT = "https://api.openai.com/v1/images/edits"


def _resolve_image_model() -> str:
    """Retourne un modèle compatible avec l'édition d'image.

    Correctif Bug #9 : ``dall-e-3`` ne doit pas être utilisé comme valeur
    par défaut pour un flux d'édition/morphing car l'API d'édition moderne
    attend un modèle image dédié. On bascule donc automatiquement vers
    ``gpt-image-1`` si l'instance est restée sur l'ancien défaut.
    """
    configured = (getattr(settings, "openai_image_model", "") or "").strip()
    if not configured:
        return "gpt-image-1"

    legacy_models = {"dall-e-2", "dall-e-3"}
    if configured.lower() in legacy_models:
        return "gpt-image-1"

    return configured


def _normalize_intensite(intensite: int) -> int:
    """Borne l'intensité même si le service est appelé hors route FastAPI."""
    return max(0, min(100, int(intensite)))


def _build_simulation_prompt(zone: str, intensite: int) -> str:
    """Construit un prompt d'édition photoréaliste et médicalement prudent."""
    intensite = _normalize_intensite(intensite)
    zone_label = (zone or "zone esthétique concernée").strip()

    if intensite <= 20:
        intensity_label = "very subtle"
    elif intensite <= 45:
        intensity_label = "subtle"
    elif intensite <= 70:
        intensity_label = "moderate"
    else:
        intensity_label = "visible but still medically plausible"

    return (
        "Edit this clinical reference photo of the same patient into a realistic "
        "aesthetic-treatment projection. Preserve identity perfectly, keep the same "
        "camera angle, crop, background, skin texture, hair, expression, and lighting. "
        f"Only modify the anatomical area '{zone_label}' with a {intensity_label} result "
        f"corresponding to intensity {intensite}/100. The outcome must look like a conservative, "
        "credible post-treatment simulation used during a medical consultation. "
        "Do not create a split screen, no before/after collage, no extra text, no makeup change, "
        "no jewelry change, no cartoon effect, no exaggerated transformation. Keep all untreated "
        "areas unchanged and photorealistic."
    )


def _prepare_image_for_openai(photo_bytes: bytes) -> io.BytesIO:
    """Prépare la photo source dans un format robuste pour l'API d'édition."""
    img = PILImage.open(io.BytesIO(photo_bytes)).convert("RGBA")

    max_dim = 1536
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim))

    prepared = io.BytesIO()
    img.save(prepared, format="PNG")
    prepared.seek(0)
    prepared.name = "simulation_source.png"
    return prepared


def _decode_openai_image_payload(payload: dict[str, Any]) -> bytes:
    """Extrait l'image binaire depuis la réponse JSON OpenAI."""
    data = payload.get("data") or []
    if not data:
        raise RuntimeError("Réponse OpenAI invalide : aucune image retournée")

    first = data[0] or {}
    b64_image = first.get("b64_json")
    if b64_image:
        return base64.b64decode(b64_image)

    image_url = first.get("url")
    if image_url:
        download = requests.get(image_url, timeout=60)
        download.raise_for_status()
        return download.content

    raise RuntimeError("Réponse OpenAI invalide : image introuvable dans la réponse")


def _generate_ai_simulation_image(photo_bytes: bytes, zone: str, intensite: int) -> bytes:
    """Génère une vraie simulation IA via l'API OpenAI Images Edits.

    Correctif Bug #9 : on supprime la fausse "simulation" basée sur un simple
    changement de luminosité et on remplace ce comportement par une édition
    d'image dédiée, centrée sur la zone anatomique et l'intensité demandées.
    """
    if getattr(settings, "env", "development") == "production" and (
        not getattr(settings, "llm_enabled", False)
        or "ai" not in settings.allowed_external_integrations
    ):
        raise RuntimeError("Les sorties IA sont désactivées par la politique de déploiement")
    if getattr(settings, "env", "development") == "production" and getattr(settings, "llm_provider", "openai") != "openai":
        raise RuntimeError("La simulation d’image exige le provider IA OpenAI explicitement autorisé")
    api_key = getattr(settings, "openai_api_key", None)
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY manquant : impossible de générer une vraie simulation IA. "
            "Aucune simulation dégradée locale n'est produite pour éviter un faux morphing."
        )

    model = _resolve_image_model()
    prompt = _build_simulation_prompt(zone, intensite)
    prepared_image = _prepare_image_for_openai(photo_bytes)

    response = requests.post(
        OPENAI_IMAGE_EDIT_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}"},
        data={
            "model": model,
            "prompt": prompt,
            "size": "1024x1024",
            "response_format": "b64_json",
        },
        files={
            "image": (prepared_image.name, prepared_image.getvalue(), "image/png"),
        },
        timeout=180,
    )
    response.raise_for_status()
    return _decode_openai_image_payload(response.json())


async def generer_simulation_ia(
    patient_id: int,
    photo_source_id: int,
    zone: str,
    intensite: int,
    genere_par_id: int,
    db: AsyncSession,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    clinic_id: int | None = None,
) -> SimulationIA:
    """Génère une simulation de résultat par IA.

    1. Vérifie le consentement spécifique 'simulation_ia'
    2. Récupère et déchiffre la photo source
    3. Appelle l'API d'édition d'image OpenAI pour produire une vraie simulation
    4. Applique le filigrane déontologique obligatoire
    5. Chiffre et stocke le résultat
    6. Log l'accès sensible
    """

    if clinic_id is None:
        if settings.env in {"test", "development"}:
            clinic_id = int(settings.clinic_id or 1)
        elif settings.is_internal_single_clinic and settings.clinic_id:
            clinic_id = int(settings.clinic_id)
        else:
            raise ValueError("Contexte clinique obligatoire")
    intensite = _normalize_intensite(intensite)
    require_medical_ai_approval(settings, "image_simulation")

    patient_result = await db.execute(select(Patient).where(
        Patient.id == patient_id,
        Patient.clinic_id == clinic_id,
    ))
    if patient_result.scalar_one_or_none() is None:
        raise ValueError("Patient non trouvé")

    # 1. Vérification consentement spécifique
    consentement = await verify_consent(
        patient_id, None, db, type_consentement="simulation_ia", clinic_id=clinic_id
    )
    if not consentement:
        raise ValueError("Consentement spécifique 'Simulation IA' non signé ou expiré")

    # 2. Récupérer photo source
    result = await db.execute(select(PhotoClinic).where(
        PhotoClinic.id == photo_source_id,
        PhotoClinic.patient_id == patient_id,
        PhotoClinic.clinic_id == clinic_id,
        not PhotoClinic.is_deleted,
    ))
    photo_source = result.scalar_one_or_none()
    if not photo_source:
        raise ValueError("Photo source non trouvée")

    with open(photo_source.url_stockage, "rb") as f:
        raw = f.read()
    nonce, ciphertext = raw[:12], raw[12:]
    photo_bytes = _decrypt_file(nonce, ciphertext)

    # 3. Simulation IA réelle, sérialisée pour protéger le VPS et le budget.
    await reserve_budget(
        settings,
        f"clinic:{clinic_id}:user:{genere_par_id}:image_simulation",
        int(getattr(settings, "llm_max_tokens_per_request", 2048)),
        clinic_id=clinic_id,
    )
    async with SIMULATION_SEMAPHORE:
        simulated_bytes = await asyncio.to_thread(
            _generate_ai_simulation_image, photo_bytes,
            zone, intensite,
        )
    img_simulated = PILImage.open(io.BytesIO(simulated_bytes)).convert("RGB")

    # 4. Filigrane obligatoire (CNOM)
    watermark_text = "Simulation non contractuelle"
    img_final = _add_watermark(img_simulated, watermark_text)

    # 5. Chiffrement et stockage
    signed_jpeg = _save_signed_jpeg(img_final, watermark_text, quality=90)
    nonce, ciphertext = _encrypt_file(signed_jpeg)

    date_dir = datetime.utcnow().strftime("%Y/%m")
    base_path = os.path.join(str(settings.photos_dir), "simulations", date_dir)
    os.makedirs(base_path, exist_ok=True)

    filename = f"sim_{patient_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.enc"
    file_path = os.path.join(base_path, filename)

    with open(file_path, "wb") as f:
        f.write(nonce + ciphertext)

    # Génération thumbnail (conservé pour l'écosystème photos si exploité plus tard)
    try:
        _create_thumbnail(img_final)
    except Exception:
        # La vignette n'est pas bloquante pour la simulation stockée.
        pass

    # 6. Créer l'entrée DB
    simulation = SimulationIA(
        clinic_id=clinic_id,
        photo_source_id=photo_source_id,
        patient_id=patient_id,
        zone_anatomique=zone,
        url_resultat=file_path,
        consentement_id=consentement.id,
        genere_par_id=genere_par_id,
    )
    db.add(simulation)
    await db.flush()

    # 7. Log audit
    await log_access(
        db=db,
        utilisateur_id=genere_par_id,
        patient_id=patient_id,
        action="GENERATE_IA_SIMULATION",
        resource_type="simulation_ia",
        resource_id=simulation.id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={"zone": zone, "intensite": intensite, "image_model": _resolve_image_model()},
    )

    return simulation


async def get_decrypted_simulation(
    simulation_id: int,
    patient_id: int,
    db: AsyncSession,
    utilisateur_id: Optional[int] = None,
    clinic_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> tuple[bytes, str]:
    """Déchiffre une simulation pour affichage et journalise la lecture.

    Le tenant est obligatoire hors test/développement et doit être fourni par
    le contexte authentifié de la route, jamais par le frontend.

    Correctif Bug #12 : chaque consultation d'une simulation IA doit être
    tracée dans l'audit médical, pas uniquement sa génération.
    """
    if clinic_id is None:
        if settings.env in {"test", "development"}:
            clinic_id = int(settings.clinic_id or 1)
        else:
            raise ValueError("Contexte clinique obligatoire")

    result = await db.execute(
        select(SimulationIA).where(
            SimulationIA.id == simulation_id,
            SimulationIA.patient_id == patient_id,
            SimulationIA.clinic_id == clinic_id,
            SimulationIA.patient.has(Patient.clinic_id == clinic_id),
        )
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise ValueError("Simulation non trouvée")

    if not os.path.exists(sim.url_resultat):
        raise ValueError("Fichier simulation introuvable")

    with open(sim.url_resultat, "rb") as f:
        raw = f.read()
    nonce, ciphertext = raw[:12], raw[12:]
    decrypted = _decrypt_file(nonce, ciphertext)

    if utilisateur_id is not None:
        await log_access(
            db=db,
            utilisateur_id=utilisateur_id,
            patient_id=patient_id,
            action="READ_IA_SIMULATION",
            resource_type="simulation_ia",
            resource_id=simulation_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"zone": sim.zone_anatomique, "clinic_id": clinic_id},
        )

    return decrypted, f"simulation_{simulation_id}.jpg"
