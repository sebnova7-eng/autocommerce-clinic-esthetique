#!/usr/bin/env bash
# Contrôle de déploiement hôte. Ce script ne modifie rien et échoue fermé.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
ENV_FILE="${API_ENV_FILE:-api-server/.env.clinic}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "NO-GO : fichier de configuration absent : $ENV_FILE" >&2
  exit 2
fi
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

MODE="${DEPLOYMENT_MODE:-}"
if [[ "$MODE" != "internal_single_clinic" && "$MODE" != "enterprise" ]]; then
  echo "NO-GO : DEPLOYMENT_MODE doit valoir internal_single_clinic ou enterprise" >&2
  exit 3
fi

if ! grep -q '127\.0\.0\.1:8000:8000' docker-compose.mono-vps.yml || \
   ! grep -q '127\.0\.0\.1:8080:80' docker-compose.mono-vps.yml; then
  echo "NO-GO : API/frontend ne sont pas liés à loopback dans Compose" >&2
  exit 4
fi

if grep -Eq '^[[:space:]]*-[[:space:]]*"?[0-9.]+:[0-9]+:5432|^[[:space:]]*-[[:space:]]*"?[0-9.]+:[0-9]+:6379' docker-compose.mono-vps.yml; then
  echo "NO-GO : PostgreSQL ou Redis est publié sur l’hôte" >&2
  exit 5
fi

if [[ "$MODE" == "internal_single_clinic" ]]; then
  if [[ "${PUBLIC_ROUTES_ENABLED:-false}" == "true" || "${WEBHOOKS_ENABLED:-false}" == "true" ]]; then
    echo "NO-GO : le mode interne ne doit pas activer routes publiques ou webhooks" >&2
    exit 6
  fi
  echo "GO CODE/RESEAU INTERNE : aucune résolution de domaine public ni certificat TLS Internet n’est requise."
  echo "ATTENTION : ne pas installer nginx-production.conf sur un serveur interne sans l’adapter à l’adresse LAN/VPN réelle."
else
  APP_DOMAIN="${APP_DOMAIN:-}"
  API_DOMAIN="${API_DOMAIN:-}"
  TLS_CERT_PATH="${TLS_CERT_PATH:-}"
  TLS_KEY_PATH="${TLS_KEY_PATH:-}"
  for value_name in APP_DOMAIN API_DOMAIN TLS_CERT_PATH TLS_KEY_PATH; do
    if [[ -z "${!value_name}" ]]; then
      echo "NO-GO : $value_name doit être défini en mode enterprise" >&2
      exit 7
    fi
  done
  if [[ "$APP_DOMAIN" =~ ^(_|localhost|app\.autocommerce-clinic\.com|__|.*\.local$) ]] || \
     [[ "$API_DOMAIN" =~ ^(_|localhost|api\.autocommerce-clinic\.com|__|.*\.local$) ]]; then
    echo "NO-GO : domaine Nginx de démonstration ou placeholder détecté" >&2
    exit 8
  fi
  if [[ ! -s "$TLS_CERT_PATH" || ! -s "$TLS_KEY_PATH" ]]; then
    echo "NO-GO : certificats TLS absents ou vides" >&2
    exit 9
  fi
  if ! openssl x509 -in "$TLS_CERT_PATH" -noout -checkend 86400 >/dev/null; then
    echo "NO-GO : certificat TLS expiré ou expirant dans moins de 24 heures" >&2
    exit 10
  fi
  NGINX_CONF_PATH="${NGINX_CONF_PATH:-nginx-production.conf}"
  if [[ ! -s "$NGINX_CONF_PATH" ]] || grep -Eq 'server_name[[:space:]]+(_|app\.autocommerce-clinic\.com|api\.autocommerce-clinic\.com|__)' "$NGINX_CONF_PATH"; then
    echo "NO-GO : configuration Nginx contient encore un domaine exemple/placeholder" >&2
    exit 11
  fi
  if command -v nginx >/dev/null 2>&1; then
    nginx -t -c "$ROOT_DIR/$NGINX_CONF_PATH"
  else
    echo "NO-GO : nginx absent, configuration TLS non vérifiable" >&2
    exit 12
  fi
  echo "GO INFRASTRUCTURE ENTERPRISE : domaine, TLS et Nginx vérifiés."
fi

if [[ "${REQUIRE_RUNTIME_ATTESTATION:-0}" == "1" ]]; then
  [[ "${DOCKER_RUNTIME_VALIDATED:-0}" == "1" ]] || { echo "NO-GO : Docker runtime non attesté" >&2; exit 20; }
  [[ "${STAGING_VALIDATED:-0}" == "1" ]] || { echo "NO-GO : staging non attesté" >&2; exit 21; }
  [[ "${BACKUP_RESTORE_VALIDATED:-0}" == "1" ]] || { echo "NO-GO : restauration backup non attestée" >&2; exit 22; }
  [[ "${LOAD_TEST_VALIDATED:-0}" == "1" ]] || { echo "NO-GO : test de charge non attesté" >&2; exit 23; }
  echo "GO ATTESTATION : runtime, staging, restauration et charge déclarés validés par l’opérateur."
fi
