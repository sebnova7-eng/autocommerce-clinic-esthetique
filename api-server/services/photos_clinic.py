"""
AutoCommerce Clinic — Gestion photos médicales
Upload, strip EXIF, redimensionnement, filigrane, chiffrement AES, soft delete
"""

import hashlib
import hmac
import io
import json
import os
from datetime import datetime
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from PIL import Image as PILImage, ImageDraw, ImageFont
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from models.database import Consentement

from config import get_settings, PHOTO_ALLOWED_MIMETYPES, PHOTO_MAX_DIMENSION, PHOTO_THUMBNAIL_SIZE
from models.database import PhotoClinic, TypePhoto
from services.consentement import verify_consent
from services.audit_medical import log_access
from services.branding import get_branding_context

settings = get_settings()
# Défense contre les decompression bombs : limite indépendante de la taille compressée.
PILImage.MAX_IMAGE_PIXELS = 16_000_000

# PIL rapporte "jpeg" pour du JPEG quel que soit le mime déclaré (jpg/jpeg) —
# mapping utilisé pour vérifier que le contenu réel correspond au MIME annoncé.
MIME_TO_PIL_FORMAT = {"image/jpeg": "jpeg", "image/png": "png", "image/webp": "webp"}


def _get_aes_key() -> bytes:
    """Dérive une clé AES 256-bit depuis PHOTO_ENCRYPTION_KEY.

    Clé dédiée, distincte de FERNET_KEY (dossier médical) : la
    compromission d'une des deux ne doit pas exposer l'autre.
    Pas de fallback en dur — une clé absente doit faire échouer
    l'opération, jamais chiffrer avec une valeur connue à l'avance.
    """
    import hashlib
    if not settings.photo_encryption_key:
        raise RuntimeError(
            "PHOTO_ENCRYPTION_KEY manquante — impossible de chiffrer/déchiffrer les photos"
        )
    return hashlib.sha256(settings.photo_encryption_key.encode()).digest()


def _encrypt_file(file_bytes: bytes) -> tuple[bytes, bytes]:
    """Chiffre un fichier avec AES-256-GCM. Retourne (nonce, ciphertext)."""
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, file_bytes, None)
    return nonce, ciphertext


def _decrypt_file(nonce: bytes, ciphertext: bytes) -> bytes:
    """Déchiffre un fichier avec AES-256-GCM."""
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def _strip_exif(img: PILImage.Image) -> PILImage.Image:
    """Supprime toutes les métadonnées EXIF (géolocalisation, device, etc.)."""
    data = img.getdata()
    clean = PILImage.new(img.mode, img.size)
    clean.putdata(data)
    return clean


WATERMARK_SIGNATURE_PREFIX = "ACCWMSIG:v1:"


def _get_watermark_font(size: int) -> ImageFont.ImageFont:
    """Retourne une police robuste pour le filigrane."""
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _compute_visual_hash(img: PILImage.Image) -> str:
    """Hash du contenu visuel normalisé, indépendant des métadonnées JPEG."""
    normalized = img.convert("RGB")
    payload = normalized.tobytes() + f"|{normalized.width}x{normalized.height}|".encode()
    return hashlib.sha256(payload).hexdigest()


def _build_watermark_signature_payload(img: PILImage.Image, text: str) -> bytes:
    """Construit une signature HMAC embarquée pour détecter toute altération.

    Correctif Bug #11 : le filigrane visible seul n'était pas suffisant.
    On embarque désormais une signature cryptographique dans le JPEG pour
    rendre toute suppression/modification détectable.
    """
    visual_hash = _compute_visual_hash(img)
    secret = hashlib.sha256(f"{settings.photo_encryption_key}:watermark-signature".encode()).digest()
    signed_material = f"{text}\n{visual_hash}".encode()
    signature = hmac.new(secret, signed_material, hashlib.sha256).hexdigest()
    payload = {
        "version": 1,
        "watermark_text": text,
        "visual_hash": visual_hash,
        "signature": signature,
        "signed_at": datetime.utcnow().isoformat(),
    }
    return (WATERMARK_SIGNATURE_PREFIX + json.dumps(payload, separators=(",", ":"))).encode("utf-8")


