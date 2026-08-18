# AutoCommerce Clinic — Guide de déploiement corrigé

Cette release est conçue pour deux profils à partir d’une même base de code. Le profil doit être sélectionné dans `api-server/.env.clinic` ; il n’est jamais déduit d’un `clinic_id` fourni par le navigateur.

| Mode | Périmètre | Réseau | Sorties externes | Isolation |
|---|---|---|---|---|
| `internal_single_clinic` | Une clinique, base dédiée | Serveur local, LAN/VPN, aucun accès Internet entrant | IA autorisée et WhatsApp uniquement | `CLINIC_ID` explicite, RBAC et scope serveur |
| `enterprise` | Plusieurs cliniques possibles | Privé ou public selon reverse proxy et firewall | Allowlist configurable, chaque canal opt-in | `clinic_id` issu de la session, RLS/défense applicative et contrôles par tenant |

Le mode interne est le profil recommandé pour un premier client. Il ne publie pas de route publique, de webhook entrant, de téléconsultation Jitsi, d’Email, de SMS, de S3 ou de Sentry. L’IA et WhatsApp restent des sorties contrôlées : elles sont désactivées par défaut et ne sont activées qu’avec les credentials et la allowlist correspondants.

**Important : `nginx-production.conf` est un modèle d’exemple, pas une configuration prête à installer telle quelle.** Ses domaines `app.autocommerce-clinic.com` et `api.autocommerce-clinic.com` doivent être remplacés par le domaine réel en mode entreprise, avec des certificats TLS existants et vérifiables. En mode interne strictement local, ne pas installer ce modèle public : utiliser un reverse proxy lié à l’adresse LAN/VPN réelle ou un accès local contrôlé.

## Architecture réseau

| Composant | Exposition attendue en mode interne | Rôle |
|---|---:|---|
| Frontend | `127.0.0.1:8080` puis accès LAN/VPN via reverse proxy local | Interface React/Nginx |
| API | `127.0.0.1:8000` | FastAPI |
| PostgreSQL | Réseau Docker uniquement | Données métier et médicales |
| Redis | Réseau Docker uniquement | Cache, quotas IA, broker Celery |
| Worker / Beat | Réseau Docker uniquement | Tâches asynchrones et planifiées |
| IA / WhatsApp | Connexions sortantes TLS uniquement, si activées | Seules communications externes du mode interne |

Le mapping Compose de l’API et du frontend est lié à `127.0.0.1`. Le fait que le serveur soit local ne remplace pas le firewall : le VPS ou serveur doit refuser les connexions entrantes non nécessaires, désactiver UPnP, ne pas exposer Docker Engine et réserver l’accès aux postes autorisés du LAN/VPN. PostgreSQL et Redis ne doivent jamais recevoir de section `ports:` publique.

Le réseau Docker reste sortant afin de permettre l’IA et WhatsApp. La restriction des sorties doit être appliquée au niveau applicatif par `EXTERNAL_INTEGRATIONS_ALLOWLIST`, et au niveau hôte par une politique d’egress limitant les destinations autorisées lorsque l’environnement le permet.

## Prérequis

Le serveur cible doit disposer de Docker Engine avec Compose v2, d’un stockage persistant séparé pour les sauvegardes, d’un firewall local et d’une méthode de restauration testée. En mode entreprise public, ajouter un reverse proxy TLS, un DNS maîtrisé, un renouvellement de certificats, une protection réseau et une procédure de rotation des secrets.

Les fichiers réels ne doivent jamais être commités :

```bash
cp .env.example .env
cp api-server/.env.clinic.example api-server/.env.clinic
chmod 600 .env api-server/.env.clinic
```

## Configuration du mode interne mono-client

Utiliser au minimum les valeurs suivantes dans `api-server/.env.clinic` :

```env
ENV=production
DEPLOYMENT_MODE=internal_single_clinic
CLINIC_ID=1
PUBLIC_ROUTES_ENABLED=false
WEBHOOKS_ENABLED=false
TELECONSULTATION_ENABLED=false
EXTERNAL_INTEGRATIONS_ALLOWLIST=ai,whatsapp
CORS_ORIGINS=http://clinic.local
LLM_ENABLED=false
WHATSAPP_ENABLED=false
WA_ALLOW_DEV_MODE=false
```

Lorsque l’IA est activée, définir un provider autorisé, sa clé et les plafonds :

