# AutoCommerce Clinic Enterprise — Release Index

**Version :** Commercial Production Release 2026-08-17  
**Verdict :** GO — COMMERCIAL PRODUCTION RELEASE  
**Source de vérité :** `FINAL_RELEASE_GATE.log`  
**Head Alembic :** `c9d0e1f2a3b4`

## Documents officiels

| Document | Rôle |
|---|---|
| `RELEASE_MANIFEST.txt` | Identité et métadonnées de la release |
| `RELEASE_EVIDENCE_FINAL.md` | Résultats finaux avec commandes, dates, exit codes et preuves |
| `FINAL_COMMERCIAL_RELEASE_REPORT.md` | Rapport commercial final structuré |
| `RELEASE_NOTES.md` | Notes de version |
| `README_DEPLOYMENT.md` | Installation et déploiement |
| `DEPLOYMENT.md` | Procédure mono-VPS et reverse proxy |
| `SECURITY.md` | Sessions, RBAC, tenant isolation, IA et réseau |
| `ARCHITECTURE.md` | Architecture Public Gateway / Private Clinical Core |
| `BACKUP_RESTORE.md` | Sauvegarde et restauration |
| `OPERATIONS.md` | Exploitation quotidienne |
| `UPGRADE.md` | Upgrade et migrations |
| `ROLLBACK.md` | Retour contrôlé |

## Preuves finales

| Preuve | Contenu |
|---|---|
| `FINAL_RELEASE_GATE.log` | Gate complet, EXIT 0 et ligne GO finale |
| `STAGING_E2E_FINAL.log` | Auth, MFA, booking, rotation/reuse, tenant isolation et logout |
| `FULL_STACK_FINAL.log` | Patients, dossiers, agenda, facturation, stock, IA et logout |
| `AI_SECURITY_FINAL.log` | 14 tests IA et garde-fous médicaux |
| `NETWORK_BOUNDARY_FINAL.log` | Preuve runtime public/private |
| `NGINX_EXPOSURE_FINAL.log` | Politique Nginx bloquante |
| `BACKUP_RESTORE_VALIDATION.log` | Restore PostgreSQL isolé |
| `SECRET_SCAN_FINAL.log` | Scan de secrets |
| `FINAL_EVIDENCE_TIMESTAMP.txt` | Horodatage de la dernière campagne de preuves |

## Architecture réseau

La surface publique est `app.autocommerce-clinic.com` et `pub.api.autocommerce-clinic.com`, avec `/api/public`, booking, landing et webhooks nécessaires. La surface privée est `clinic.autocommerce-clinic.local` et `api.autocommerce-clinic.com`, avec `/api/private`, `/api/v1` legacy, patients, dossiers, facturation, stock, agenda, IA et audit. PostgreSQL et Redis restent internes.

## Package

Le package attendu est `AutoCommerce-Clinic-Enterprise-Commercial-Production-Ready-FINAL-2026-08-17.zip`; son empreinte est dans `SHA256SUMS.txt`. Les éléments propres au VPS client sont détaillés dans la section **Known deployment requirements** du rapport final.
