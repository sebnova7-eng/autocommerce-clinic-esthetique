# Architecture — AutoCommerce Clinic Enterprise

L’architecture est un monolithe modulaire FastAPI/React, choisi pour rester simple à exploiter sur le VPS d’une clinique. Elle ne déploie pas de microservices inutiles. Le modèle commercial est **une clinique = une instance isolée**, avec une surface publique et un cœur clinique privé.

```text
Internet ou LAN/VPN
        |
   Nginx / TLS
    /       \
Public       Private
Gateway     Clinical Core
    \       /
 PostgreSQL — Redis — Celery/Beat
```

La Public Gateway est montée sur `/api/public` et contient uniquement les routes explicitement publiques. Le Private Clinical Core est monté sur `/api/private`; `/api/v1` est conservé comme contrat de compatibilité pour les clients historiques. PostgreSQL et Redis ne sont pas publiés directement.

En production, Nginx sépare aussi les surfaces au niveau réseau : `app.autocommerce-clinic.com` et `pub.api.autocommerce-clinic.com` sont publics et ne proxifient que le web public, `/api/public` et les webhooks explicitement nécessaires. `clinic.autocommerce-clinic.local` et `api.autocommerce-clinic.com` sont privés, liés à un réseau clinique/VPN via une allowlist CIDR et seuls eux proxifient `/api/private` et `/api/v1`. Le test `scripts/network_boundary_test.py` fournit une preuve reproductible sur deux listeners : public vers Public Gateway `200`, public vers Private Core `404/refusé`, interface privée vers Private Core authentifiée `200`.

Le cœur privé porte l’authentification, le MFA, le RBAC, le contexte clinique, les patients, dossiers, agenda, facturation, stock, personnel, workflows, IA clinique, reporting et audit. Celery exécute les tâches asynchrones et planifiées via Redis. Les volumes sont persistants et les limites de ressources sont définies dans Compose.

Le frontend public sert la landing et le booking; le frontend privé peut rester le même build statique dans le mode mono-VPS, car la frontière de sécurité est le listener Nginx et l’authentification serveur, non l’existence de bundles JavaScript séparés. Une variante à deux domaines est toutefois recommandée en Enterprise.

L’isolation inter-cliniques est actuellement applicative : chaque route sensible doit dériver son scope du contexte authentifié et filtrer la ressource par `clinic_id`. Une RLS PostgreSQL n’est pas activée dans cette release et ne doit pas être documentée comme telle.
