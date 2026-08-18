"""
AutoCommerce Clinic — Configuration centralisée
Règles absolues : jamais de secret en dur, jamais de Float pour montants
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    """Configuration chargée depuis les variables d'environnement."""

    # ── Identité clinique ────────────────────────────────────
    # No implicit tenant or deployment mode in a release.
    clinic_id: int | None = None
    # Mode d’exploitation explicite : aucun fallback implicite en production.
    deployment_mode: Literal["internal_single_clinic", "enterprise"] = "enterprise"
    # Les routes publiques/webhooks doivent être opt-in, jamais implicites.
    public_routes_enabled: bool = False
    webhooks_enabled: bool = False
    teleconsultation_enabled: bool = False
    # Tenant explicite utilisé uniquement par les routes publiques de la landing.
    public_clinic_id: int | None = None
    env: str = ""

    @property
    def is_internal_single_clinic(self) -> bool:
        return self.deployment_mode == "internal_single_clinic"

    @property
    def allowed_external_integrations(self) -> set[str]:
        raw = getattr(self, "external_integrations_allowlist", "ai,whatsapp") or ""
        return {item.strip().lower() for item in raw.split(",") if item.strip()}

    # ── API / réseau ─────────────────────────────────────────
    # Domaine(s) du frontend autorisé(s) en CORS, séparés par virgule.
    # À restreindre au domaine réel du client en production.
    cors_origins: str = ""

    # ── Base de données ──────────────────────────────────────
    database_url: str = ""

    # ── Redis ────────────────────────────────────────────────
    redis_url: str = ""

    # ── Sécurité ─────────────────────────────────────────────
    secret_key: str = ""
    fernet_key: str = ""
    # Clé séparée pour le chiffrement AES des photos : ne doit jamais
    # partager la clé du dossier médical (compromission de l'une ne doit
    # pas exposer l'autre).
    photo_encryption_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    refresh_cookie_secure: bool = True
    refresh_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    refresh_cookie_domain: str = ""

    # ── WhatsApp Business API ────────────────────────────────
    wa_business_token: str = ""
    wa_phone_id: str = ""
    wa_webhook_verify_token: str = ""
    wa_api_version: str = "v18.0"
    wa_base_url: str = "https://graph.facebook.com"
    # Correction B6 (AUDIT) : opt-in explicite pour le mode dev WhatsApp.
    # JAMAIS `true` en production : sécurise le connecteur contre l'envoi
    # silencieux de messages non livrés (cf. services/omnicanal/whatsapp_connector.py).
    wa_allow_dev_mode: bool = False
    whatsapp_enabled: bool = False

    # ── Resend (Email) ───────────────────────────────────────
    resend_api_key: str = ""

    # ── Twilio (SMS) ─────────────────────────────────────────
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from: str = ""

    # ── Feature Flags Omnicanal ──────────────────────────────
    tiktok_enabled: bool = False
    instagram_enabled: bool = False
    facebook_enabled: bool = False

    # ── Webhooks réseaux sociaux (signature) ─────────────────
    # Secret partagé pour vérifier la signature HMAC-SHA256 des webhooks
    # entrants (header X-Signature). En prod, chaque plateforme a son
    # propre schéma (Meta : X-Hub-Signature-256, TikTok : sa propre
    # convention) — ce secret sert de base commune tant qu'un seul
    # webhook générique est utilisé ; à spécialiser par plateforme si
    # plusieurs comptes développeur réels sont branchés.
    social_webhook_secret: str = ""  # Meta uniquement (WhatsApp/Instagram/Facebook — un seul App Secret)
    social_webhook_clinic_id: int | None = None  # Mapping vérifié du webhook vers une clinique
    tiktok_webhook_secret: str = ""  # TikTok a son propre secret, distinct de Meta — jamais le même

    # ── Politique des sorties externes ─────────────────────────
    # En mode interne, seules les valeurs ai,whatsapp sont autorisées.
    external_integrations_allowlist: str = "ai,whatsapp"

    # ── LLM multi-provider (v1.1.0 patch IA) ───────────────────
    # Sélection du provider LLM principal pour les assistants et le runtime
    # agent. Valeurs supportées : openai | openrouter | anthropic |
    # gemini | mistral.
    llm_enabled: bool = False
    # Les données médicales ne sortent jamais par défaut. L’activation est
    # serveur-only et doit être accompagnée des garanties contractuelles.
    medical_ai_provider_approved: bool = False
    medical_ai_store_raw_transcription: bool = False
    llm_provider: str = "openai"
    llm_provider_allowlist: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-latest"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    mistral_api_key: str = ""
    mistral_model: str = "mistral-large-latest"
    # Modèle d'édition d'image pour les simulations IA médicales.
    # gpt-image-1 permet un vrai flux d'édition à partir d'une photo source.
    openai_image_model: str = "gpt-image-1"
    llm_max_tokens_per_request: int = 2048
    llm_daily_token_budget: int = 100_000
    llm_monthly_token_budget: int = 1_000_000
    llm_max_requests_per_user_day: int = 100
    llm_max_requests_per_clinic_day: int = 1_000

    # ── Stockage fichiers ────────────────────────────────────
    data_dir: Path = Path("/home/ubuntu/autocommerce-clinic/data")
    photos_dir: Path = Path("/home/ubuntu/autocommerce-clinic/data/photos")
    uploads_dir: Path = Path("/home/ubuntu/autocommerce-clinic/data/uploads")
    branding_dir: Path = Path("/home/ubuntu/autocommerce-clinic/data/branding")
    backups_dir: Path = Path("/home/ubuntu/autocommerce-clinic/backups")
    max_photo_size_mb: int = 20
    max_invoice_upload_size_mb: int = 20
    max_pdf_pages: int = 5

    # ── AWS S3 (optionnel) ───────────────────────────────────
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_s3_bucket: str = ""
    aws_region: str = "eu-west-1"

    # ── Email (optionnel) ────────────────────────────────────
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@clinic.local"

    # ── Monitoring ───────────────────────────────────────────
    sentry_dsn: str = ""

    # ── RGPD ─────────────────────────────────────────────────
    rgpd_retention_years: int = 10
    points_expiry_months: int = 12
    consent_validity_months: int = 12

    model_config = ConfigDict(
        env_file=".env.production",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
    )


