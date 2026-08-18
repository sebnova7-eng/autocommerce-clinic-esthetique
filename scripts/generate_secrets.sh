#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
# AutoCommerce Clinic — Génération automatique des secrets
# ═══════════════════════════════════════════════════════════

set -euo pipefail

echo "🔐 Génération des secrets AutoCommerce Clinic..."

# Vérifier que openssl est disponible
if ! command -v openssl &> /dev/null; then
    echo "❌ openssl requis mais non installé"
    exit 1
fi

# Génération des secrets
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
SECRET_KEY=$(openssl rand -hex 64)
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || openssl rand -base64 32)
PHOTO_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || openssl rand -base64 32)
WA_WEBHOOK_VERIFY_TOKEN=$(openssl rand -hex 16)
SOCIAL_WEBHOOK_SECRET=$(openssl rand -hex 32)
TIKTOK_WEBHOOK_SECRET=$(openssl rand -hex 32)

# Affichage (à copier dans .env.clinic)
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Secrets générés — copier dans .env.clinic"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "POSTGRES_USER=clinic_admin"
echo "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}"
echo "POSTGRES_DB=autocommerce_clinic"
echo "DATABASE_URL=postgresql+asyncpg://clinic_admin:${POSTGRES_PASSWORD}@postgres:5432/autocommerce_clinic"
echo ""
echo "REDIS_PASSWORD=${REDIS_PASSWORD}"
echo "REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0"
echo ""
echo "SECRET_KEY=${SECRET_KEY}"
echo "FERNET_KEY=${FERNET_KEY}"
echo "PHOTO_ENCRYPTION_KEY=${PHOTO_ENCRYPTION_KEY}"
echo ""
echo "WA_WEBHOOK_VERIFY_TOKEN=${WA_WEBHOOK_VERIFY_TOKEN}"
echo "SOCIAL_WEBHOOK_SECRET=${SOCIAL_WEBHOOK_SECRET}"
echo "TIKTOK_WEBHOOK_SECRET=${TIKTOK_WEBHOOK_SECRET}"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  ⚠️  Conservez ces secrets en lieu sûr !"
echo "═══════════════════════════════════════════════════════════"
