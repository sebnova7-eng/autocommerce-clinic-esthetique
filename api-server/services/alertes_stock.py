"""
AutoCommerce Clinic — Alertes stock WhatsApp
Tâche Celery pour notifier la directrice
"""

from datetime import date
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from services.stock_injectable import check_stock_alerts, StockAlert
from services.clinic_settings import get_setting
from services.branding import get_branding_context
from services.clinic_settings import _resolve_clinic_id


async def format_stock_alerts_message(alerts: List[StockAlert], clinic_name: str = "Clinique") -> str:
    """Formate les alertes stock en message WhatsApp."""
    rouges = [a for a in alerts if a.niveau == "rouge"]
    oranges = [a for a in alerts if a.niveau == "orange"]

    lines = [f"{clinic_name} — Rapport stock {date.today().strftime('%d/%m/%Y')}"]

    if rouges:
        lines.append("\n🔴 URGENT :")
        for a in rouges:
            lines.append(f"• {a.produit_nom} — {a.message}")

    if oranges:
        lines.append("\n🟠 ATTENTION :")
        for a in oranges:
            lines.append(f"• {a.produit_nom} — {a.message}")

    if not rouges and not oranges:
        lines.append(f"\n✅ Aucune alerte critique aujourd'hui pour {clinic_name}.")

    return "\n".join(lines)


async def send_stock_alerts_whatsapp(db: AsyncSession, clinic_id: Optional[int] = None) -> bool:
    """Envoie les alertes stock groupées par WhatsApp à la directrice.

    Retourne True si un message a été envoyé, False sinon.
    """
    from services.whatsapp_service import send_whatsapp_message

    clinic_id = _resolve_clinic_id(clinic_id)
    alerts = await check_stock_alerts(db, clinic_id=clinic_id)

    # Filtrer uniquement rouge et orange
    critical = [a for a in alerts if a.niveau in ("rouge", "orange")]
    if not critical:
        return False

    # Vérifier si les alertes WhatsApp sont activées
    try:
        alert_enabled = await get_setting("stock.alert_whatsapp", db, clinic_id=clinic_id)
        if alert_enabled and isinstance(alert_enabled, dict):
            if not alert_enabled.get("enabled", True):
                return False
    except Exception:
        pass

    branding = await get_branding_context(db, clinic_id=clinic_id)
    message = await format_stock_alerts_message(alerts, branding["clinic_name"])

    # Récupérer le téléphone de la directrice
    from sqlalchemy import select
    from models.database import Utilisateur, RoleEnum

    result = await db.execute(
        select(Utilisateur.telephone)
        .where(Utilisateur.role == RoleEnum.DIRECTRICE.value)
        .where(Utilisateur.clinic_id == clinic_id)
        .where(Utilisateur.is_active)
        .limit(1)
    )
    directrice_phone = result.scalar_one_or_none()

    if not directrice_phone:
        return False

    await send_whatsapp_message(directrice_phone, message)
    return True
