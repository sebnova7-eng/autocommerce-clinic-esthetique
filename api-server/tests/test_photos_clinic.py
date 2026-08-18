"""Tests — services/photos_clinic.py

Couvre le chiffrement AES-256-GCM des fichiers, le pipeline de
traitement d'image (resize/thumbnail/EXIF), le garde-fou consentement
avant upload, et le soft-delete (jamais de suppression physique).
"""
import io

import pytest
from PIL import Image

from services.photos_clinic import (
    _encrypt_file, _decrypt_file, _resize_image, _create_thumbnail,
    _calculate_hash, _strip_exif, upload_photo, delete_photo,
)
from models.database import PhotoClinic
from sqlalchemy import select


def _make_test_image(width=500, height=400, fmt="JPEG"):
    img = Image.new("RGB", (width, height), color=(120, 60, 200))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf.getvalue()


# ── Chiffrement fichier (AES-256-GCM) ────────────────────────

def test_encrypt_decrypt_file_roundtrip():
    data = b"contenu binaire d'une photo"
    nonce, ciphertext = _encrypt_file(data)
    assert _decrypt_file(nonce, ciphertext) == data


def test_encrypt_file_produces_different_ciphertext_each_time():
    """Le nonce aléatoire garantit un ciphertext différent à chaque appel,
    même pour un contenu identique."""
    data = b"meme contenu"
    _, c1 = _encrypt_file(data)
    _, c2 = _encrypt_file(data)
    assert c1 != c2


def test_decrypt_with_wrong_nonce_fails():
    data = b"contenu"
    nonce, ciphertext = _encrypt_file(data)
    _, other_nonce = _encrypt_file(b"autre")
    with pytest.raises(Exception):
        _decrypt_file(other_nonce, ciphertext)


# ── Traitement image ──────────────────────────────────────────

def test_resize_image_shrinks_oversized_image():
    img = Image.new("RGB", (5000, 3000))
    resized = _resize_image(img, max_dim=4096)
    assert max(resized.width, resized.height) <= 4096


def test_resize_image_preserves_aspect_ratio():
    img = Image.new("RGB", (4000, 2000))
    resized = _resize_image(img, max_dim=2000)
    assert resized.width == 2000
    assert resized.height == 1000


def test_resize_image_leaves_small_image_untouched():
    img = Image.new("RGB", (300, 200))
    resized = _resize_image(img, max_dim=4096)
    assert (resized.width, resized.height) == (300, 200)


def test_create_thumbnail_is_square():
    img = Image.new("RGB", (800, 400))
    thumb = _create_thumbnail(img, size=200)
    assert thumb.size == (200, 200)


def test_calculate_hash_is_deterministic():
    data = b"same bytes"
    assert _calculate_hash(data) == _calculate_hash(data)


def test_calculate_hash_differs_for_different_content():
    assert _calculate_hash(b"a") != _calculate_hash(b"b")


def test_strip_exif_returns_same_dimensions():
    img = Image.new("RGB", (100, 100))
    stripped = _strip_exif(img)
    assert stripped.size == img.size


# ── upload_photo : garde-fous ─────────────────────────────────

@pytest.mark.asyncio
async def test_upload_photo_rejects_disallowed_mimetype(db, patient, medecin):
    with pytest.raises(ValueError, match="MIME"):
        await upload_photo(
            patient_id=patient.id, dossier_id=None, type_photo="avant",
            zone="visage", angle=None, file_bytes=_make_test_image(),
            mime_type="application/pdf", prise_par_id=medecin.id, db=db,
        )


@pytest.mark.asyncio
async def test_upload_photo_rejects_non_image_content_disguised_as_jpeg(db, patient, medecin, consentement_valide):
    """Fichier qui n'est PAS une image, mais annoncé comme image/jpeg —
    doit être bloqué par la vérification du contenu réel, pas seulement
    par le Content-Type déclaré (qu'un client peut mentir)."""
    fake_bytes = b"#!/bin/sh\necho not an image\n"
    with pytest.raises(ValueError, match="pas une image valide"):
        await upload_photo(
            patient_id=patient.id, dossier_id=None, type_photo="avant",
            zone=None, angle=None, file_bytes=fake_bytes,
            mime_type="image/jpeg", prise_par_id=medecin.id, db=db,
        )


