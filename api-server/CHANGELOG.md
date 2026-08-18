# CHANGELOG — AutoCommerce Clinic

## [1.1.0] — 2026-07-30

### Fixed
- **NC-M01** — `services/factures.py`: `marquer_payee()` lève désormais `ValueError` si la facture est déjà marquée payée (double paiement interdit).
- **NC-R01** — `config.py`: ajout d'une validation en production qui refuse `CORS_ORIGINS = ["*"]` (secrets exposure).
- **NC-R02** — `services/clinic_settings.py`: ajout d'un cache LRU en mémoire (max 128 entrées, TTL 300 s) pour les paramètres cliniques, reduisant les appels DB récurrents.
- **NC-R03** — `models/omnicanal.py`, `services/omnicanal/__init__.py`: import `Utilisateur` ajouté, re-export explicite `ChannelAdapter as ChannelAdapter`. `ruff check . --select F,E9` passe désormais sans erreur.

### Added (Tests)
- **NC-M02** — `tests/test_copilote_crm_coverage.py` : 16 tests nouveaux, couverture `copilote_crm` portée à **98 %** (seuil ≥ 60 %).
- **NC-M03** — `tests/test_dashboard_ia_coverage.py` : 24 tests nouveaux, couverture `dashboard_ia` portée à **98 %** (seuil ≥ 55 %).
- **NC-M04** — `tests/test_business_intelligence_coverage.py` : 14 tests nouveaux, couverture `business_intelligence` portée à **100 %** (seuil ≥ 55 %).
- **NC-M05** — `tests/test_workflow_engine_coverage.py` : 12 tests nouveaux, couverture `workflow_engine` portée à **57 %** (seuil ≥ 55 %).
- **NC-M06** — `client/src/__tests__/shared-const.test.ts`, `auth-context.test.ts`, `utils.test.ts` : 16 tests vitest frontend, tous verts.

### Updated
- `tests/test_factures.py`: test `marquer_payee_twice` corrigé pour attendre `ValueError`.
- `tests/test_config_security.py`: fixture `_settings` mise à jour avec `cors_origins`.

### Results
- **pytest** : 466 passed, 1 skipped, 0 failed
- **vitest** : 16 passed, 0 failed
- **ruff** : 0 erreur F/E9
