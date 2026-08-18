# Restore d’un backup chiffré

Le fichier produit par `scripts/backup_postgres.sh` est un dump PostgreSQL compressé puis chiffré. La clé `BACKUP_ENCRYPTION_KEY` doit être fournie hors de l’archive et conservée séparément du VPS.

```bash
export BACKUP_ENCRYPTION_KEY='clé-récupérée-hors-dépôt'
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -pass env:BACKUP_ENCRYPTION_KEY \
  -in autocommerce_YYYY-MM-DD_HHMM.sql.gz.enc \
  | gunzip \
  | docker exec -i autocommerce_postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

La procédure doit être exécutée périodiquement sur un environnement de restauration isolé. Une sauvegarde ne sera considérée comme validée qu’après restauration effective et vérification applicative.

Cette validation reste **BLOCKED** tant qu’un PostgreSQL réel et une clé client ne sont pas disponibles.