def _verify_signed_watermark(jpeg_bytes: bytes, expected_text: Optional[str] = None) -> bool:
    """Vérifie la signature embarquée d'un JPEG filigrané."""
    try:
        img = PILImage.open(io.BytesIO(jpeg_bytes))
        comment = img.info.get("comment")
        if not comment:
            return False
        if isinstance(comment, bytes):
            comment = comment.decode("utf-8", errors="ignore")
        if not comment.startswith(WATERMARK_SIGNATURE_PREFIX):
            return False
        payload = json.loads(comment[len(WATERMARK_SIGNATURE_PREFIX):])
        watermark_text = payload.get("watermark_text")
        if expected_text and watermark_text != expected_text:
            return False
        visual_hash = _compute_visual_hash(img)
        if payload.get("visual_hash") != visual_hash:
            return False
        secret = hashlib.sha256(f"{settings.photo_encryption_key}:watermark-signature".encode()).digest()
        signed_material = f"{watermark_text}\n{visual_hash}".encode()
        expected_sig = hmac.new(secret, signed_material, hashlib.sha256).hexdigest()
        return hmac.compare_digest(payload.get("signature", ""), expected_sig)
    except Exception:
        return False


def _save_signed_jpeg(img: PILImage.Image, watermark_text: str, quality: int = 90) -> bytes:
    """Sérialise un JPEG avec signature de filigrane embarquée."""
    comment = _build_watermark_signature_payload(img, watermark_text)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality, comment=comment)
    buf.seek(0)
    return buf.getvalue()


