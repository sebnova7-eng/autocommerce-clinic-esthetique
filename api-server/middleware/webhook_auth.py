"""
AutoCommerce Clinic — Vérification de signature des webhooks sociaux

N'importe qui pouvait auparavant poster sur /social/messages/webhook
et injecter de faux messages (donc déclencher de fausses réponses
automatiques). Ce module vérifie une signature HMAC-SHA256 du corps
brut de la requête avant de laisser passer.

Fail-closed : si SOCIAL_WEBHOOK_SECRET n'est pas configuré, le webhook
refuse tout (503) plutôt que d'accepter des payloads non signés.
"""
import hashlib
import hmac

from fastapi import HTTPException, Request, status

from config import get_settings


def _compute_signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def verify_webhook_signature(request: Request) -> bytes:
    """Dépendance FastAPI : vérifie X-Signature (hex HMAC-SHA256 du
    corps brut) et retourne le corps pour que la route puisse le
    reparser si besoin. Comparaison en temps constant pour éviter le
    timing attack sur la signature."""
    settings = get_settings()
    if not settings.social_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook non configuré (SOCIAL_WEBHOOK_SECRET manquant)",
        )

    signature = request.headers.get("X-Signature", "")
    body = await request.body()
    attendu = _compute_signature(settings.social_webhook_secret, body)

    if not signature or not hmac.compare_digest(signature, attendu):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature invalide")

    return body
