"""Tests — services/branding.py"""
import io

import pytest
from PIL import Image

from services.branding import get_branding, update_branding, save_logo, DEFAULT_BRANDING


def _png_bytes(w=100, h=100):
    img = Image.new("RGB", (w, h), color=(10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_get_branding_returns_defaults_when_unset(db):
    branding = await get_branding(db)
    assert branding["nom_clinique"] == DEFAULT_BRANDING["nom_clinique"]


@pytest.mark.asyncio
async def test_update_branding_persists_partial_change(db):
    await update_branding({"nom_clinique": "Clinique Ennasr"}, db)
    branding = await get_branding(db)
    assert branding["nom_clinique"] == "Clinique Ennasr"
    # les autres champs restent aux valeurs par défaut
    assert branding["couleur_primaire"] == DEFAULT_BRANDING["couleur_primaire"]


@pytest.mark.asyncio
async def test_update_branding_merges_contenu_landing(db):
    await update_branding({"contenu_landing": {"titre": "Bienvenue chez nous"}}, db)
    await update_branding({"contenu_landing": {"telephone": "+21671000000"}}, db)

    branding = await get_branding(db)
    assert branding["contenu_landing"]["titre"] == "Bienvenue chez nous"
    assert branding["contenu_landing"]["telephone"] == "+21671000000"


def test_save_logo_rejects_disallowed_mimetype(tmp_path, monkeypatch):
    from config import get_settings
    monkeypatch.setattr(get_settings(), "branding_dir", tmp_path)
    with pytest.raises(ValueError, match="MIME"):
        save_logo(b"peu importe", "application/pdf")


def test_save_logo_rejects_non_image_content(tmp_path, monkeypatch):
    from config import get_settings
    monkeypatch.setattr(get_settings(), "branding_dir", tmp_path)
    with pytest.raises(ValueError, match="pas une image valide"):
        save_logo(b"pas une image", "image/png")


def test_save_logo_rejects_mismatched_content(tmp_path, monkeypatch):
    from config import get_settings
    monkeypatch.setattr(get_settings(), "branding_dir", tmp_path)
    with pytest.raises(ValueError, match="ne correspond pas"):
        save_logo(_png_bytes(), "image/jpeg")


def test_save_logo_succeeds_and_returns_url(tmp_path, monkeypatch):
    from config import get_settings
    monkeypatch.setattr(get_settings(), "branding_dir", tmp_path)
    url = save_logo(_png_bytes(), "image/png")
    assert url.startswith("/static/branding/logo-")
    assert url.endswith(".png")


def test_save_logo_rejects_oversized_file(tmp_path, monkeypatch):
    from config import get_settings
    monkeypatch.setattr(get_settings(), "branding_dir", tmp_path)
    oversized = _png_bytes(3000, 3000)  # PNG non compressé d'une grande image
    if len(oversized) <= 2 * 1024 * 1024:
        pytest.skip("image de test pas assez volumineuse sur cet environnement")
    with pytest.raises(ValueError, match="volumineux"):
        save_logo(oversized, "image/png")
