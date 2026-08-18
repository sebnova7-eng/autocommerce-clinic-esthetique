# Rollback — AutoCommerce Clinic Enterprise

Un rollback est décidé après analyse de l’incident et vérification qu’il ne compromet pas les données écrites par la version courante. Conserver les logs et une sauvegarde de l’état avant retour.

Pour revenir à la version précédente, restaurer l’image et les fichiers de release précédents, arrêter les services applicatifs, puis appliquer uniquement la procédure Alembic documentée pour cette version. Ne jamais exécuter un downgrade non testé sur la base de production.

Si le schéma courant n’est pas compatible avec l’ancienne release, restaurer une copie PostgreSQL dans une instance isolée, vérifier les données et relations, puis basculer le trafic vers l’instance validée. Après retour, exécuter `/health`, `/ready`, login, MFA, un parcours métier et le release gate. Documenter la décision, la version source, la version cible et les contrôles passés.
