# Installation — AutoCommerce Clinic Enterprise

Cette release s’installe comme une instance isolée par clinique sur un VPS privé. Le déploiement de référence comprend une application, PostgreSQL, Redis, Celery, un stockage persistant et un répertoire de sauvegarde séparé.

## Prérequis

Le serveur doit disposer de Docker Engine avec Compose v2, d’un firewall actif, d’un stockage persistant pour les données et d’un support de sauvegarde distinct. PostgreSQL et Redis ne doivent recevoir aucun port public.

## Configuration

Pour une recette isolée, utiliser `.env.staging.example`, `api-server/.env.clinic.staging.example` et `docker-compose.staging.yml`. Pour la production, utiliser `.env.example`, `api-server/.env.clinic.example` et `docker-compose.mono-vps.yml`. Les deux environnements doivent avoir des secrets, bases, volumes et sauvegardes distincts.

Le mode simple reste un VPS et une clinique, sans microservices supplémentaires. La surface publique peut utiliser `app.autocommerce-clinic.com` et `pub.api.autocommerce-clinic.com`; l’application clinique utilise `clinic.autocommerce-clinic.local` et `api.autocommerce-clinic.com` depuis le réseau clinique ou le VPN. Le même build frontend statique peut servir les deux surfaces, car Nginx et l’autorisation serveur imposent la frontière; un build public/privé séparé est possible si l’exploitation le requiert.

Copier les modèles sans jamais copier de credentials de production dans le dépôt :

```bash
cp .env.example .env
cp api-server/.env.clinic.example api-server/.env.clinic
chmod 600 .env api-server/.env.clinic
```

Renseigner les valeurs réelles dans un gestionnaire de secrets ou dans des fichiers protégés hors dépôt. En production, utiliser `ENV=production`, `DEPLOYMENT_MODE=internal_single_clinic`, un `CLINIC_ID` positif, des clés distinctes pour `FERNET_KEY` et `PHOTO_ENCRYPTION_KEY`, ainsi que `REFRESH_COOKIE_SECURE=true`.

## Démarrage

Après configuration, vérifier l’infrastructure puis démarrer les services :

```bash
API_ENV_FILE=api-server/.env.clinic ./scripts/verify_infrastructure.sh
./scripts/first_deploy.sh
```

Le compte administrateur initial doit être transmis par variables d’environnement hors dépôt : `ADMIN_EMAIL` et `ADMIN_PASSWORD`. Le mot de passe doit être long, unique et communiqué au client par un canal séparé.

## Première connexion

Avant ouverture commerciale, installer et tester `nginx-production.conf`, les certificats TLS publics et privés, la résolution DNS publique/privée et les règles firewall/VPN. Vérifier que le domaine public retourne `404` pour `/api/private` et `/api/v1`, tandis que le domaine privé est atteignable uniquement depuis le réseau clinique.


Après démarrage, vérifier `/health`, `/ready`, puis ouvrir l’interface via le reverse proxy TLS. Le refresh token est conservé exclusivement dans un cookie `HttpOnly`; aucun refresh token ne doit apparaître dans le navigateur JavaScript ni dans une réponse JSON.
