# Changelog de durcissement — Blocs 0 à 29

Cette version consolide les corrections réalisées des Blocs 0 à 17 et les contrôles finaux applicables aux Blocs 18 à 29.

Les protections maintenues ou ajoutées comprennent l’authentification JWT avec rotation et révocation, le hachage des codes MFA, l’idempotence webhook, la détection multilingue, le garde-fou médical, la séparation des segments de prompt, la minimisation LLM, les limites ReAct, la source de vérité des tools IA, la readiness non verbeuse, la protection métriques, les contrôles photos AES-GCM, l’audit médical append-only, le durcissement Celery, le build frontend et la suppression des credentials hardcodés retrouvés lors du scan final.

Le script racine `create_user.py` exige désormais `DATABASE_URL`, `ADMIN_EMAIL` et `ADMIN_PASSWORD` par variables d’environnement. Aucun mot de passe par défaut n’est affiché ni utilisé.

Les contrôles d’environnement réel PostgreSQL, Redis, Docker mono-VPS, migrations sur base propre/existante, restauration physique et test de charge n’ont pas pu être exécutés dans le sandbox disponible. Ils restent des conditions de validation avant production.
