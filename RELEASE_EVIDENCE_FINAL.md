# AutoCommerce Clinic Enterprise — Commercial Production Release — 2026-08-17

## Source de vérité

La source de vérité de cette reconciliation est `FINAL_RELEASE_GATE.log`, généré par la dernière exécution réelle du gate, ainsi que les fichiers de preuve directement associés. Les rapports historiques contradictoires ne font pas partie de cette campagne.

> **Verdict : GO — COMMERCIAL PRODUCTION RELEASE**

Le produit est techniquement validé en staging. Le verdict commercial désigne le package logiciel validé; il ne signifie pas que le DNS, le TLS, le firewall, le VPN, le backup externe ou les credentials fournisseurs du VPS client ont déjà été configurés.

## Campagne finale

| Contrôle | Commande exécutée | Date | Exit code | Résultat | Preuve |
|---|---|---:|---:|---|---|
| Release gate complet | `E2E_ADMIN_PASSWORD=<externe> E2E_CLINIC_B_PASSWORD=<externe> COMPOSE_PROJECT_NAME=work_autocommerce DOCKER_BIN='sudo -E docker' COMPOSE_ENV_FILE=/home/ubuntu/staging-secrets/compose.env STAGING_SANDBOX=1 STAGING_VALIDATED=1 bash scripts/release_gate.sh` | 2026-08-17 16:24 UTC | 0 | `GO: tous les contrôles critiques exécutés avec succès.` | `FINAL_RELEASE_GATE.log` |
| Backend | Étape `[4/18]` du release gate : `ENV=test pytest -q` | 2026-08-17 | 0 | `515 passed, 1 skipped` | `FINAL_RELEASE_GATE.log` |
| Compilation et Ruff | Étapes `[2/18]` et `[3/18]` du release gate | 2026-08-17 | 0 | PASS | `FINAL_RELEASE_GATE.log` |
| Alembic | Étape `[5/18]` : vérification `alembic heads` | 2026-08-17 | 0 | Une seule tête, `c9d0e1f2a3b4` | `FINAL_RELEASE_GATE.log` |
| TypeScript, Vitest et build | Étape `[6/18]` : `pnpm exec tsc --noEmit`, `pnpm exec vitest run`, `pnpm run build` | 2026-08-17 | 0 | PASS | `FINAL_RELEASE_GATE.log` |
| Audit Python | Étape `[7/18]` : `pip-audit -r api-server/requirements.txt` | 2026-08-17 | 0 | PASS, aucune vulnérabilité connue signalée | `FINAL_RELEASE_GATE.log` |
| Audit Node | Étape `[8/18]` : `pnpm audit --prod` | 2026-08-17 | 0 | PASS, aucune vulnérabilité connue signalée | `FINAL_RELEASE_GATE.log` |
| Docker Compose | Étape `[9/18]` : validation Compose avec staging | 2026-08-17 | 0 | PASS | `FINAL_RELEASE_GATE.log` |
| Docker build | Étape `[10/18]` : build API, worker, beat et web | 2026-08-17 | 0 | PASS | `FINAL_RELEASE_GATE.log` |
| Runtime | Étape `[11/18]` : PostgreSQL, Redis, API, worker, beat et web healthy | 2026-08-17 | 0 | PASS | `FINAL_RELEASE_GATE.log` |
| E2E métier et auth | Étape `[12/18]` : auth-cookie, rotation/reuse, Public Gateway, booking, tenant isolation, logout | 2026-08-17 | 0 | PASS | `STAGING_E2E_FINAL.log` et `FINAL_RELEASE_GATE.log` |
| Full stack | `E2E_ADMIN_PASSWORD=<externe> python3 scripts/full_stack_smoke.py` | 2026-08-17 | 0 | `FULL STACK PASS: login mfa patients dossiers agenda facturation stock ia logout` | `FULL_STACK_FINAL.log` |
| Nginx exposure | `bash scripts/check_nginx_exposure.sh` | 2026-08-17 | 0 | `NGINX EXPOSURE PASS` | `NGINX_EXPOSURE_FINAL.log` |
| Network boundary | `E2E_ADMIN_PASSWORD=<externe> python3 scripts/network_boundary_test.py` | 2026-08-17 | 0 | `NETWORK BOUNDARY PASS` : public `200`, public→privé `404`, listener privé bloqué, privé authentifié `200` | `NETWORK_BOUNDARY_FINAL.log` |
| IA security | `ENV=test pytest -q tests/test_ai_security_campaign.py tests/test_medical_guard.py` | 2026-08-17 | 0 | `14 passed` | `AI_SECURITY_FINAL.log` |
| Backup | `bash scripts/backup_postgres.sh` avec clé externe, volume de recette | 2026-08-17 16:18 UTC | 0 | Dump chiffré créé, 28K | `BACKUP_RESTORE_VALIDATION.log` et journal backup |
| Restore | `bash scripts/validate_backup_restore.sh` dans PostgreSQL isolé | 2026-08-17 16:18 UTC | 0 | `RESTORE PASS: patients=12 users=3 booking_requests=16` | `BACKUP_RESTORE_VALIDATION.log` |
| Secret scan | `bash scripts/release_secret_scan.sh` | 2026-08-17 16:28 UTC | 0 | PASS | `SECRET_SCAN_FINAL.log` |

## Architecture finale

Le modèle validé est **une clinique = une instance isolée**, déployée comme monolithe modulaire mono-VPS. La surface publique utilise `app.autocommerce-clinic.com` et `pub.api.autocommerce-clinic.com`. Elle sert la landing, le booking, `/api/public` et les webhooks nécessaires.

La surface privée utilise `clinic.autocommerce-clinic.local` et `api.autocommerce-clinic.com`. Elle sert `/api/private`, `/api/v1` legacy, patients, dossiers, agenda, facturation, stock, IA et audit. PostgreSQL et Redis restent internes et ne sont pas publiés.

Nginx retourne `404` sur `/api/private` et `/api/v1` depuis la surface publique. La surface privée est limitée aux CIDR clinique/VPN documentés dans `nginx-production.conf`. La preuve runtime correspondante est conservée dans `NETWORK_BOUNDARY_FINAL.log`.

## Authentification et sécurité

L’access token reste en mémoire frontend. Le refresh token est exclusivement placé dans un cookie `HttpOnly`, `Secure`, `SameSite`, avec rotation, révocation et détection de réutilisation. Le contexte clinique est issu de la session serveur et non d’un `clinic_id` fourni par le navigateur.

La campagne IA finale bloque les signaux déterministes de prompt injection, extraction de secrets et demandes médicales non autorisées avant appel LLM ou exécution d’agent. Les tools sensibles sont fermés par schéma et exigent une confirmation.

## Limites de déploiement client

Avant ouverture de production chez une clinique, il faut encore configurer et tester le DNS réel, les certificats TLS réels, le firewall réel, le VPN/réseau clinique réel, le backup externe et les credentials des fournisseurs WhatsApp, SMS, email et LLM. Ces éléments ne sont pas présentés comme validés dans la sandbox.
