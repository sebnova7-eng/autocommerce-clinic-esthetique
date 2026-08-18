"""
AutoCommerce Clinic — Scan facture IA avec GPT-4o Vision
Upload, extraction, validation, notification WhatsApp
"""

import io
import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pdf2image import convert_from_bytes
from PIL import Image as PILImage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import get_settings
from models.database import Depense, StatutDepense, Utilisateur, RoleEnum
from services.branding import get_branding_context
from services.photos_clinic import _encrypt_file, _decrypt_file
from core.llm_client import LLMUnavailable, get_llm_client

settings = get_settings()

EXTRACTION_PROMPT = """Analyse cette facture fournisseur de clinique esthétique médicale.
Réponds UNIQUEMENT en JSON valide, null si absent.

{
  "fournisseur_nom": "string|null",
  "fournisseur_tel": "string|null",
  "matricule_fiscal": "string|null",
  "numero_facture": "string|null",
  "date_facture": "YYYY-MM-DD|null",
  "lignes": [
    {
      "description": "string",
      "quantite": "number|null",
      "unite": "string|null",
      "prix_unitaire_ht": "number|null",
      "taux_tva": "number|null",
      "montant_ht": "number|null",
      "est_medicament": "boolean",
      "reference_lot": "string|null"
    }
  ],
  "total_ht": "number|null",
  "total_tva": "number|null",
  "total_ttc": "number|null",
  "devise": "string|null",
  "mode_paiement_indique": "string|null"
}

Règles :
- Si la facture contient des produits injectables (acide hyaluronique, toxine botulique, etc.), marque est_medicament=true
- Les montants sont en dinars tunisiens (TND) par défaut
- La date doit être au format YYYY-MM-DD
- Si une information est absente, utilise null
- Ne renvoie JAMAIS de texte hors du JSON"""


_ALLOWED_UPLOADS = {"application/pdf", "image/jpeg", "image/png", "image/webp"}


def _resolve_clinic(clinic_id: int | None) -> int:
    if clinic_id and clinic_id > 0:
        return int(clinic_id)
    if settings.env in {"test", "development"}:
        return int(settings.clinic_id or 1)
    raise ValueError("Contexte clinique obligatoire")


def _validate_upload(file_bytes: bytes, mime_type: str) -> None:
    max_bytes = settings.max_invoice_upload_size_mb * 1024 * 1024
    if not file_bytes or len(file_bytes) > max_bytes:
        raise ValueError(f"Fichier facture invalide ou trop volumineux (max {settings.max_invoice_upload_size_mb} Mo)")
    if mime_type not in _ALLOWED_UPLOADS:
        raise ValueError("Format de facture non autorisé : PDF, JPEG, PNG ou WEBP uniquement")
    if mime_type == "application/pdf":
        if not file_bytes.startswith(b"%PDF-"):
            raise ValueError("Le contenu ne correspond pas à un PDF valide")
        return
    try:
        PILImage.MAX_IMAGE_PIXELS = 16_000_000
        image = PILImage.open(io.BytesIO(file_bytes))
        image.verify()
    except Exception as exc:
        raise ValueError("Le contenu ne correspond pas à une image valide") from exc


