# AutoCommerce Clinic Enterprise — Manifest de release

## Statut

`ENTERPRISE READY — MEDICAL AI DISABLED`

Le code technique est validé pour la release avec les flux Medical AI désactivés par défaut. Les validations contractuelles, réglementaires et de compte provider restent externes et ne sont pas affirmées par ce package.

## Preuves incluses

Le répertoire `evidence-final/` contient les journaux du backend complet, des tests frontend, du typecheck, du build, de la campagne Playwright staging Docker, du seed Clinic B, de la campagne Redis multi-processus, du fail-closed Redis indisponible, de la campagne provider synthétique et du scan de secrets.

Les scripts reproductibles de validation sont inclus dans `scripts/redis_multi_process_campaign.py`, `scripts/redis_fail_closed_probe.py` et `scripts/openai_synthetic_proxy_campaign.py`. Le scénario Playwright et sa configuration sont inclus dans `evidence-final/enterprise.spec.ts` et `evidence-final/playwright.config.ts`; la source active reste dans `autocommerce-app/e2e/enterprise.spec.ts`.

## Résultats de release

| Contrôle | Résultat |
|---|---:|
| Backend complet | 532 passed, 1 skipped |
| Campagnes IA historiques | 76/76 |
| Tests Enterprise security | 17/17 |
| Frontend Vitest | 67 passed dans 12 fichiers |
| TypeScript | PASS |
| Build frontend | PASS |
| Playwright staging Docker | 4/4 passed |
| Redis multi-processus | 1 PASS + 1 HTTP 429 par clinique, cliniques 1 et 2 |
| Redis indisponible en production | FAIL_CLOSED_PASS |
| Provider synthétique | PROVIDER_PASS, sans PHI, quota PASS_429 |
| Scan secrets | PASS |

## Exclusions de sécurité

Les secrets de `/home/ubuntu/staging-secrets/` ne sont pas inclus. Les fichiers d’environnement réels, clés provider, volumes Docker, bases de données et artefacts de credentials ne font pas partie de cette archive. Les répertoires `node_modules`, `.git`, `dist`, `coverage` et les sorties temporaires de tests locales sont exclus de l’archive quand ils ne sont pas nécessaires à la preuve.

## Limite d’activation médicale

Ne pas modifier `MEDICAL_AI_PROVIDER_APPROVED=false` sans validation écrite de l’organisation et du fournisseur concernant le BAA/Healthcare Addendum, la rétention, la résidence, l’éligibilité du modèle/endpoint, le compte de production, la supervision coûts et la procédure de révocation.
