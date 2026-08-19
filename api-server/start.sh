#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "Running database migrations..."
alembic upgrade head

# Seed optionnel et idempotent du compte initial. Le mot de passe est lu
# uniquement depuis les variables Railway BOOTSTRAP_ADMIN_*.
if [[ -n "${BOOTSTRAP_ADMIN_EMAIL:-}" || -n "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]]; then
  echo "Seeding initial admin account..."
  python bootstrap_admin.py --from-env
fi

echo "Starting Uvicorn server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
