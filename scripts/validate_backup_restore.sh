#!/usr/bin/env bash
set -euo pipefail

BACKUP_FILE="${BACKUP_FILE:?BACKUP_FILE requis}"
BACKUP_ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY requis}"
RESTORE_CONTAINER="${RESTORE_CONTAINER:-autocommerce_restore_pg}"
RESTORE_PORT="${RESTORE_PORT:-55432}"
RESTORE_USER="${RESTORE_USER:-restore_user}"
RESTORE_PASSWORD="${RESTORE_PASSWORD:-restore_password_staging}"
RESTORE_DB="${RESTORE_DB:-restore_db}"
TMP_SQL_GZ="$(mktemp)"
TMP_SQL="$(mktemp)"
cleanup() {
  rm -f "$TMP_SQL_GZ" "$TMP_SQL"
  docker rm -f "$RESTORE_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker rm -f "$RESTORE_CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$RESTORE_CONTAINER" --network host \
  -e "POSTGRES_USER=$RESTORE_USER" \
  -e "POSTGRES_PASSWORD=$RESTORE_PASSWORD" \
  -e "POSTGRES_DB=$RESTORE_DB" \
  postgres:16-alpine -p "$RESTORE_PORT" >/dev/null

for _ in $(seq 1 30); do
  if docker exec "$RESTORE_CONTAINER" pg_isready -U "$RESTORE_USER" -d "$RESTORE_DB" -p "$RESTORE_PORT" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec "$RESTORE_CONTAINER" pg_isready -U "$RESTORE_USER" -d "$RESTORE_DB" -p "$RESTORE_PORT" >/dev/null

openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -md sha256 \
  -pass "env:BACKUP_ENCRYPTION_KEY" -in "$BACKUP_FILE" | tee "$TMP_SQL_GZ" >/dev/null
gunzip -t "$TMP_SQL_GZ"
gunzip -c "$TMP_SQL_GZ" > "$TMP_SQL"
docker exec -i "$RESTORE_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$RESTORE_USER" -d "$RESTORE_DB" -p "$RESTORE_PORT" < "$TMP_SQL" >/dev/null

patients="$(docker exec "$RESTORE_CONTAINER" psql -At -U "$RESTORE_USER" -d "$RESTORE_DB" -p "$RESTORE_PORT" -c 'select count(*) from patients;')"
users="$(docker exec "$RESTORE_CONTAINER" psql -At -U "$RESTORE_USER" -d "$RESTORE_DB" -p "$RESTORE_PORT" -c 'select count(*) from utilisateurs;')"
requests="$(docker exec "$RESTORE_CONTAINER" psql -At -U "$RESTORE_USER" -d "$RESTORE_DB" -p "$RESTORE_PORT" -c 'select count(*) from booking_requests;')"
if [[ "$patients" -lt 1 || "$users" -lt 1 || "$requests" -lt 1 ]]; then
  echo "RESTORE FAIL: patients=$patients users=$users booking_requests=$requests" >&2
  exit 1
fi

echo "RESTORE PASS: patients=$patients users=$users booking_requests=$requests"
