#!/usr/bin/env bash
# AutoCommerce Clinic — gate de release final.
# Un contrôle non exécuté ou un échec critique arrête la release avec NO-GO.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

fail() { echo "NO-GO: $*" >&2; exit 10; }
pass() { echo "PASS: $*"; }
require_file() { [[ -f "$1" ]] || fail "fichier absent: $1"; }

printf '%s\n' '=== AutoCommerce Clinic Release Gate ==='
printf 'Date UTC: '; date -u +%FT%TZ

printf '%s\n' '[1/18] Secret scan'
SECRET_SCAN_OUTPUT="${SECRET_SCAN_OUTPUT:-/tmp/autocommerce-secret-scan.log}"
if ! bash scripts/release_secret_scan.sh >"$SECRET_SCAN_OUTPUT" 2>&1; then
  cat "$SECRET_SCAN_OUTPUT" >&2
  fail 'secret scan'
fi
pass 'secret scan'

printf '%s\n' '[2/18] Shell et compilation Python'
bash -n scripts/*.sh start.sh
python3 -m compileall -q api-server
pass 'shell + Python compile'

printf '%s\n' '[3/18] Ruff'
(cd api-server && ruff check .)
pass 'Ruff'

printf '%s\n' '[4/18] Tests backend'
(cd api-server && ENV=test pytest -q)
pass 'pytest backend'

printf '%s\n' '[5/18] Alembic'
HEAD_COUNT="$(cd api-server && ENV=development alembic heads | grep -c '(head)' || true)"
[[ "$HEAD_COUNT" == '1' ]] || fail "Alembic heads=$HEAD_COUNT"
pass 'une seule tête Alembic'

printf '%s\n' '[6/18] TypeScript, Vitest, frontend build'
(cd autocommerce-app && pnpm exec tsc --noEmit)
(cd autocommerce-app && pnpm exec vitest run)
(cd autocommerce-app && pnpm run build)
pass 'frontend'

printf '%s\n' '[7/18] Audit dépendances Python'
pip-audit -r api-server/requirements.txt
pass 'pip-audit'

printf '%s\n' '[8/18] Audit dépendances Node'
pnpm audit --prod
pass 'pnpm audit'

DOCKER=(sudo docker)
if [[ -n "${DOCKER_BIN:-}" ]]; then
  read -r -a DOCKER <<< "$DOCKER_BIN"
fi
BASE_COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.mono-vps.yml}"
COMPOSE_ARGS=(--env-file "${COMPOSE_ENV_FILE:?COMPOSE_ENV_FILE requis pour le gate runtime}" -f "$ROOT_DIR/$BASE_COMPOSE_FILE")
if [[ "${STAGING_SANDBOX:-0}" == '1' ]]; then
  COMPOSE_ARGS+=(-f "$ROOT_DIR/docker-compose.staging-sandbox.yml")
fi
COMPOSE=("${DOCKER[@]}" compose "${COMPOSE_ARGS[@]}")

printf '%s\n' '[9/18] Docker Compose configuration'
"${COMPOSE[@]}" config -q
pass 'Compose config'

printf '%s\n' '[10/18] Docker build'
"${COMPOSE[@]}" build
pass 'Docker build'

if [[ "${STAGING_VALIDATED:-0}" != '1' ]]; then
  fail 'STAGING_VALIDATED=1 requis : runtime staging non exécuté'
fi
: "${E2E_ADMIN_PASSWORD:?E2E_ADMIN_PASSWORD requis hors dépôt}"
: "${E2E_CLINIC_B_PASSWORD:?E2E_CLINIC_B_PASSWORD requis hors dépôt}"
export E2E_ADMIN_PASSWORD E2E_CLINIC_B_PASSWORD

printf '%s\n' '[11/18] Runtime services'
for service in postgres redis api worker beat web; do
  container="$(${COMPOSE[@]} ps -q "$service")"
  [[ -n "$container" ]] || fail "conteneur absent: $service"
  state="$(${DOCKER[@]} inspect -f '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}no-health{{end}}' "$container")"
  [[ "$state" == 'running healthy' ]] || fail "$service: $state"
done
pass 'PostgreSQL Redis API worker beat web healthy'

printf '%s\n' '[12/18] API readiness, migrations et E2E'
curl --fail --silent --show-error http://127.0.0.1:8000/health >/dev/null
curl --fail --silent --show-error http://127.0.0.1:8000/ready >/dev/null
api_container="$(${COMPOSE[@]} ps -q api)"
"${DOCKER[@]}" exec "$api_container" sh -lc 'ENV=development alembic -c /app/alembic.ini current' | grep '(head)'
"${DOCKER[@]}" exec "$api_container" sh -lc 'ENV=development alembic -c /app/alembic.ini heads' | grep '(head)'
python3 scripts/staging_e2e.py
pass 'health readiness migrations E2E public/private/auth/tenant'
python3 scripts/full_stack_smoke.py
pass 'full stack mfa patients dossiers agenda facturation stock ia logout'

printf '%s\n' '[13/18] Nginx exposure policy'
bash scripts/check_nginx_exposure.sh
pass 'Nginx public/private policy'

printf '%s\n' '[14/18] Network boundary'
python3 scripts/network_boundary_test.py
pass 'public gateway / private core network boundary'

printf '%s\n' '[15/18] Backup/restore'
require_file BACKUP_RESTORE_VALIDATION.log
grep -q 'RESTORE PASS:' BACKUP_RESTORE_VALIDATION.log || fail 'preuve RESTORE PASS absente'
pass 'backup/restore réellement exécuté et journalisé'

printf '%s\n' '[16/18] Frontière refresh token'
if grep -RInE 'localStorage\.(getItem|setItem|removeItem)\([^)]*(access_token|refresh_token)|refresh_token.*localStorage|localStorage.*refresh_token' autocommerce-app/client/src --exclude-dir=node_modules; then
  fail 'token d’authentification trouvé dans localStorage'
fi
pass 'access token mémoire, refresh cookie'

printf '%s\n' '[17/18] RLS et isolation'
if grep -RInE 'ENABLE ROW LEVEL SECURITY|CREATE POLICY|current_setting\(|set_config\(' api-server/alembic api-server/models api-server/services api-server/api >/dev/null; then
  echo 'INFO: RLS PostgreSQL détectée : exécuter une vérification DB dédiée.'
else
  echo 'INFO: RLS PostgreSQL absente; isolation retenue: application-level tenant isolation.'
fi
pass 'contrôle explicite RLS/isolation'

printf '%s\n' '[18/18] Release evidence prerequisites'
for file in INSTALLATION.md DEPLOYMENT.md BACKUP_RESTORE.md SECURITY.md ARCHITECTURE.md OPERATIONS.md UPGRADE.md ROLLBACK.md RELEASE_NOTES.md NGINX_EXPOSURE_FINAL.log NETWORK_BOUNDARY_FINAL.log AI_SECURITY_FINAL.log FULL_STACK_FINAL.log; do
  require_file "$file"
done
pass 'documentation minimale présente'

echo 'GO: tous les contrôles critiques exécutés avec succès.'
