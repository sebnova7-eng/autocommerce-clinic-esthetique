#!/usr/bin/env bash
# Gate local de release AutoCommerce Clinic.
# Ne déploie rien : il produit un GO/NO-GO reproductible.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

printf '%s\n' '[1/8] Syntaxe shell'
bash -n scripts/*.sh start.sh

printf '%s\n' '[2/8] Compilation Python'
python3 -m compileall -q api-server

printf '%s\n' '[3/8] Ruff backend'
(cd api-server && ruff check .)

printf '%s\n' '[4/8] Tests backend'
(cd api-server && ENV=test pytest -q)

printf '%s\n' '[5/8] Une seule tête Alembic'
HEAD_COUNT="$(cd api-server && ENV=development alembic heads | grep -c '(head)' || true)"
if [[ "$HEAD_COUNT" != "1" ]]; then
  echo "NO-GO : nombre de heads Alembic inattendu : $HEAD_COUNT" >&2
  exit 10
fi

printf '%s\n' '[6/8] TypeScript'
(cd autocommerce-app && pnpm exec tsc --noEmit)

printf '%s\n' '[7/8] Tests et build frontend'
(cd autocommerce-app && pnpm exec vitest run && pnpm run build)

printf '%s\n' '[8/8] Contrôle dépendances'
if command -v pip-audit >/dev/null 2>&1; then
  pip-audit -r api-server/requirements.txt
else
  echo 'AVERTISSEMENT : pip-audit absent ; installer pip-audit pour le gate dépendances.'
fi

echo 'GO : validations locales terminées. Le déploiement réel doit encore exécuter first_deploy.sh sur le VPS cible.'
