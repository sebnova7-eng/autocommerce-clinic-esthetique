# Déploiement — AutoCommerce Clinic Enterprise

Le profil recommandé est `internal_single_clinic` : une clinique dispose d’une instance dédiée, d’une base PostgreSQL dédiée et d’un Redis dédié. L’API et le frontend sont liés à l’interface locale du serveur; le reverse proxy est le seul composant exposé au réseau autorisé.

La configuration commerciale distingue `app.autocommerce-clinic.com` et `pub.api.autocommerce-clinic.com` pour la surface publique, puis `clinic.autocommerce-clinic.local` et `api.autocommerce-clinic.com` pour la surface privée. Le domaine public proxifie le frontend public, `/api/public` et les webhooks explicitement nécessaires; il retourne `404` pour `/api/private` et `/api/v1`. Le domaine privé est accessible uniquement depuis le réseau clinique/VPN via les règles `allow`/`deny` et proxifie le Private Clinical Core.

## Séquence

```bash
export ADMIN_EMAIL='admin@clinique.example'
export ADMIN_PASSWORD='<mot-de-passe-fourni-hors-dépôt>'
API_ENV_FILE=api-server/.env.clinic ./scripts/verify_infrastructure.sh
./scripts/first_deploy.sh
```

Le script de déploiement valide la configuration Compose, construit les images, attend PostgreSQL et Redis, applique Alembic et vérifie les sondes de santé. Les intégrations externes sont désactivées par défaut et doivent être activées une par une, avec leurs secrets propres et leurs tests de refus.

## Reverse proxy

`nginx-production.conf` est un modèle complet public/private. Le fichier `deploy/nginx/snippets/autocommerce-private-tls.conf` fournit le socle TLS privé; remplacer les chemins et certificats par ceux de la PKI interne ou du VPN. Remplacer les CIDR d’exemple par le réseau réel de la clinique. Vérifier avec `nginx -t`, puis tester les quatre résultats attendus : Public Gateway `200`, public vers Private Core bloqué, listener privé inaccessible depuis l’interface publique et Private Core authentifié `200` depuis le réseau privé.

PostgreSQL et Redis ne doivent jamais apparaître dans une section `ports:` publique. Le firewall doit refuser les connexions entrantes non nécessaires et Docker Engine ne doit pas être publié.

## Vérification post-déploiement

Exécuter `python3 scripts/network_boundary_test.py` dans la recette locale lorsque les deux listeners sont disponibles. Cette preuve ne remplace pas la vérification du firewall, du DNS privé, du TLS et du VPN sur le VPS de la clinique.


Vérifier successivement `/health`, `/ready`, la connexion à l’interface, le login, le MFA lorsqu’il est obligatoire, le parcours patient et la réception des journaux d’audit. Une installation production ne peut être déclarée `GO` qu’après exécution du release gate dans l’environnement cible.
