"""Tests — services/alertes_stock.py"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from services.alertes_stock import format_stock_alerts_message, send_stock_alerts_whatsapp
from services.stock_injectable import StockAlert
from models.database import LotInjectable, StatutLot, RoleEnum, Utilisateur


@pytest.mark.asyncio
async def test_format_message_no_alerts():
    msg = await format_stock_alerts_message([])
    assert "Aucune alerte critique" in msg


@pytest.mark.asyncio
async def test_format_message_includes_rouge_section():
    alerts = [StockAlert(niveau="rouge", produit_nom="Botox", numero_lot="L1", message="RUPTURE", lot_id=1)]
    msg = await format_stock_alerts_message(alerts)
    assert "URGENT" in msg
    assert "Botox" in msg


@pytest.mark.asyncio
async def test_format_message_includes_orange_but_not_urgent_header():
    alerts = [StockAlert(niveau="orange", produit_nom="Acide", numero_lot="L2", message="Stock bas", lot_id=2)]
    msg = await format_stock_alerts_message(alerts)
    assert "ATTENTION" in msg
    assert "URGENT" not in msg


@pytest.mark.asyncio
async def test_format_message_ignores_vert_alerts_in_summary():
    alerts = [StockAlert(niveau="vert", produit_nom="Vitamine", numero_lot="L3", message="Expire bientôt", lot_id=3)]
    msg = await format_stock_alerts_message(alerts)
    # Pas de section urgente/attention, mais pas non plus le message "aucune alerte"
    assert "URGENT" not in msg
    assert "ATTENTION" not in msg


@pytest.mark.asyncio
async def test_send_stock_alerts_returns_false_when_no_critical_alerts(db):
    sent = await send_stock_alerts_whatsapp(db, clinic_id=1)
    assert sent is False


@pytest.mark.asyncio
async def test_send_stock_alerts_returns_false_without_directrice(db, produit):
    expired = LotInjectable(
        clinic_id=1, produit_id=produit.id, numero_lot="LOT-URGENT",
        date_expiration=date.today() - timedelta(days=1),
        quantite_initiale=Decimal("10.00"), quantite_restante=Decimal("10.00"),
        statut=StatutLot.DISPONIBLE.value,
    )
    db.add(expired)
    await db.flush()
    # Pas de directrice en base -> pas d'envoi possible
    sent = await send_stock_alerts_whatsapp(db, clinic_id=1)
    assert sent is False


@pytest.mark.asyncio
async def test_send_stock_alerts_returns_true_with_directrice_and_critical_alert(db, produit):
    directrice = Utilisateur(
        clinic_id=1, email="directrice@clinic.tn", hashed_password="x",
        nom="Karray", prenom="Nour", role=RoleEnum.DIRECTRICE.value,
        telephone="+21625000000", is_active=True,
    )
    db.add(directrice)
    expired = LotInjectable(
        clinic_id=1, produit_id=produit.id, numero_lot="LOT-URGENT2",
        date_expiration=date.today() - timedelta(days=1),
        quantite_initiale=Decimal("10.00"), quantite_restante=Decimal("10.00"),
        statut=StatutLot.DISPONIBLE.value,
    )
    db.add(expired)
    await db.flush()

    sent = await send_stock_alerts_whatsapp(db, clinic_id=1)
    assert sent is True
