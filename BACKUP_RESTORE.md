# Backup et restauration

Une sauvegarde n’est valide qu’après déchiffrement, contrôle gzip et restauration réussie sur une instance isolée. Le support de sauvegarde doit être distinct du disque principal du VPS et la clé de chiffrement doit être conservée séparément.

## Sauvegarde

Configurer `POSTGRES_USER`, `POSTGRES_DB`, `BACKUP_ENCRYPTION_KEY`, `BACKUP_ROOT` et `BACKUP_REQUIRE_SEPARATE_DEVICE=1` dans un fichier protégé hors dépôt, puis exécuter :

```bash
sudo ENV_FILE=/etc/autocommerce/.env.production bash scripts/backup_postgres.sh
```

Le script produit un dump PostgreSQL compressé puis chiffré AES-256-CBC avec PBKDF2. Il conserve les fichiers selon la politique de rétention configurée.

## Restauration contrôlée

Arrêter l’instance concernée, préparer une PostgreSQL isolée, déchiffrer et importer le dump avec `psql`, puis vérifier les utilisateurs, patients, dossiers, rendez-vous, factures, stock, fichiers et relations. Le script `scripts/validate_backup_restore.sh` fournit une validation automatisée pour une instance de recette.

## Règle opérationnelle

Ne jamais restaurer directement en production sans fenêtre de maintenance, copie de sécurité préalable et vérification du schéma Alembic. Après restauration, exécuter `/ready`, le release gate et un parcours métier synthétique avant de rouvrir l’accès clinique.