```env
LLM_ENABLED=true
# Les flux contenant des données médicales restent bloqués par défaut.
# Activer uniquement après garanties contractuelles/provider approuvées.
MEDICAL_AI_PROVIDER_APPROVED=false
MEDICAL_AI_STORE_RAW_TRANSCRIPTION=false
LLM_PROVIDER=openai
LLM_PROVIDER_ALLOWLIST=openai
OPENAI_API_KEY=<clé gérée hors dépôt>
LLM_MAX_TOKENS_PER_REQUEST=2048
LLM_DAILY_TOKEN_BUDGET=100000
LLM_MONTHLY_TOKEN_BUDGET=1000000
LLM_MAX_REQUESTS_PER_USER_DAY=100
LLM_MAX_REQUESTS_PER_CLINIC_DAY=1000
```

Lorsque WhatsApp est activé, il doit être explicitement configuré :

```env
WHATSAPP_ENABLED=true
EXTERNAL_INTEGRATIONS_ALLOWLIST=ai,whatsapp
WA_ALLOW_DEV_MODE=false
WA_BUSINESS_TOKEN=<token Meta géré hors dépôt>
WA_PHONE_ID=<identifiant du numéro WhatsApp Business>
```

Le mode interne refuse les credentials Email, SMS, SMTP, S3 et Sentry. Il refuse également les routes publiques et les webhooks. Si la réception WhatsApp entrante devient nécessaire, elle exige un relais externe ou un VPN entrant contrôlé, car un serveur strictement non public ne peut pas recevoir directement un webhook Internet.

## Configuration entreprise

Pour une installation évolutive :

```env
ENV=production
DEPLOYMENT_MODE=enterprise
CLINIC_ID=
PUBLIC_ROUTES_ENABLED=false
WEBHOOKS_ENABLED=false
TELECONSULTATION_ENABLED=false
EXTERNAL_INTEGRATIONS_ALLOWLIST=ai,whatsapp
```

En mode `enterprise`, une session authentifiée doit porter le contexte clinique ; aucune route métier ne doit utiliser `clinic_id=1` comme fallback. Les routes publiques et webhooks doivent recevoir un `PUBLIC_CLINIC_ID` ou un mapping signé explicite. Chaque intégration supplémentaire doit être ajoutée à l’allowlist, disposer d’un secret distinct et être couverte par un test d’activation et de refus.

## Secrets et chiffrement

Les secrets critiques sont `SECRET_KEY`, `FERNET_KEY`, `PHOTO_ENCRYPTION_KEY`, les credentials PostgreSQL/Redis, les tokens IA et le token WhatsApp. `FERNET_KEY` et `PHOTO_ENCRYPTION_KEY` doivent être distinctes. Les photos médicales et les factures uploadées sont chiffrées au repos ; les uploads de facture sont limités en taille et en type, puis envoyés à l’IA uniquement si la politique IA l’autorise.

Les factures sont stockées sous forme AES-GCM avec nonce préfixé au ciphertext. Les réponses brutes non parsées du provider IA ne sont pas conservées. Les exports, lectures de dossiers, photos, factures, audits et actions IA doivent rester journalisés avec l’utilisateur et la clinique.

## Déploiement contrôlé

Le script recommandé est `scripts/first_deploy.sh`. Il commence par `scripts/verify_infrastructure.sh`, qui bloque les domaines/TLS placeholders en mode entreprise et refuse les ports DB/Redis publiés. Il vérifie ensuite la configuration Compose, construit les images, démarre PostgreSQL/Redis, applique les migrations, crée l’administrateur fourni hors dépôt, exécute le contrôle de sécurité et vérifie les sondes API/frontend.

```bash
export ADMIN_EMAIL='admin@clinique.local'
export ADMIN_PASSWORD='<mot-de-passe-long-et-unique>'
API_ENV_FILE=api-server/.env.clinic ./scripts/verify_infrastructure.sh
./scripts/first_deploy.sh
```

Avant transfert vers le serveur, exécuter le gate local :

```bash
ENV=development ./scripts/verify_ready_to_go.sh
```

