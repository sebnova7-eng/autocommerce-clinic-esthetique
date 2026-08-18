# Rapport de recette commerciale — Clinique Esthétique

**Destinataire :** responsable de validation et décision de vente  
**Environnement :** staging HTTPS temporaire avec PostgreSQL, Redis et données synthétiques  
**Date :** 18 août 2026

## Verdict exécutif

> **Le produit est vendable comme solution de démonstration avancée et comme pilote contrôlé, mais il ne doit pas être vendu comme une installation de production totalement finalisée tant que les canaux de notification réels ne sont pas configurés et que la recette client n’est pas signée.**

Le cœur opérationnel répond correctement : connexion par rôle, séparation des droits, création patient, rendez-vous, consentement, dossier médical esthétique, facture, paiement, réservation publique et approbation par la direction ont été exécutés en ligne. Un défaut réel de facture a été découvert pendant cette recette, corrigé dans le code, redéployé et validé par HTTP 201 pour la création puis HTTP 200 pour le paiement.

## Rôles réellement présents

| Rôle | Connexion | `auth/me` | Périmètre observé |
|---|---:|---:|---|
| Administrateur | Réussie | Réussi | Accès global et paramétrage |
| Directrice | Réussie | Réussi | Agenda, patients, factures, demandes, stock et supervision |
| Médecin | Réussie | Réussi | Agenda, patients, dossiers médicaux et consentements |
| Esthéticienne | Réussie | Réussi | Agenda, patients et consultation opérationnelle selon permissions |
| Assistante | Réussie | Réussi | Accueil, patients, agenda, facturation et stock |
| Commercial | Réussie | Réussi | Patients CRM et commissions ; accès refusé à l’agenda clinique et à la facturation |

La version ne contient pas de rôle technique séparé nommé **« secrétaire »**. Le besoin secrétaire est actuellement couvert par le rôle **assistante**. Si la clinique exige une séparation stricte entre secrétaire, assistante et accueil, il faudra ajouter un rôle distinct, ses permissions, son compte de démonstration et ses tests.

## Parcours métier simulés en ligne

| Scénario | Résultat | Preuve observée |
|---|---|---|
| Chargement public des praticiens | Réussi | 2 praticiens retournés |
| Chargement public des actes | Réussi | 5 actes esthétiques retournés |
| Connexion des six rôles | Réussie | HTTP 200 pour chaque compte |
| Vérification de session | Réussie | `auth/me` valide pour chaque rôle |
| Création d’un patient | Réussie | HTTP 201, patient créé en base |
| Création d’un rendez-vous | Réussie | HTTP 200, praticien, acte, salle et créneau enregistrés |
| Consentement d’acte | Réussie | HTTP 200, consentement valide et horodaté |
| Création d’un dossier médical | Réussie | HTTP 200, dossier créé avec l’acte et le praticien |
| Création d’une facture | **Corrigée puis réussie** | HTTP 201, facture `F-2026-0001` |
| Paiement d’une facture | Réussie | HTTP 200, statut `payee`, 9 points fidélité |
| Réservation publique | Réussie | HTTP 202, demande `pending` |
| Approbation par la directrice | Réussie | HTTP 200, demande acceptée, patient et rendez-vous créés |
| Consultation stock injectable | Réussie techniquement | HTTP 200, catalogue actuellement vide |
| Santé des canaux | Réussie techniquement | HTTP 200, canaux inspectés |

## Défaut réel découvert et corrigé

La première simulation de facture retournait HTTP 500. Le traceback backend a identifié une erreur précise : des objets `Decimal` étaient insérés directement dans la colonne JSON `actes` de PostgreSQL, provoquant `TypeError: Object of type Decimal is not JSON serializable`.

Le service a été corrigé pour convertir les montants des lignes en valeurs JSON sérialisables avant insertion. Après redémarrage de l’API, le parcours a été rejoué en ligne :

```text
Création facture : HTTP 201
Facture : F-2026-0001
Total TTC : 95.2
Paiement : HTTP 200
Statut : payee
Points fidélité : 9
```

