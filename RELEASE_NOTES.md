# Release Notes — AutoCommerce Clinic Enterprise

## Commercial Production Release — 2026-08-17

### Verdict

**GO — COMMERCIAL PRODUCTION RELEASE**.

Cette release correspond à la version finale réconciliée du package AutoCommerce Clinic Enterprise. La passe de reconciliation n’a ajouté aucune fonctionnalité et n’a pas modifié l’architecture validée; elle a consolidé la source de vérité, les documents et les preuves finales.

### État validé

Le backend compte **515 tests passés et 1 test skipped**. La campagne IA compte **14 tests passés**. Le full-stack, TypeScript, Vitest, le build frontend, Docker, PostgreSQL, Redis, Celery, beat, les audits de dépendances, l’authentification/MFA, les cookies de refresh, la rotation/reuse, l’isolation tenant, le booking public, la Public Gateway, le Private Clinical Core, Nginx, la frontière réseau et le backup/restore sont PASS.

Le release gate final a produit `EXIT 0` et :

```text
GO: tous les contrôles critiques exécutés avec succès.
```

### Version et migrations

La tête Alembic réellement exécutée est `c9d0e1f2a3b4`. Cette valeur est la seule tête référencée dans les documents finaux et dans le manifeste.

### Architecture réseau

La surface publique est `app.autocommerce-clinic.com` et `pub.api.autocommerce-clinic.com`, avec `/api/public`, booking, landing et webhooks nécessaires. La surface privée est `clinic.autocommerce-clinic.local` et `api.autocommerce-clinic.com`, avec `/api/private`, `/api/v1` legacy, patients, dossiers, facturation, stock, agenda, IA et audit. PostgreSQL et Redis restent internes.

Le contrôle runtime final a confirmé : public gateway `200`, public vers private `404`, listener privé bloqué depuis l’interface publique et private authentifié `200`.

### Preuves et packaging

La source de vérité est `FINAL_RELEASE_GATE.log`. Les commandes, dates, exit codes et fichiers de preuve sont détaillés dans `RELEASE_EVIDENCE_FINAL.md`. Le package final est `AutoCommerce-Clinic-Enterprise-Commercial-Production-Ready-FINAL-2026-08-17.zip` et son empreinte est dans `SHA256SUMS.txt`.

### Limites de déploiement

Le package est techniquement validé en staging. Avant l’ouverture production chez une clinique, il faut configurer et tester le DNS réel, le TLS réel, le firewall réel, le VPN/réseau clinique réel, le backup externe et les credentials des fournisseurs externes. Ces éléments ne sont pas présentés comme déjà validés.
