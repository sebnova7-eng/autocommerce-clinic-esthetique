# Sécurité — AutoCommerce Clinic Enterprise

## Frontières de confiance

`/api/public` constitue la Public Gateway. Elle accepte uniquement les informations nécessaires à la landing, au catalogue public, aux disponibilités et aux demandes de réservation. `/api/private` constitue le Private Clinical Core et exige une authentification serveur, un rôle autorisé et un contexte clinique issu de la session.

La séparation applicative est doublée d’une séparation Nginx. Le domaine public refuse explicitement `/api/private` et `/api/v1`; le domaine privé est protégé par une allowlist des CIDR réseau clinique/VPN et proxifie le cœur clinique. Le listener privé ne doit pas être publié par DNS public. Le test `scripts/network_boundary_test.py` échoue si le listener privé devient accessible depuis l’interface publique.

Une demande publique crée un `BookingRequest` en état `pending`. Elle ne crée pas directement de patient clinique ni de rendez-vous. Un utilisateur autorisé doit l’accepter ou la refuser depuis le Private Core.

## Sessions

L’access token est conservé en mémoire JavaScript uniquement. Le refresh token est placé par le backend dans un cookie `HttpOnly`, `Secure` en production, `SameSite=lax` et limité au chemin `/api`. La rotation, la révocation, l’expiration, la détection de réutilisation, le logout et l’invalidation par changement d’état utilisateur sont testés.

## Autorisation et tenants

Le `clinic_id` transmis par le navigateur n’est jamais la source d’autorité. Les routes métier filtrent sur le contexte authentifié côté serveur. La release utilise une **application-level tenant isolation**; le scan du code et des migrations n’a pas trouvé de `ENABLE ROW LEVEL SECURITY` ni de `CREATE POLICY` PostgreSQL. Aucune RLS n’est donc revendiquée.

## Réseau, TLS et VPN

En production, le domaine public utilise un certificat TLS public; le domaine privé utilise un certificat émis par la PKI interne ou par un gestionnaire TLS accessible au VPN. Les CIDR d’exemple `10.0.0.0/8`, `172.16.0.0/12` et `192.168.0.0/16` doivent être remplacés par les réseaux réels de la clinique. Le firewall du VPS doit autoriser uniquement 80/443 selon la politique publique et le réseau VPN sur la surface privée; PostgreSQL, Redis et les ports applicatifs ne doivent jamais être exposés.

## Données et fichiers

Les données médicales, photos, factures et exports doivent rester protégés par autorisation et journalisation. Les uploads sont contrôlés par taille, type, extension et chemin; les fichiers privés ne sont pas servis comme fichiers publics. Les secrets, clés et credentials doivent rester hors de l’archive de livraison.

## IA et intégrations

L’IA n’est pas une couche d’autorisation. L’ordre obligatoire est utilisateur, authentification, contexte clinique, RBAC, politique d’agent, autorisation d’outil, puis outil. Les tests de sécurité doivent traiter les notes et messages comme des données non fiables, y compris lorsqu’ils contiennent des instructions de type prompt injection. Les fournisseurs externes sont désactivés par défaut et doivent être configurés avec une allowlist explicite.

> La sécurité technique du logiciel ne constitue pas, à elle seule, une certification réglementaire de la clinique. Les obligations dépendent du pays, de l’usage, des procédures internes et des contrats fournisseurs.
