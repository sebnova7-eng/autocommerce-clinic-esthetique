# AutoCommerce Clinic — Release Esthétique Ready To Go

**Version de nettoyage : 18 août 2026**

Cette release est une version nettoyée et réorientée pour une clinique esthétique. Elle conserve le périmètre fonctionnel de la release Enterprise tout en supprimant les résidus de branding et de contenu non alignés avec une clinique esthétique détectés dans la landing page et les fixtures frontend.

## Corrections appliquées

| Élément | Correction |
|---|---|
| Signature d’en-tête | Remplacement de l’ancienne signature sectorielle par « Médecine esthétique » |
| Accroche hero | Remplacement de l’ancienne accroche par « Beauté naturelle, expertise médicale » |
| Image hero | Suppression de l’image d’attente non alignée et remplacement par un fond visuel neutre, premium et médical |
| Fixture de praticien | Remplacement de l’ancienne spécialité par « Médecine esthétique » |
| Références d’asset | Suppression de l’ancien asset visuel et de sa référence de checksum |
| Contrôle lexical | Aucun terme de positionnement incompatible détecté dans le code, les données, les assets et les scripts utiles de cette release |

## Vérifications exécutées

La copie nettoyée a été installée avec `pnpm install --frozen-lockfile`. Les contrôles frontend ont ensuite été exécutés : le typecheck TypeScript est passé, les tests Vitest ont produit **67 tests passés sur 12 fichiers**, et le build Vite de production est passé.

La landing page a également été lancée localement sur le port de démonstration. La capture `release-evidence/landing_page_esthetique_real.webp` montre le nouveau branding « Médecine esthétique » et « Beauté naturelle, expertise médicale », sans visuel de positionnement incompatible.

## État de préparation

> **Ready for demonstration and controlled pilot. Production deployment remains subject to target-server validation.**

La release est plus proche d’un Ready To Go grâce au nettoyage du branding et à la vérification frontend. Elle ne constitue toutefois pas une certification automatique de production : l’installation complète backend, PostgreSQL, Redis, Celery, les migrations, le firewall, la sauvegarde/restauration et la recette clinique doivent encore être validés sur l’infrastructure réelle.

## Paramétrage client avant mise en service

Le nom réel de la clinique, le logo, les couleurs, les coordonnées, les horaires, les actes esthétiques, les tarifs, les praticiens, les mentions légales et les politiques de consentement doivent être renseignés avant livraison finale au client.

Les actes de démonstration doivent rester cohérents avec l’offre réelle de la clinique, par exemple consultation esthétique, soins du visage, peelings, laser, injectables ou silhouette selon le périmètre autorisé par le client.

## Installation

Le mode local `internal_single_clinic` est recommandé pour le pilote : frontend et API derrière un accès LAN/VPN, PostgreSQL et Redis non exposés, routes publiques et webhooks désactivés par défaut.

Le mode public `enterprise` nécessite un domaine réel, TLS, DNS, reverse proxy, CORS strict, firewall, secrets gérés hors dépôt, tests d’isolation multi-clinique et validation des intégrations externes. Les fichiers Nginx fournis restent des modèles à adapter.