Les tests backend après correction restent à **532 passés, 1 ignoré**, et Ruff ne signale aucune erreur.

## Contrôle des permissions

Les refus réellement confirmés sont cohérents : le commercial reçoit HTTP 403 sur l’agenda et la facturation. La première matrice attendait à tort HTTP 403 pour les lectures de factures du médecin et de l’esthéticienne ; ces routes de lecture retournent HTTP 200 avec une liste vide, tandis que les opérations d’écriture restent protégées. Il s’agissait d’une erreur de test, non d’une fuite de données.

Le contrôle doit donc distinguer : **lecture autorisée selon le rôle**, **écriture restreinte**, **suppression et anonymisation réservées à la direction ou à l’administration**.

## Notifications et communications

Le module de santé des canaux répond correctement, mais aucun canal de notification réel n’est configuré dans le staging :

| Canal | Activé | Configuré | Statut |
|---|---:|---:|---|
| WhatsApp | Oui | Non | Non configuré |
| Email | Oui | Non | Non configuré |
| SMS | Oui | Non | Non configuré |
| Instagram | Non | Oui | Désactivé |
| Facebook | Non | Oui | Désactivé |
| TikTok | Non | Oui | Désactivé |

Une demande de réservation a bien été approuvée, mais une notification externe réelle n’a pas été déclarée comme envoyée. Les conversations omnicanales étaient vides et aucun fournisseur n’était connecté. **Il ne faut donc pas vendre au client que WhatsApp, email ou SMS sont opérationnels avant configuration des comptes fournisseurs, des secrets, des modèles et des tests de réception.**

## Stock et actes esthétiques

Le catalogue public contient cinq prestations esthétiques, dont consultation, injection, laser, peeling et soin du visage. Le module stock injectable répond, mais le stock de démonstration est actuellement vide : aucun produit ni lot injectable n’a été initialisé dans cette base de recette.

Pour vendre la traçabilité injectable comme fonction démontrée, il faut ajouter un produit, créer un lot avec date d’expiration, enregistrer une utilisation liée au patient et vérifier l’apparition dans la traçabilité et les alertes. La fonction existe dans l’application, mais cette chaîne complète n’a pas été validée dans cette session.

## Cohérence de l’expérience utilisateur

L’expérience publique est cohérente avec une clinique esthétique : branding esthétique, praticiens, actes, réservation, adresse, téléphone et horaires sont visibles. Les parcours professionnels respectent les droits principaux. L’interface affiche correctement les états de réservation et le formulaire de rendez-vous.

Les points à finaliser avant une présentation de vente définitive sont le remplacement des comptes de démonstration, le chargement des actes et prix réels, la configuration d’un stock réaliste, l’ajout d’un rôle secrétaire si nécessaire, les notifications réelles et la personnalisation des coordonnées de la clinique.

## Décision recommandée pour la vente

| Décision | Recommandation |
|---|---|
| Démonstration commerciale | **GO** |
| Pilote avec données synthétiques | **GO** |
| Pilote avec une clinique réelle | **GO conditionnel**, après configuration et recette |
| Vente comme production immédiatement exploitable | **NO-GO tant que notifications, stock, secrets et infrastructure ne sont pas validés** |

La formulation commerciale recommandée est :

> **Plateforme de gestion pour clinique esthétique validée en staging avec parcours patient, agenda, dossier médical, consentement, facturation, paiement, réservation publique et contrôle des rôles. Déploiement client et intégrations de notification inclus dans la phase d’activation, avec recette finale sur l’environnement de la clinique.**

## Actions obligatoires avant signature client

La clinique doit fournir les utilisateurs et rôles définitifs, les actes et tarifs, les praticiens, les horaires, le stock initial, le fournisseur WhatsApp ou SMS, le fournisseur email, les mentions légales et les règles de conservation des données. L’équipe de déploiement doit ensuite réaliser une recette avec comptes nominatifs, sauvegarde/restauration, MFA, firewall, monitoring, notification reçue sur un téléphone ou email de test et procès-verbal signé.