DEFAULT_SECRET_KEY = "change-me-in-production-64-chars-minimum-for-jwt-signing"
_PLACEHOLDER_MARKERS = ("changeme", "change-me", "change_me", "password", "placeholder", "your_", "your-", "secret-key", "example")


def _contains_placeholder(value: str) -> bool:
    normalized = (value or "").strip().lower()
    return any(marker in normalized for marker in _PLACEHOLDER_MARKERS)


def _validate_production_secrets(settings: "Settings") -> None:
    """Refuse de démarrer en production avec des secrets par défaut ou
    absents — un oubli de configuration ne doit jamais passer inaperçu.
    Ne s'applique pas en dev/test pour ne pas gêner le développement local."""
    if not settings.env:
        raise RuntimeError("ENV doit être explicitement défini (test, development ou production)")
    if settings.env not in {"test", "development", "production"}:
        raise RuntimeError("ENV doit valoir test, development ou production")
    if settings.env != "production":
        return

    erreurs = []
    if settings.deployment_mode not in {"internal_single_clinic", "enterprise"}:
        erreurs.append("DEPLOYMENT_MODE doit valoir internal_single_clinic ou enterprise")
    if settings.deployment_mode == "internal_single_clinic" and (not settings.clinic_id or settings.clinic_id <= 0):
        erreurs.append("CLINIC_ID doit être un identifiant positif en mode internal_single_clinic")
    if settings.deployment_mode == "enterprise" and settings.clinic_id is not None:
        erreurs.append("CLINIC_ID ne doit pas être globalement implicite en mode enterprise")
    if not settings.database_url:
        erreurs.append("DATABASE_URL doit être définie en production")
    if not settings.redis_url:
        erreurs.append("REDIS_URL doit être définie en production")
    if settings.webhooks_enabled and not settings.social_webhook_clinic_id:
        erreurs.append("SOCIAL_WEBHOOK_CLINIC_ID doit être défini lorsque les webhooks sont activés")
    if settings.public_routes_enabled and (not settings.public_clinic_id or settings.public_clinic_id <= 0):
        erreurs.append("PUBLIC_CLINIC_ID doit être défini lorsque les routes publiques sont activées")
    if settings.is_internal_single_clinic and settings.public_routes_enabled:
        erreurs.append("PUBLIC_ROUTES_ENABLED doit être false en mode internal_single_clinic")
    if settings.is_internal_single_clinic and settings.webhooks_enabled:
        erreurs.append("WEBHOOKS_ENABLED doit être false en mode internal_single_clinic")
    if settings.is_internal_single_clinic and not settings.allowed_external_integrations.issubset({"ai", "whatsapp"}):
        erreurs.append("Le mode interne autorise uniquement les intégrations externes ai et whatsapp")
    if not settings.cors_origins:
        erreurs.append("CORS_ORIGINS doit être définie en production")
    if settings.secret_key == DEFAULT_SECRET_KEY or len(settings.secret_key) < 64:
        erreurs.append("SECRET_KEY doit être définie et faire au moins 64 caractères en production")
    if not settings.fernet_key:
        erreurs.append("FERNET_KEY doit être définie en production (chiffrement des données médicales)")
    if not settings.photo_encryption_key:
        erreurs.append("PHOTO_ENCRYPTION_KEY doit être définie en production (chiffrement des photos)")
    if settings.photo_encryption_key and settings.photo_encryption_key == settings.fernet_key:
        erreurs.append("PHOTO_ENCRYPTION_KEY doit être différente de FERNET_KEY")
    if not settings.refresh_cookie_secure:
        erreurs.append("REFRESH_COOKIE_SECURE doit être true en production")
    if settings.refresh_cookie_samesite == "none" and not settings.refresh_cookie_secure:
        erreurs.append("SameSite=None exige Secure=true")
    if _contains_placeholder(settings.database_url):
        erreurs.append("DATABASE_URL contient un identifiant ou placeholder de démonstration")
    if _contains_placeholder(settings.redis_url):
        erreurs.append("REDIS_URL contient un mot de passe ou placeholder de démonstration")
    if _contains_placeholder(settings.secret_key):
        erreurs.append("SECRET_KEY contient un placeholder interdit")
    if _contains_placeholder(settings.fernet_key):
        erreurs.append("FERNET_KEY contient un placeholder interdit")
    if _contains_placeholder(settings.photo_encryption_key):
        erreurs.append("PHOTO_ENCRYPTION_KEY contient un placeholder interdit")
    if settings.cors_origins.strip() == "*":
        erreurs.append("CORS_ORIGINS ne doit pas valoir '*' en production")
    if settings.wa_allow_dev_mode:
        erreurs.append("WA_ALLOW_DEV_MODE doit être false en production")
    if settings.whatsapp_enabled and (not settings.wa_business_token or not settings.wa_phone_id):
        erreurs.append("WHATSAPP_ENABLED exige WA_BUSINESS_TOKEN et WA_PHONE_ID")
    if settings.medical_ai_provider_approved:
        if not settings.llm_enabled:
            erreurs.append("MEDICAL_AI_PROVIDER_APPROVED exige LLM_ENABLED=true")
        if "ai" not in settings.allowed_external_integrations:
            erreurs.append("MEDICAL_AI_PROVIDER_APPROVED exige l’intégration externe ai")
        approved_allowlist = {
            item.strip().lower()
            for item in settings.llm_provider_allowlist.split(",")
            if item.strip()
        }
        if settings.llm_provider.lower() not in approved_allowlist:
            erreurs.append("MEDICAL_AI_PROVIDER_APPROVED exige un provider présent dans LLM_PROVIDER_ALLOWLIST")
    if settings.llm_enabled and "ai" in settings.allowed_external_integrations:
        provider_keys = {
            "openai": settings.openai_api_key,
            "openrouter": settings.openrouter_api_key,
            "anthropic": settings.anthropic_api_key,
            "gemini": settings.gemini_api_key,
            "mistral": settings.mistral_api_key,
        }
        if not provider_keys.get(settings.llm_provider, ""):
            erreurs.append(f"LLM_PROVIDER={settings.llm_provider} est activé mais sa clé est absente")
    if settings.is_internal_single_clinic and any((
        settings.resend_api_key,
        settings.twilio_auth_token,
        settings.aws_access_key_id,
        settings.aws_secret_access_key,
        settings.smtp_host,
        settings.smtp_password,
        settings.sentry_dsn,
    )):
        erreurs.append("Les credentials Email/SMS/S3/Sentry sont interdits en mode internal_single_clinic")

    if erreurs:
        raise RuntimeError(
            "Configuration de production invalide :\n- " + "\n- ".join(erreurs)
        )


