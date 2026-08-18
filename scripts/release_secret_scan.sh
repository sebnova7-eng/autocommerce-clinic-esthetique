#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while IFS= read -r -d '' file; do
  base="${file#"$ROOT"/}"
  case "$base" in
    *.env.example|*.env.production.example|.env.mono-vps.example|.env.staging.example|api-server/.env.example|api-server/.env.clinic.example|api-server/.env.clinic.production.example|api-server/.env.clinic.staging.example)
      ;;
    *.env*)
      echo "[NO-GO] Fichier d’environnement non template dans la release: $base" >&2
      exit 1
      ;;
  esac
done < <(find "$ROOT" -type f -name '.env*' -print0)

if grep -RInE --exclude-dir=node_modules --exclude-dir=dist --exclude='*.lock' --exclude='release_secret_scan.sh' \
  -e 'admin@clinic\.com' \
  -e 'VXpwOu4m2AZzv3wGY51Z79nN' \
  -e 'AdminPass123456' \
  -e 'BEGIN (RSA|OPENSSH|EC|PGP) PRIVATE KEY' \
  -e 'sk-[A-Za-z0-9]{10,}' \
  "$ROOT"; then
  echo "[NO-GO] Motif de secret ou credential détecté dans la release." >&2
  exit 1
fi

echo "[OK] Secret scan release: aucun fichier ou motif interdit détecté."
