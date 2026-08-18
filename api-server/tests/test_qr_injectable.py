"""Tests — services/qr_injectable.py (decode_scan) et
services/stock_injectable.get_lot_by_scan (double format QR/Code128).
"""
import json

import pytest

from services.qr_injectable import decode_scan
from services.stock_injectable import get_lot_by_scan


def test_decode_scan_qr_json():
    payload = json.dumps({"lot_id": 42, "numero_lot": "LOT-42"})
    result = decode_scan(payload)
    assert result["type"] == "qr_json"
    assert result["data"]["lot_id"] == 42


def test_decode_scan_barcode():
    result = decode_scan("LOT-0007")
    assert result["type"] == "barcode"
    assert result["numero_lot"] == "LOT-0007"


def test_decode_scan_invalid_json_reports_unknown():
    result = decode_scan("{not valid json")
    assert result["type"] == "unknown"
    assert "error" in result


def test_decode_scan_strips_whitespace():
    result = decode_scan("  LOT-0007  \n")
    assert result["numero_lot"] == "LOT-0007"


@pytest.mark.asyncio
async def test_get_lot_by_scan_via_barcode(db, lot):
    detail = await get_lot_by_scan(lot.numero_lot, db)
    assert detail.lot_id == lot.id
    assert detail.numero_lot == lot.numero_lot


@pytest.mark.asyncio
async def test_get_lot_by_scan_via_qr_json(db, lot):
    payload = json.dumps({"lot_id": lot.id})
    detail = await get_lot_by_scan(payload, db)
    assert detail.lot_id == lot.id


@pytest.mark.asyncio
async def test_get_lot_by_scan_unknown_barcode_raises(db, lot):
    with pytest.raises(ValueError, match="non trouvé"):
        await get_lot_by_scan("LOT-INEXISTANT", db)


@pytest.mark.asyncio
async def test_get_lot_by_scan_qr_without_lot_id_raises(db):
    with pytest.raises(ValueError, match="lot_id"):
        await get_lot_by_scan(json.dumps({"foo": "bar"}), db)


@pytest.mark.asyncio
async def test_get_lot_by_scan_malformed_code_raises(db):
    with pytest.raises(ValueError):
        await get_lot_by_scan("{broken", db)
