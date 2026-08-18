"""
AutoCommerce Clinic — Génération QR Code, Code-barre et étiquettes
pour lots injectables.
Formats dual : QR (scan tablette) + Code 128 (scan douchette)
"""

import json
import io
from typing import List

import qrcode
from qrcode.constants import ERROR_CORRECT_H
from barcode import Code128
from barcode.writer import ImageWriter
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import LotInjectable, ProduitInjectable
from services.branding import get_branding_context


# ── QR Code ────────────────────────────────────────────────

async def generate_lot_qr(lot_id: int, db: AsyncSession) -> bytes:
    """Génère un QR code PNG 300x300px pour un lot.

    Payload JSON : {lot_id, product_id, numero_lot, date_expiration, clinic_id}
    Error correction H, noir sur blanc.
    """
    result = await db.execute(
        select(LotInjectable, ProduitInjectable)
        .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
        .where(LotInjectable.id == lot_id)
    )
    row = result.first()
    if not row:
        raise ValueError(f"Lot {lot_id} non trouvé")

    lot, produit = row

    payload = {
        "lot_id": lot.id,
        "product_id": lot.produit_id,
        "numero_lot": lot.numero_lot,
        "date_expiration": lot.date_expiration.isoformat(),
        "clinic_id": lot.clinic_id,
    }

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(json.dumps(payload))
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((300, 300), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


# ── Code-barre Code 128 ────────────────────────────────────

async def generate_lot_barcode(lot_id: int, db: AsyncSession) -> bytes:
    """Génère un code-barre Code 128 PNG 400x100px, 300 DPI.
    Encode uniquement le numéro de lot.
    """
    result = await db.execute(
        select(LotInjectable).where(LotInjectable.id == lot_id)
    )
    lot = result.scalar_one_or_none()
    if not lot:
        raise ValueError(f"Lot {lot_id} non trouvé")

    # Générer le code-barre
    code128 = Code128(lot.numero_lot, writer=ImageWriter())

    # Options de rendu
    options = {
        "module_width": 0.4,      # mm
        "module_height": 15.0,    # mm
        "quiet_zone": 6.0,        # mm
        "font_size": 14,
        "text_distance": 4.0,     # mm
        "background": "white",
        "foreground": "black",
        "write_text": True,
    }

    buf = io.BytesIO()
    code128.write(buf, options)
    buf.seek(0)

    # Redimensionner à 400x100px
    img = Image.open(buf)
    img = img.convert("RGB")
    img = img.resize((400, 100), Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="PNG", dpi=(300, 300))
    out.seek(0)
    return out.getvalue()


# ── Étiquette PDF ──────────────────────────────────────────

LABEL_FORMATS = {
    "a4": {"width": 210, "height": 297, "cols": 2, "rows": 2, "margin": 10},
    "50x30": {"width": 50, "height": 30, "cols": 1, "rows": 1, "margin": 2},
    "40x25": {"width": 40, "height": 25, "cols": 1, "rows": 1, "margin": 2},
    "60x40": {"width": 60, "height": 40, "cols": 1, "rows": 1, "margin": 2},
}


async def generate_lot_label(
    lot_id: int,
    db: AsyncSession,
    label_format: str = "50x30",
) -> bytes:
    """Génère une étiquette PDF pour un lot.

    Contient : nom clinique, nom produit, numéro lot, date expiration,
    QR code (scan tablette), code-barre Code 128 (scan douchette).
    """
    if label_format not in LABEL_FORMATS:
        raise ValueError(f"Format inconnu : {label_format}. Disponibles : {list(LABEL_FORMATS.keys())}")

    result = await db.execute(
        select(LotInjectable, ProduitInjectable)
        .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
        .where(LotInjectable.id == lot_id)
    )
    row = result.first()
    if not row:
        raise ValueError(f"Lot {lot_id} non trouvé")

    lot, produit = row

    branding = await get_branding_context(db)
    clinic_name = branding["clinic_name"]

    fmt = LABEL_FORMATS[label_format]
    width_mm = fmt["width"]
    height_mm = fmt["height"]

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width_mm * mm, height_mm * mm))

    # Générer QR et barcode en mémoire
    qr_bytes = await generate_lot_qr(lot_id, db)
    barcode_bytes = await generate_lot_barcode(lot_id, db)

    qr_img = ImageReader(io.BytesIO(qr_bytes))
    barcode_img = ImageReader(io.BytesIO(barcode_bytes))

    if label_format == "a4":
        # 4 étiquettes par page A4
        _draw_a4_label_page(c, lot, produit, clinic_name, qr_img, barcode_img, fmt)
    else:
        # Étiquette unique
        _draw_single_label(c, lot, produit, clinic_name, qr_img, barcode_img, width_mm, height_mm)

    c.save()
    buf.seek(0)
    return buf.getvalue()