async def upload_facture(
    depense_id: int,
    file_bytes: bytes,
    mime_type: str,
    db: AsyncSession,
    clinic_id: int | None = None,
) -> str:
    """Stocke le fichier et retourne le chemin.
    Lance la tâche Celery d'extraction IA."""

    clinic_id = _resolve_clinic(clinic_id)
    _validate_upload(file_bytes, mime_type)
    # Vérifier la dépense dans le contexte clinique courant.
    result = await db.execute(select(Depense).where(
        Depense.id == depense_id,
        Depense.clinic_id == clinic_id,
    ))
    depense = result.scalar_one_or_none()
    if not depense:
        raise ValueError(f"Dépense {depense_id} non trouvée")

    # Stockage AES-GCM : nonce préfixé au ciphertext, jamais en clair.
    ext = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }[mime_type]
    filename = f"facture_depense_{depense_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}{ext}.enc"
    filepath = os.path.join(str(settings.uploads_dir), filename)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    nonce, ciphertext = _encrypt_file(file_bytes)
    with open(filepath, "wb") as f:
        f.write(nonce + ciphertext)

    # Mettre à jour la dépense
    depense.facture_scan_url = filepath
    depense.facture_scan_statut = StatutDepense.EN_ATTENTE.value
    await db.flush()

    # Lancer tâche Celery (async call)
    from services.celery_app import extract_facture_ia_task
    extract_facture_ia_task.delay(depense_id)

    return filepath


async def extract_facture_ia(depense_id: int, db: AsyncSession) -> dict:
    """Tâche Celery : extrait les données de la facture via GPT-4o Vision.

    Si PDF → convertir page 1 en image.
    Appel LLM vision avec prompt structuré.
    Sauvegarde JSON dans depense.extraction_ia.
    """
    result = await db.execute(select(Depense).where(Depense.id == depense_id))
    depense = result.scalar_one_or_none()
    if not depense or not depense.facture_scan_url:
        raise ValueError("Dépense ou scan non trouvé")

    filepath = depense.facture_scan_url

    # Lire et déchiffrer le fichier ; aucune facture brute n'est conservée.
    with open(filepath, "rb") as f:
        encrypted = f.read()
    if len(encrypted) < 13:
        raise ValueError("Fichier facture chiffré invalide")
    file_bytes = _decrypt_file(encrypted[:12], encrypted[12:])

    # Déterminer le type depuis l'extension conservée avant .enc.
    mime_type = "application/pdf" if ".pdf." in filepath else (
        "image/png" if ".png." in filepath else
        "image/webp" if ".webp." in filepath else "image/jpeg"
    )

    if mime_type == "application/pdf":
        images = convert_from_bytes(
            file_bytes, dpi=150, first_page=1,
            last_page=min(1, settings.max_pdf_pages),
        )
        if not images:
            raise ValueError("Impossible de convertir le PDF")
        img = images[0]
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG", quality=95)
        img_bytes.seek(0)
        image_data = img_bytes.read()
        base64_image = _encode_image(image_data)
    else:
        base64_image = _encode_image(file_bytes)

    # Appel IA via la passerelle centrale : allowlist, quota, timeout et audit.
    llm = get_llm_client(settings)
    response = await llm.chat(
        [{
            "role": "user",
            "content": [
                {"type": "text", "text": EXTRACTION_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                        "detail": "high",
                    },
                },
            ],
        }],
        model=settings.openai_model,
        max_tokens=min(2000, settings.llm_max_tokens_per_request),
        temperature=0.1,
        use_cache=False,
        response_format_json=True,
        budget_subject=f"clinic:{depense.clinic_id}:invoice-scanner",
        budget_clinic_id=depense.clinic_id,
    )
    if isinstance(response, LLMUnavailable):
        raise RuntimeError(f"Scan IA indisponible : {response.reason}")
    raw_content = response.text

    # Parser le JSON
    try:
        # Nettoyer les backticks markdown si présents
        cleaned = raw_content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        extraction = json.loads(cleaned)
    except json.JSONDecodeError:
        extraction = {"_parse_error": True, "provider_response_discarded": True}

    # Sauvegarder dans la dépense
    depense.extraction_ia = extraction
    depense.facture_scan_statut = StatutDepense.TRAITEE_IA.value
    await db.flush()

    # Notification WhatsApp directrice
    await _notify_directrice_extraction(depense, extraction, db)

    return extraction


def _encode_image(image_bytes: bytes) -> str:
    import base64
    return base64.b64encode(image_bytes).decode("utf-8")


