"""
AutoCommerce Clinic — Branding / configuration de la landing page

Une instance = un client, donc pas de multi-tenant : c'est un unique
enregistrement de configuration (clé "branding" dans ClinicSetting),
lu publiquement par la landing page et modifiable par la direction.
"""
import os
import uuid

from PIL import Image as PILImage
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from services.clinic_settings import get_setting, set_setting

settings = get_settings()

BRANDING_KEY = "branding"

DEFAULT_BRANDING = {
    "nom_clinique": "AutoCommerce Clinic",
    "logo_url": None,
    "couleur_primaire": "#0EA5A4",
    "couleur_secondaire": "#0F172A",
    "contenu_landing": {
        "titre": "Bienvenue",
        "sous_titre": "",
        "services_mis_en_avant": [],
        "adresse": "",
        "telephone": "",
        "horaires": "",
    },
}

LOGO_ALLOWED_MIMETYPES = {"image/jpeg", "image/png", "image/webp"}
MIME_TO_PIL_FORMAT = {"image/jpeg": "jpeg", "image/png": "png", "image/webp": "webp"}
MIME_TO_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_LOGO_SIZE_MB = 2


async def get_branding(db: AsyncSession, clinic_id: int | None = None) -> dict:
    stored = await get_setting(BRANDING_KEY, db, default=None, clinic_id=clinic_id)
    if not stored:
        return DEFAULT_BRANDING
    # merge superficiel : les clés absentes du stockage retombent sur le défaut
    merged = {**DEFAULT_BRANDING, **stored}
    merged["contenu_landing"] = {**DEFAULT_BRANDING["contenu_landing"], **stored.get("contenu_landing", {})}
    return merged


async def get_branding_context(db: AsyncSession, clinic_id: int | None = None) -> dict:
    """Retourne les valeurs branding déjà normalisées pour les services.

    Clés stables :
    - clinic_name
    - primary_color
    - secondary_color
    - address
    - phone
    - logo_url
    """
    branding = await get_branding(db, clinic_id=clinic_id)
    landing = branding.get("contenu_landing") or {}
    return {
        "clinic_name": branding.get("nom_clinique") or DEFAULT_BRANDING["nom_clinique"],
        "primary_color": branding.get("couleur_primaire") or DEFAULT_BRANDING["couleur_primaire"],
        "secondary_color": branding.get("couleur_secondaire") or DEFAULT_BRANDING["couleur_secondaire"],
        "address": landing.get("adresse") or "",
        "phone": landing.get("telephone") or "",
        "logo_url": branding.get("logo_url"),
    }


async def update_branding(data: dict, db: AsyncSession, clinic_id: int | None = None) -> dict:
    current = await get_branding(db, clinic_id=clinic_id)
    for key in ("nom_clinique", "logo_url", "couleur_primaire", "couleur_secondaire"):
        if key in data and data[key] is not None:
            current[key] = data[key]
    if "contenu_landing" in data and data["contenu_landing"]:
        current["contenu_landing"] = {**current["contenu_landing"], **data["contenu_landing"]}

    await set_setting(
        BRANDING_KEY,
        current,
        db,
        description="Branding et contenu de la landing page",
        clinic_id=clinic_id,
    )
    return current


def save_logo(file_bytes: bytes, mime_type: str, clinic_id: int | None = None) -> str:
    """Valide (taille + contenu réel via magic-bytes) puis enregistre le
    logo sur disque. Retourne l'URL relative à exposer publiquement.
    Pas de chiffrement : un logo n'est pas une donnée sensible."""
    if mime_type not in LOGO_ALLOWED_MIMETYPES:
        raise ValueError(f"Type MIME non autorisé : {mime_type}. Autorisés : {LOGO_ALLOWED_MIMETYPES}")

    if len(file_bytes) > MAX_LOGO_SIZE_MB * 1024 * 1024:
        raise ValueError(f"Logo trop volumineux (max {MAX_LOGO_SIZE_MB} Mo)")

    try:
        import io
        probe = PILImage.open(io.BytesIO(file_bytes))
        probe.verify()
    except Exception:
        raise ValueError("Le fichier n'est pas une image valide")

    detected_format = (probe.format or "").lower()
    if MIME_TO_PIL_FORMAT.get(mime_type) != detected_format:
        raise ValueError(
            f"Le contenu du fichier ({detected_format or 'inconnu'}) ne correspond pas "
            f"au type déclaré ({mime_type})"
        )

    if clinic_id is not None and int(clinic_id) <= 0:
        raise ValueError("clinic_id invalide")
    branding_dir = settings.branding_dir
    relative_dir = ""
    if clinic_id is not None:
        relative_dir = f"clinic-{int(clinic_id)}"
        branding_dir = branding_dir / relative_dir
    os.makedirs(str(branding_dir), exist_ok=True)
    filename = f"logo-{uuid.uuid4().hex[:12]}.{MIME_TO_EXT[mime_type]}"
    filepath = os.path.join(str(branding_dir), filename)
    with open(filepath, "wb") as f:
        f.write(file_bytes)

    return f"/static/branding/{relative_dir + '/' if relative_dir else ''}{filename}"
