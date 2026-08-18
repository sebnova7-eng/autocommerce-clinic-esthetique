# Opérations — AutoCommerce Clinic Enterprise

Surveiller `/health`, `/ready`, l’espace disque, les volumes de données, les logs bornés, PostgreSQL, Redis et l’état des workers Celery. Les logs ne doivent pas contenir inutilement de données médicales ou de credentials.

Les tâches planifiées sont exécutées par Celery Beat et traitées par le worker. En cas d’échec, vérifier d’abord Redis, puis la file Celery, les logs worker et la disponibilité PostgreSQL. Une tâche métier doit rester idempotente et tolérer un redémarrage.

Les accès administrateurs doivent être individuels, protégés par MFA lorsque requis et retirés immédiatement lors d’un départ. Les secrets doivent être renouvelés selon la politique de la clinique; après rotation de `SECRET_KEY`, invalider les sessions existantes et vérifier le login.

Pour un incident, conserver les journaux techniques nécessaires, éviter tout export médical non indispensable, isoler le service concerné, restaurer sur une copie si nécessaire, puis documenter la cause, l’action corrective et le résultat du release gate.
