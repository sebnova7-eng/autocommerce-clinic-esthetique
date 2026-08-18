#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "Démarrage de AutoCommerce Clinic..."

if [[ ! -f "api-server/.env.clinic" ]]; then
  echo "[NO-GO] api-server/.env.clinic est absent." >&2
  echo "        Préparez-le avec : cp api-server/.env.clinic.example api-server/.env.clinic" >&2
  exit 2
fi

if [[ ! -f "autocommerce-app/dist/public/index.html" ]]; then
  echo "[NO-GO] Le frontend n’est pas buildé." >&2
  echo "        Exécutez : pnpm install --frozen-lockfile && pnpm build:frontend" >&2
  exit 2
fi

# Charge uniquement le fichier de secrets préparé localement dans l’environnement
# du processus ; aucun secret n’est copié dans l’image ou dans le dépôt.
set -a
. "api-server/.env.clinic"
set +a

cd api-server
exec python3 run_combined.py