async def _notify_directrice_extraction(depense: Depense, extraction: dict, db: AsyncSession):
    """Envoie une notification WhatsApp à la directrice."""
    from services.whatsapp_service import send_whatsapp_message

    branding = await get_branding_context(db, clinic_id=depense.clinic_id)
    fournisseur = extraction.get("fournisseur_nom", "Fournisseur inconnu")
    total_ttc = extraction.get("total_ttc", "N/A")

    message = (
        f"{branding['clinic_name']} — Facture {fournisseur} analysée — {total_ttc} TND\n"
        f"Vérifiez et validez dans l'app ✅"
    )

    result = await db.execute(
        select(Utilisateur.telephone)
        .where(Utilisateur.role == RoleEnum.DIRECTRICE.value)
        .where(Utilisateur.clinic_id == depense.clinic_id)
        .where(Utilisateur.is_active)
        .limit(1)
    )
    phone = result.scalar_one_or_none()

    if phone:
        await send_whatsapp_message(phone, message)


async def valider_depense(
    depense_id: int,
    validateur_id: int,
    corrections: Optional[dict],
    db: AsyncSession,
    clinic_id: int | None = None,
) -> Depense:
    """Valide une dépense avec corrections optionnelles.

    Applique les corrections sur l'extraction IA.
    Si lignes contiennent médicaments → propose création lot injectable.
    """
    clinic_id = _resolve_clinic(clinic_id)
    result = await db.execute(select(Depense).where(
        Depense.id == depense_id,
        Depense.clinic_id == clinic_id,
    ))
    depense = result.scalar_one_or_none()
    if not depense:
        raise ValueError("Dépense non trouvée")

    if depense.facture_scan_statut not in (StatutDepense.TRAITEE_IA.value, StatutDepense.EN_ATTENTE.value):
        raise ValueError(f"Statut invalide pour validation : {depense.facture_scan_statut}")

    # Appliquer corrections
    if corrections:
        if "fournisseur" in corrections:
            depense.fournisseur = corrections["fournisseur"]
        if "montant_ht" in corrections:
            depense.montant_ht = Decimal(str(corrections["montant_ht"]))
        if "montant_tva" in corrections:
            depense.montant_tva = Decimal(str(corrections["montant_tva"]))
        if "montant_ttc" in corrections:
            depense.montant_ttc = Decimal(str(corrections["montant_ttc"]))
        if "titre" in corrections:
            depense.titre = corrections["titre"]
        if "categorie_id" in corrections:
            depense.categorie_id = corrections["categorie_id"]

    # Si extraction IA existe, tenter auto-remplissage
    if depense.extraction_ia and isinstance(depense.extraction_ia, dict):
        ext = depense.extraction_ia
        if not depense.fournisseur and ext.get("fournisseur_nom"):
            depense.fournisseur = ext["fournisseur_nom"]
        if depense.montant_ht == Decimal("0.000") and ext.get("total_ht"):
            depense.montant_ht = Decimal(str(ext["total_ht"]))
        if depense.montant_tva == Decimal("0.000") and ext.get("total_tva"):
            depense.montant_tva = Decimal(str(ext["total_tva"]))
        if depense.montant_ttc == Decimal("0.000") and ext.get("total_ttc"):
            depense.montant_ttc = Decimal(str(ext["total_ttc"]))
        if not depense.titre and ext.get("numero_facture"):
            depense.titre = f"Facture {ext['numero_facture']}"

    # Vérifier si médicaments présents
    medicaments = []
    if depense.extraction_ia and isinstance(depense.extraction_ia, dict):
        lignes = depense.extraction_ia.get("lignes", [])
        for ligne in lignes:
            if ligne.get("est_medicament"):
                medicaments.append(ligne)

    depense.facture_scan_statut = StatutDepense.VALIDEE.value
    depense.valide_par_id = validateur_id
    depense.validated_at = datetime.utcnow()
    await db.flush()

    return depense, medicaments