@pytest.mark.asyncio
async def test_upload_photo_rejects_mismatched_declared_mimetype(db, patient, medecin, consentement_valide):
    """Vraie image PNG, mais déclarée comme image/jpeg — le contenu réel
    doit primer sur la déclaration du client."""
    png_bytes = _make_test_image(fmt="PNG")
    with pytest.raises(ValueError, match="ne correspond pas"):
        await upload_photo(
            patient_id=patient.id, dossier_id=None, type_photo="avant",
            zone=None, angle=None, file_bytes=png_bytes,
            mime_type="image/jpeg", prise_par_id=medecin.id, db=db,
        )


@pytest.mark.asyncio
async def test_upload_photo_rejects_file_too_large(db, patient, medecin, monkeypatch):
    from config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "max_photo_size_mb", 1)

    oversized = b"0" * (2 * 1024 * 1024)  # 2 Mo > 1 Mo autorisé
    with pytest.raises(ValueError, match="volumineux"):
        await upload_photo(
            patient_id=patient.id, dossier_id=None, type_photo="avant",
            zone=None, angle=None, file_bytes=oversized,
            mime_type="image/jpeg", prise_par_id=medecin.id, db=db,
        )


@pytest.mark.asyncio
async def test_upload_photo_rejects_without_consent(db, patient, medecin):
    with pytest.raises(ValueError, match="[Cc]onsentement"):
        await upload_photo(
            patient_id=patient.id, dossier_id=None, type_photo="avant",
            zone=None, angle=None, file_bytes=_make_test_image(),
            mime_type="image/jpeg", prise_par_id=medecin.id, db=db,
        )


@pytest.mark.asyncio
async def test_upload_photo_succeeds_with_consent(db, patient, medecin, consentement_valide, tmp_path, monkeypatch):
    from config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "photos_dir", tmp_path)

    photo = await upload_photo(
        patient_id=patient.id, dossier_id=None, type_photo="avant",
        zone="visage", angle="face", file_bytes=_make_test_image(),
        mime_type="image/jpeg", prise_par_id=medecin.id, db=db,
    )
    assert photo.id is not None
    assert photo.filigrane_applique is True
    assert photo.visible_patient is False  # invisible au patient par défaut
    assert photo.hash_fichier is not None


# ── Soft delete ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_photo_is_soft_delete_only(db, patient, medecin, consentement_valide, tmp_path, monkeypatch):
    from config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "photos_dir", tmp_path)

    photo = await upload_photo(
        patient_id=patient.id, dossier_id=None, type_photo="avant",
        zone=None, angle=None, file_bytes=_make_test_image(),
        mime_type="image/jpeg", prise_par_id=medecin.id, db=db,
    )
    deleted = await delete_photo(photo.id, raison="Erreur de zone", deleted_by=medecin.id, db=db)

    assert deleted.is_deleted is True
    assert deleted.raison_suppression == "Erreur de zone"

    # La ligne existe toujours en base (pas de suppression physique)
    result = await db.execute(select(PhotoClinic).where(PhotoClinic.id == photo.id))
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_delete_unknown_photo_raises(db, medecin):
    with pytest.raises(ValueError, match="non trouvée"):
        await delete_photo(999999, raison="x", deleted_by=medecin.id, db=db)


@pytest.mark.asyncio
async def test_get_comparaison_logs_read_access_when_user_provided(db, patient, medecin):
    from services.photos_clinic import get_comparaison_avant_apres
    from models.database import AuditLogMedical
    from sqlalchemy import select

    await get_comparaison_avant_apres(patient.id, None, None, db,
                                       utilisateur_id=medecin.id, ip_address="10.0.0.5")

    result = await db.execute(select(AuditLogMedical).where(AuditLogMedical.action == "READ_PHOTOS_COMPARAISON"))
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.utilisateur_id == medecin.id