@lru_cache()
def get_settings() -> Settings:
    """Retourne une instance singleton des settings. Échoue au démarrage
    (pas au premier appel isolé) si ENV=production et que des secrets
    critiques sont absents ou laissés à leur valeur par défaut."""
    import os
    env_file = os.getenv("API_ENV_FILE", ".env.production")
    
    # On surcharge dynamiquement le fichier d'environnement
    class CustomSettings(Settings):
        model_config = ConfigDict(
            env_file=env_file,
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="allow",
        )
        
    settings = CustomSettings()
    _validate_production_secrets(settings)
    return settings


# ── Constantes métier ──────────────────────────────────────

POINTS_PER_DT: int = 1
FIDELITE_SEUILS = {
    "bronze": 0,
    "silver": 500,
    "gold": 1500,
    "vip": 3000,
}

COMMISSION_VALIDATION_SEUIL: float = 500.0  # Numeric, pas Float

STOCK_ALERT_DAYS_EXPIRING: int = 30
STOCK_WARNING_DAYS_EXPIRING: int = 60

PHOTO_ALLOWED_MIMETYPES = {"image/jpeg", "image/png", "image/webp"}
PHOTO_MAX_DIMENSION = 4096
PHOTO_THUMBNAIL_SIZE = 200

LABEL_FORMATS = {
    "a4": {"width": 210, "height": 297, "cols": 2, "rows": 2},
    "50x30": {"width": 50, "height": 30, "cols": 1, "rows": 1},
    "40x25": {"width": 40, "height": 25, "cols": 1, "rows": 1},
    "60x40": {"width": 60, "height": 40, "cols": 1, "rows": 1},
}

