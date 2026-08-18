# Upgrade — AutoCommerce Clinic Enterprise

Avant toute mise à jour, vérifier l’espace disque, produire une sauvegarde chiffrée et confirmer qu’une restauration récente est disponible. Lire les release notes, planifier une fenêtre de maintenance et tester la version sur staging avec des données synthétiques.

Sur le serveur, transférer la release sans secrets, mettre à jour les images Docker, arrêter les workers si la migration l’exige, puis appliquer :

```bash
alembic upgrade head
```

Vérifier `alembic current`, `alembic heads`, `/ready`, les healthchecks, le login, le MFA et un parcours métier. Redémarrer les workers et vérifier qu’ils répondent à la sonde Celery. Ne jamais considérer une migration comme validée si elle n’a pas été testée sur une copie restaurée.