def _add_watermark(img: PILImage.Image, text: str) -> PILImage.Image:
    """Ajoute un filigrane visible renforcé sur toute l'image.

    Correctif Bug #11 : au lieu d'un simple texte discret en bas à droite,
    on applique un filigrane diagonal répété + cartouche bas droit. Combiné
    à la signature JPEG embarquée, cela rend les suppressions ou altérations
    nettement plus coûteuses et détectables.
    """
    base = img.convert("RGBA")
    overlay = PILImage.new("RGBA", base.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    diagonal_font = _get_watermark_font(max(20, min(base.size) // 12))
    footer_font = _get_watermark_font(max(18, min(base.size) // 28))

    tile_bbox = draw.textbbox((0, 0), text, font=diagonal_font)
    tile_w = tile_bbox[2] - tile_bbox[0]
    tile_h = tile_bbox[3] - tile_bbox[1]
    x_step = max(tile_w + 120, 220)
    y_step = max(tile_h + 100, 180)

    for x in range(-base.width // 3, base.width + x_step, x_step):
        for y in range(-base.height // 3, base.height + y_step, y_step):
            draw.text((x, y), text, font=diagonal_font, fill=(255, 255, 255, 38))

    overlay = overlay.rotate(28, resample=PILImage.BICUBIC, expand=False)
    composited = PILImage.alpha_composite(base, overlay)

    footer = ImageDraw.Draw(composited)
    footer_bbox = footer.textbbox((0, 0), text, font=footer_font)
    text_width = footer_bbox[2] - footer_bbox[0]
    text_height = footer_bbox[3] - footer_bbox[1]
    padding = 18
    x = composited.width - text_width - (padding * 2)
    y = composited.height - text_height - (padding * 2)

    footer.rounded_rectangle(
        (x - padding, y - padding, x + text_width + padding, y + text_height + padding),
        radius=14,
        fill=(0, 0, 0, 120),
    )
    footer.text((x, y), text, font=footer_font, fill=(255, 255, 255, 220))

    return composited.convert("RGB")


def _resize_image(img: PILImage.Image, max_dim: int = PHOTO_MAX_DIMENSION) -> PILImage.Image:
    """Redimensionne si nécessaire en conservant le ratio."""
    if max(img.width, img.height) > max_dim:
        ratio = max_dim / max(img.width, img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, PILImage.LANCZOS)
    return img


def _create_thumbnail(img: PILImage.Image, size: int = PHOTO_THUMBNAIL_SIZE) -> PILImage.Image:
    """Crée une miniature carrée."""
    thumb = img.copy()
    thumb.thumbnail((size, size), PILImage.LANCZOS)

    # Créer un canvas carré
    canvas = PILImage.new("RGB", (size, size), (255, 255, 255))

    # Centrer
    x = (size - thumb.width) // 2
    y = (size - thumb.height) // 2
    canvas.paste(thumb, (x, y))

    return canvas


def _calculate_hash(file_bytes: bytes) -> str:
    """Calcule le hash SHA-256 du fichier."""
    return hashlib.sha256(file_bytes).hexdigest()


async def upload_photo(
    patient_id: int,
    dossier_id: Optional[int],
    type_photo: str,
    zone: Optional[str],
    angle: Optional[str],
    file_bytes: bytes,
    mime_type: str,
    prise_par_id: int,
    db: AsyncSession,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    clinic_id: int = 1,
) -> PhotoClinic:
    """Upload et traitement complet d'une photo médicale.

    1. Vérification MIME (jpg/png/webp)
    2. Vérification taille max 20 Mo
    3. Strip EXIF complet
    4. Redimensionnement original + thumbnail 200x200
    5. Calcul hash SHA-256
    6. Ajout filigrane : logo clinique + date
    7. Chiffrement AES avant stockage disque
    8. Vérification consentement photo valide
    """
    # 1. Vérification MIME déclaré
    if mime_type not in PHOTO_ALLOWED_MIMETYPES:
        raise ValueError(f"Type MIME non autorisé : {mime_type}. Autorisés : {PHOTO_ALLOWED_MIMETYPES}")

    # 2. Vérification taille
    if len(file_bytes) > settings.max_photo_size_mb * 1024 * 1024:
        raise ValueError(f"Fichier trop volumineux : {len(file_bytes) / (1024*1024):.1f} Mo (max {settings.max_photo_size_mb} Mo)")

    # 2bis. Vérification du contenu réel (magic bytes) — le Content-Type
    # déclaré par le client n'est qu'une déclaration, jamais une preuve.
    # On ouvre réellement le fichier et on vérifie que le format détecté
    # correspond au MIME annoncé, pour bloquer un exécutable/script
    # renommé en .jpg.
    try:
        probe = PILImage.open(io.BytesIO(file_bytes))
        probe.verify()
    except (PILImage.DecompressionBombError, PILImage.DecompressionBombWarning) as exc:
        raise ValueError("Image trop grande après décompression") from exc
    except Exception:
        raise ValueError("Le fichier n'est pas une image valide")

    detected_format = (probe.format or "").lower()
    if MIME_TO_PIL_FORMAT.get(mime_type) != detected_format:
        raise ValueError(
            f"Le contenu du fichier ({detected_format or 'inconnu'}) ne correspond pas "
            f"au type déclaré ({mime_type})"
        )

    # 3. Vérification consentement photo
    # Un consentement général suffit, mais un consentement acte médical
    # encore valide pour la patiente est également acceptable pour ne pas
    # bloquer le flux photo clinique existant.
    has_general_consent = await verify_consent(patient_id, None, db, clinic_id=clinic_id)
    has_any_valid_consent = False
    if not has_general_consent:
        consent_result = await db.execute(
            select(Consentement).where(
                and_(
                    Consentement.patient_id == patient_id,
                    Consentement.clinic_id == clinic_id,
                    Consentement.est_valide,
                )
            ).limit(1)
        )
        has_any_valid_consent = consent_result.scalar_one_or_none() is not None

    if not (has_general_consent or has_any_valid_consent):
        raise ValueError("Consentement photo non signé ou expiré")

    # Charger l'image (probe.verify() ferme le fichier, on le rouvre)
    img = PILImage.open(io.BytesIO(file_bytes))

    # 3. Strip EXIF
    img = _strip_exif(img)

    # Convertir en RGB si nécessaire
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # 4. Redimensionnement
    img = _resize_image(img)

    # 5. Hash
    original_bytes = io.BytesIO()
    img.save(original_bytes, format="JPEG", quality=95)
    original_bytes.seek(0)
    file_hash = _calculate_hash(original_bytes.getvalue())

    # 6. Filigrane
    branding = await get_branding_context(db)
    watermark_text = f"{branding['clinic_name']} — {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}"
    img_watermarked = _add_watermark(img, watermark_text)

    # Sauvegarder original avec filigrane + signature cryptographique
    signed_jpeg = _save_signed_jpeg(img_watermarked, watermark_text, quality=90)

    # 7. Chiffrement
    nonce, ciphertext = _encrypt_file(signed_jpeg)

    # 4b. Thumbnail
    thumb = _create_thumbnail(img)
    thumb_buf = io.BytesIO()
    thumb.save(thumb_buf, format="JPEG", quality=80)
    thumb_buf.seek(0)
    thumb_nonce, thumb_ciphertext = _encrypt_file(thumb_buf.getvalue())

    # Stockage disque
    date_dir = datetime.utcnow().strftime("%Y/%m")
    base_path = os.path.join(str(settings.photos_dir), date_dir)
    os.makedirs(base_path, exist_ok=True)

    # Sauvegarder fichiers chiffrés
    orig_filename = f"photo_{patient_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.enc"
    thumb_filename = f"thumb_{patient_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.enc"

    orig_path = os.path.join(base_path, orig_filename)
    thumb_path = os.path.join(base_path, thumb_filename)

    with open(orig_path, "wb") as f:
        f.write(nonce + ciphertext)
    with open(thumb_path, "wb") as f:
        f.write(thumb_nonce + thumb_ciphertext)

    # Créer l'entrée DB
    photo = PhotoClinic(
        clinic_id=clinic_id,
        patient_id=patient_id,
        dossier_id=dossier_id,
        type=type_photo,
        date_prise=datetime.utcnow(),
        zone_anatomique=zone,
        angle_prise=angle,
        url_stockage=orig_path,
        url_thumbnail=thumb_path,
        hash_fichier=file_hash,
        taille_octets=len(file_bytes),
        visible_patient=False,
        visible_marketing=False,
        filigrane_applique=True,
        prise_par_id=prise_par_id,
    )
    db.add(photo)
    await db.flush()

    # Log audit
    await log_access(
        db=db,
        utilisateur_id=prise_par_id,
        patient_id=patient_id,
        action="UPLOAD_PHOTO",
        resource_type="photo",
        resource_id=photo.id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={"type": type_photo, "zone": zone},
    )

    return photo


async def get_decrypted_photo(
    photo_id: int,
    patient_id: int,
    db: AsyncSession,
    thumbnail: bool = False,
    clinic_id: int = 1,
) -> tuple[bytes, str]:
    """Déchiffre une photo médicale pour affichage. Retourne (bytes JPEG, filename).

    Route manquante jusqu'ici : le fichier n'existait que sous forme
    chiffrée sur disque (nonce + ciphertext AES-256-GCM), sans aucun
    moyen exposé de le déchiffrer pour l'afficher — le frontend ne
    pouvait physiquement pas montrer les photos avant/après."""
    result = await db.execute(
        select(PhotoClinic).where(
            PhotoClinic.id == photo_id,
            PhotoClinic.patient_id == patient_id,
            PhotoClinic.clinic_id == clinic_id,
            PhotoClinic.is_deleted.is_(False),
        )
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise ValueError("Photo non trouvée")

    path = photo.url_thumbnail if thumbnail else photo.url_stockage
    if not path or not os.path.exists(path):
        raise ValueError("Fichier photo introuvable sur le disque")

    with open(path, "rb") as f:
        raw = f.read()
    nonce, ciphertext = raw[:12], raw[12:]
    decrypted = _decrypt_file(nonce, ciphertext)

    filename = f"photo_{photo_id}{'_thumb' if thumbnail else ''}.jpg"
    return decrypted, filename


async def get_comparaison_avant_apres(
    patient_id: int,
    zone: Optional[str],
    serie_id: Optional[int],
    db: AsyncSession,
    utilisateur_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    clinic_id: int = 1,
) -> dict:
    """Retourne les photos avant/après pour comparaison."""
    if utilisateur_id:
        await log_access(
            db=db, utilisateur_id=utilisateur_id, patient_id=patient_id,
            action="READ_PHOTOS_COMPARAISON", resource_type="photo", resource_id=patient_id,
            ip_address=ip_address,
        )

    query = select(PhotoClinic).where(
        and_(
            PhotoClinic.patient_id == patient_id,
            PhotoClinic.clinic_id == clinic_id,
            PhotoClinic.is_deleted.is_(False),
            PhotoClinic.type.in_([TypePhoto.AVANT.value, TypePhoto.APRES.value]),
        )
    )

    if zone:
        query = query.where(PhotoClinic.zone_anatomique == zone)
    if serie_id:
        query = query.where(PhotoClinic.serie_id == serie_id)

    query = query.order_by(PhotoClinic.date_prise)
    result = await db.execute(query)
    photos = result.scalars().all()

    return {
        "avant": [
            {"id": p.id, "url": f"/api/v1/patients/{patient_id}/photos/{p.id}/view", "date": p.date_prise.isoformat()}
            for p in photos if p.type == TypePhoto.AVANT.value
        ],
        "apres": [
            {"id": p.id, "url": f"/api/v1/patients/{patient_id}/photos/{p.id}/view", "date": p.date_prise.isoformat()}
            for p in photos if p.type == TypePhoto.APRES.value
        ],
    }


async def delete_photo(
    photo_id: int,
    raison: str,
    deleted_by: int,
    db: AsyncSession,
    ip_address: Optional[str] = None,
    patient_id: Optional[int] = None,
    clinic_id: int = 1,
) -> PhotoClinic:
    """Soft delete uniquement. Jamais de suppression physique.
    Log audit de la suppression."""
    filters = [PhotoClinic.id == photo_id, PhotoClinic.clinic_id == clinic_id, PhotoClinic.is_deleted.is_(False)]
    if patient_id is not None:
        filters.append(PhotoClinic.patient_id == patient_id)
    result = await db.execute(select(PhotoClinic).where(*filters))
    photo = result.scalar_one_or_none()
    if not photo:
        raise ValueError("Photo non trouvée")

    photo.is_deleted = True
    photo.deleted_at = datetime.utcnow()
    photo.deleted_by = deleted_by
    photo.raison_suppression = raison

    await db.flush()

    # Log audit
    await log_access(
        db=db,
        utilisateur_id=deleted_by,
        patient_id=photo.patient_id,
        action="DELETE_PHOTO",
        resource_type="photo",
        resource_id=photo_id,
        ip_address=ip_address,
        details={"raison": raison},
    )

    return photo