WA_TEMPLATES = {
    "rdv_confirmation": "Votre rendez-vous est confirmé pour le {date} à {heure} avec {praticien}. À bientôt !",
    "rdv_rappel_j1": "Rappel : votre rendez-vous demain à {heure}h avec {praticien}. Confirmer : répondez OUI. Pour annuler : répondez NON.",
    "rdv_rappel_h2": "⏰ Dans 2h : votre rendez-vous à {clinique} 📍 {adresse}",
    "suivi_post_acte": "Comment vous sentez-vous après votre {acte} ? 1️⃣ Très satisfaite 2️⃣ Satisfaite 3️⃣ Questions 4️⃣ Problème",
    "fidelite_gain": "Vous avez gagné {points} points 🌟 Votre solde : {solde} points ({niveau})",
    "fidelite_niveau": "Félicitations {prenom} ! Vous êtes maintenant {niveau} 👑",
    "anniversaire": "Joyeux anniversaire {prenom} ! 🎂 Nous vous offrons 100 points fidélité. À très vite !",
    "relance_inactive": "Bonjour {prenom}, nous vous manquons ! Profitez de -15% sur votre prochain soin. Répondez RDV pour prendre rendez-vous.",
    "stock_alerte": "🏥 Rapport stock — {date}\n🔴 URGENT :\n{urgent}\n🟠 ATTENTION :\n{attention}",
    "backup_ok": "✅ Backup quotidien effectué avec succès. Base + photos chiffrées. {date}",
    "candidature_recu": "Nouvelle candidature reçue : {poste} — {nom}",
    "candidature_statut": "Votre candidature pour {poste} : statut mis à jour → {statut}",
    "injection_rappel": "Bonjour {prenom}, votre injection de {produit} arrive à échéance le {date}. Souhaitez-vous planifier votre prochaine séance ?",
}