def _draw_single_label(c, lot, produit, clinic_name, qr_img, barcode_img, width_mm, height_mm):
    """Dessine une étiquette unique."""
    w = width_mm * mm
    h = height_mm * mm
    margin = 2 * mm

    # Nom clinique (haut, centré, petit)
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(w / 2, h - margin - 5, clinic_name[:35])

    # Nom produit
    c.setFont("Helvetica-Bold", 8)
    c.drawString(margin, h - margin - 15, produit.nom[:30])

    # Numéro lot
    c.setFont("Helvetica", 7)
    c.drawString(margin, h - margin - 25, f"Lot: {lot.numero_lot}")

    # Date expiration
    c.drawString(margin, h - margin - 33, f"Exp: {lot.date_expiration.strftime('%d/%m/%Y')}")

    # QR code (gauche, bas)
    qr_size = min(12 * mm, (w / 2) - margin)
    c.drawImage(qr_img, margin, margin, width=qr_size, height=qr_size)

    # Code-barre (droite, bas)
    bc_width = w - qr_size - (3 * margin)
    bc_height = 8 * mm
    c.drawImage(barcode_img, qr_size + (2 * margin), margin + 2, width=bc_width, height=bc_height)


def _draw_a4_label_page(c, lot, produit, clinic_name, qr_img, barcode_img, fmt):
    """Dessine 4 étiquettes sur une page A4."""
    cols, rows = fmt["cols"], fmt["rows"]
    margin = fmt["margin"] * mm

    label_w = (210 * mm - 2 * margin) / cols
    label_h = (297 * mm - 2 * margin) / rows

    for row in range(rows):
        for col in range(cols):
            x = margin + col * label_w
            y = 297 * mm - margin - (row + 1) * label_h

            # Cadre
            c.rect(x, y, label_w, label_h)

            # Contenu
            inner_margin = 3 * mm
            cx = x + inner_margin
            cy = y + label_h - inner_margin - 5

            c.setFont("Helvetica-Bold", 9)
            c.drawString(cx, cy, clinic_name[:40])

            c.setFont("Helvetica-Bold", 10)
            c.drawString(cx, cy - 12, produit.nom[:35])

            c.setFont("Helvetica", 8)
            c.drawString(cx, cy - 24, f"Lot: {lot.numero_lot}")
            c.drawString(cx, cy - 34, f"Exp: {lot.date_expiration.strftime('%d/%m/%Y')}")

            # QR
            qr_size = 20 * mm
            c.drawImage(qr_img, cx, y + inner_margin, width=qr_size, height=qr_size)

            # Barcode
            bc_w = label_w - qr_size - (3 * inner_margin)
            c.drawImage(barcode_img, cx + qr_size + inner_margin, y + inner_margin + 2, width=bc_w, height=12 * mm)

    c.showPage()


# ── Batch multi-étiquettes ─────────────────────────────────

async def generate_lot_label_batch(
    lot_ids: List[int],
    db: AsyncSession,
    label_format: str = "50x30",
) -> bytes:
    """Génère un PDF multi-étiquettes pour impression en masse."""
    if label_format not in LABEL_FORMATS:
        raise ValueError(f"Format inconnu : {label_format}")

    fmt = LABEL_FORMATS[label_format]
    buf = io.BytesIO()

    if label_format == "a4":
        c = canvas.Canvas(buf, pagesize=A4)
    else:
        w, h = fmt["width"] * mm, fmt["height"] * mm
        c = canvas.Canvas(buf, pagesize=(w, h))

    branding = await get_branding_context(db)
    clinic_name = branding["clinic_name"]

    for lot_id in lot_ids:
        result = await db.execute(
            select(LotInjectable, ProduitInjectable)
            .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
            .where(LotInjectable.id == lot_id)
        )
        row = result.first()
        if not row:
            continue

        lot, produit = row

        qr_bytes = await generate_lot_qr(lot_id, db)
        barcode_bytes = await generate_lot_barcode(lot_id, db)
        qr_img = ImageReader(io.BytesIO(qr_bytes))
        barcode_img = ImageReader(io.BytesIO(barcode_bytes))

        if label_format == "a4":
            _draw_a4_label_page(c, lot, produit, clinic_name, qr_img, barcode_img, fmt)
        else:
            _draw_single_label(c, lot, produit, clinic_name, qr_img, barcode_img, fmt["width"], fmt["height"])
            c.showPage()

    c.save()
    buf.seek(0)
    return buf.getvalue()


# ── Décodage scan ──────────────────────────────────────────

def decode_scan(code_str: str) -> dict:
    """Détecte automatiquement le format du scan.

    - Si commence par '{' → QR JSON → parser
    - Sinon → Code 128 → retourner le numéro de lot brut
    """
    code_str = code_str.strip()

    if code_str.startswith("{"):
        try:
            return {
                "type": "qr_json",
                "data": json.loads(code_str),
            }
        except json.JSONDecodeError:
            return {
                "type": "unknown",
                "raw": code_str,
                "error": "JSON invalide",
            }

    # Code 128 brut
    return {
        "type": "barcode",
        "numero_lot": code_str,
    }
