#!/usr/bin/env bash
# AutoCommerce Clinic — premier déploiement mono-VPS
# Code 0 = déploiement vérifié ; code non nul = NO-GO.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="docker-compose.mono-vps.yml"
ENV_FILE=".env"

for required_file in "$ENV_FILE" "api-server/.env.clinic" "api-server/scripts/pre_deploy_security_check.py" "scripts/verify_infrastructure.sh"; do
  if [[ ! -f "$required_file" ]]; then
    echo "[NO-GO] Fichier manquant : $required_file" >&2
    exit 2
  fi
done

: "${ADMIN_EMAIL:?ADMIN_EMAIL doit être défini hors dépôt}"
: "${ADMIN_PASSWORD:?ADMIN_PASSWORD doit être défini hors dépôt}"
if [[ "${#ADMIN_PASSWORD}" -lt 20 ]]; then
  echo "[NO-GO] ADMIN_PASSWORD doit contenir au moins 20 caractères." >&2
  exit 2
fi

echo "1/8 — Validation infrastructure et mode de déploiement"
API_ENV_FILE="api-server/.env.clinic" ./scripts/verify_infrastructure.sh

echo "2/8 — Validation de la configuration Compose"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config >/dev/null

echo "3/8 — Build des images"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build --pull

echo "4/8 — Démarrage PostgreSQL et Redis"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d postgres redis

for service in postgres redis; do
  healthy=0
  for _ in $(seq 1 30); do
    status="$(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps "$service" --format '{{.Status}}' || true)"
    if [[ "$status" == *healthy* ]]; then
      healthy=1
      break
    fi
    sleep 2
  done
  if [[ "$healthy" -ne 1 ]]; then
    echo "[NO-GO] $service n’est pas healthy dans le délai prévu." >&2
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --tail=100 "$service" >&2 || true
    exit 3
  fi
done

echo "5/8 — Migrations et vérification Alembic"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm api alembic upgrade head
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm api alembic current
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm api alembic heads

echo "6/8 — Bootstrap administrateur"
ADMIN_EMAIL="$ADMIN_EMAIL" ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm -T api python scripts/seed_admin.py

echo "7/8 — Contrôles sécurité pré-déploiement"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm api \
  python scripts/pre_deploy_security_check.py

echo "8/8 — Démarrage complet et smoke tests"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d

for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/tmp/autocommerce-health.json; then break; fi
  sleep 2
done
curl -fsS http://127.0.0.1:8000/health >/dev/null
curl -fsS http://127.0.0.1:8000/ready >/dev/null
curl -fsSI http://127.0.0.1:8080/ >/dev/null

echo "GO — stack démarrée, migrations et sondes validées."
echo "Planifier maintenant les sauvegardes externes avec scripts/backup_postgres.sh."