Le gate vérifie la syntaxe shell, la compilation Python, Ruff, les tests backend, l’existence d’une seule tête Alembic, TypeScript, Vitest, le build frontend et `pip-audit`. Il ne prétend pas remplacer l’attestation infrastructure. Pour une certification entreprise finale, exécuter aussi `REQUIRE_RUNTIME_ATTESTATION=1 DOCKER_RUNTIME_VALIDATED=1 STAGING_VALIDATED=1 BACKUP_RESTORE_VALIDATED=1 LOAD_TEST_VALIDATED=1 ./scripts/verify_infrastructure.sh` après preuve réelle de ces contrôles. Docker, PostgreSQL, Redis, Celery et la restauration n’ont pas de valeur probante tant qu’ils n’ont pas été vérifiés sur la machine cible.

La chaîne Alembic doit afficher une seule tête :

```bash
ENV=development alembic -c api-server/alembic.ini heads
# c9d0e1f2a3b4 (head)
```

## Exploitation et limites

Les services Compose ont des plafonds CPU, mémoire, processus et logs. Celery utilise un préfetch de une tâche, une rotation des workers, une limite mémoire enfant et un rate limit sur le scan IA de factures. Le VPS doit tout de même être dimensionné à partir de la charge réelle ; une première charge contrôlée doit mesurer RAM, CPU, latence PostgreSQL, file Redis, temps de réponse IA et taille des volumes.

Les quotas IA sont comptés par sujet utilisateur/clinique et par jour via Redis. Le clinic_id de quota vient du contexte authentifié ou d’un identifiant serveur explicite; aucun clinic_id de la payload frontend n’est accepté. Les flux Scribe, audio médical et simulation d’image exigent en plus `MEDICAL_AI_PROVIDER_APPROVED=true`; ce flag reste faux par défaut et `MEDICAL_AI_STORE_RAW_TRANSCRIPTION=false` évite de conserver la transcription brute.

Pour activer un flux médical externe, valider séparément le fournisseur, la rétention, les garanties contractuelles et la conformité clinique, puis renseigner le flag côté serveur uniquement. Une absence d’approbation renvoie un refus contrôlé plutôt qu’un fallback externe silencieux. En production, si Redis est indisponible, les appels IA sont refusés plutôt que laissés sans gouvernance. Les simulations d’image sont sérialisées afin d’éviter un burst mémoire et financier.

## Sauvegarde et restauration

Le script `scripts/backup_postgres.sh` produit un dump compressé et chiffré AES-256-CBC avec PBKDF2. Par défaut, il refuse de fonctionner si `BACKUP_ROOT` se trouve sur le même device que la racine du serveur. Une exception locale doit être explicitement demandée avec `BACKUP_REQUIRE_SEPARATE_DEVICE=0`, uniquement pour un test.

```env
POSTGRES_USER=clinic_app
POSTGRES_DB=autocommerce_clinic
BACKUP_ENCRYPTION_KEY=<clé conservée séparément du serveur>
BACKUP_ROOT=/mnt/autocommerce-backups
BACKUP_REQUIRE_SEPARATE_DEVICE=1
```

Une sauvegarde n’est considérée fiable qu’après un déchiffrement, un `gunzip -t` et une restauration sur une instance isolée. Les clés de chiffrement doivent être sauvegardées séparément des données. Sans elles, les champs médicaux, photos et factures chiffrés ne sont pas récupérables.

## Checklist de mise en production

| Contrôle | Exigence |
|---|---|
| Mode | `DEPLOYMENT_MODE` explicite et validé |
| Réseau interne | Aucun accès Internet entrant, ports DB/Redis non publiés |
| Authentification | JWT, revalidation DB du compte, MFA activable, refresh révocable |
| Autorisation | RBAC serveur et clinic scope sur toutes les routes métier |
| Données | Photos et factures chiffrées, exports privés, audits scoppés |
| IA | Allowlist, provider explicite, quotas, plafond de sortie, refus fail-closed |
| WhatsApp | Activation explicite, token serveur, opt-out respecté, faux succès interdit en production |
| Intégrations | Email/SMS/S3/Sentry/Jitsi désactivés en mode interne |
| Migrations | Une seule tête Alembic et migration appliquée sur une copie restaurable |
| Sauvegarde | Support séparé, chiffrement, rotation et restauration testée |
| Validation | `scripts/verify_ready_to_go.sh` puis `scripts/first_deploy.sh` |

Cette release est **Enterprise Ready sous réserve de la validation sur le serveur cible**, notamment le démarrage Docker réel, PostgreSQL, Redis/Celery, le test de restauration, le firewall et les tests d’acceptation métier avec des données non sensibles puis un jeu contrôlé de production.
