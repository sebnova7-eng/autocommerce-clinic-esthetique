#!/usr/bin/env bash
# AutoCommerce Clinic — sauvegarde externe Postgres (cron @ 03h)
#
# Correction B7 (AUDIT) : le volume postgres_data est SUR le VPS.
# Si le VPS meurt (HDD, ransomware), tout est perdu. Ce script exporte
# nightly vers un répertoire dédié monté hors-VPS (NFS, S3 via restic,
# rsync vers un autre serveur ssh). Le fichier est chiffré ; le déchiffrer
# avant toute restauration avec la même BACKUP_ENCRYPTION_KEY.
#
# Installation :
#   sudo mkdir -p /var/backups/autocommerce-clinic
#   sudo chmod 700 /var/backups/autocommerce-clinic
#   sudo cp scripts/backup_postgres.sh /usr/local/bin/autocommerce-backup
#   sudo chmod +x /usr/local/bin/autocommerce-backup
#   sudo crontab -e
#   0 3 * * *  /usr/local/bin/autocommerce-backup
#
# Rétention : conserve les 14 derniers backups locaux ; plus ancien → suppression.
# Le répertoire cible (/var/backups/autocommerce-clinic) doit être sur un volume
# externe au VPS (NFS / S3fs / iSCSI) — JAMAIS sur le même disque.

set -euo pipefail

ENV_FILE="${ENV_FILE:-/etc/autocommerce/.env.production}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi
: "${POSTGRES_USER:?POSTGRES_USER must be configured}"
: "${POSTGRES_DB:?POSTGRES_DB must be configured}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY must be configured}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/autocommerce-clinic}"
KEEP_DAYS="${KEEP_DAYS:-14}"
BACKUP_REQUIRE_SEPARATE_DEVICE="${BACKUP_REQUIRE_SEPARATE_DEVICE:-1}"

mkdir -p "$BACKUP_ROOT"
chmod 700 "$BACKUP_ROOT"

# Un backup situé sur le même device ne protège pas contre la panne disque ou
# le ransomware du VPS. L’exception doit être explicite pour les tests locaux.
if [[ "$BACKUP_REQUIRE_SEPARATE_DEVICE" == "1" ]]; then
  ROOT_DEVICE="$(stat -c '%d' /)"
  BACKUP_DEVICE="$(stat -c '%d' "$BACKUP_ROOT")"
  if [[ "$ROOT_DEVICE" == "$BACKUP_DEVICE" ]]; then
    echo "ERREUR : BACKUP_ROOT doit être monté sur un device distinct du VPS" >&2
    exit 4
  fi
fi
DATE_TAG="$(date +%Y-%m-%d_%H%M)"
BACKUP_FILE="${BACKUP_ROOT}/autocommerce_${DATE_TAG}.sql.gz.enc"

# Dump via docker exec — évite d'installer psql côté hôte.
echo "[$(date +%FT%T)] pg_dump → ${BACKUP_FILE}"
TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

docker exec autocommerce_postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --no-owner --no-privileges --clean --if-exists \
  | gzip -9 > "$TMP_FILE"

openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -md sha256 -salt \
  -pass env:BACKUP_ENCRYPTION_KEY \
  -in "$TMP_FILE" -out "$BACKUP_FILE"

chmod 600 "$BACKUP_FILE"

# Rétention
find "$BACKUP_ROOT" -type f -name 'autocommerce_*.sql.gz.enc' -mtime +"$KEEP_DAYS" -delete

# Vérification intégrité : fichier non vide + déchiffrement + gunzip -t
if [[ ! -s "$BACKUP_FILE" ]]; then
  echo "[$(date +%FT%T)] ERREUR : backup vide — ${BACKUP_FILE}" >&2
  exit 2
fi
if ! openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -md sha256 \
  -pass env:BACKUP_ENCRYPTION_KEY -in "$BACKUP_FILE" | gunzip -t 2>/dev/null; then
  echo "[$(date +%FT%T)] ERREUR : backup corrompu — ${BACKUP_FILE}" >&2
  exit 3
fi

echo "[$(date +%FT%T)] OK : $(du -h "$BACKUP_FILE" | cut -f1)"
