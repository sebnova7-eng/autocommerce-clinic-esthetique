# AutoCommerce Clinic Enterprise — Rapport final OpenAI et sécurité IA

## Verdict final

> **`ENTERPRISE READY — MEDICAL AI DISABLED`**

Les trois blockers techniques Enterprise ont été corrigés et validés sur le code courant. La campagne navigateur Playwright a été exécutée contre le staging Docker réel, Redis a été validé en concurrence multi-processus avec deux cliniques, le fail-closed Redis indisponible a été démontré, et un appel provider synthétique réel a été effectué sans PHI. Les 76 tests IA historiques, les 17 tests Enterprise, le backend complet et la suite frontend restent verts.

Ce verdict ne signifie **pas** que l’envoi de données médicales à OpenAI est contractuellement ou réglementairement approuvé. Le mode médical reste désactivé par défaut et doit rester ainsi jusqu’à la clôture des validations externes décrites à la section 8.

## 1. Périmètre et environnement de preuve

La validation a porté sur `/home/ubuntu/work_autocommerce_reconciliation/`. Le staging Docker existant a été reconstruit pour API, worker et beat depuis la copie de code corrigée, tout en conservant les services PostgreSQL, Redis, le réseau staging, les volumes et les secrets hors dépôt. Les conteneurs de validation étaient `autocommerce_api`, `autocommerce_worker`, `autocommerce_beat`, `autocommerce_redis`, `autocommerce_postgres` et `autocommerce_web`.

La campagne navigateur a utilisé `http://127.0.0.1` sur le port 80 via le reverse proxy staging et l’API réelle. Aucun mock n’a remplacé les frontières d’authentification, de cookie, de tenant ou de politique Medical AI. Le seed Clinic B a été exécuté dans le conteneur API depuis `/app/seed_tenant_isolation.py` et a confirmé `patient_id=2` pour la clinique B.

Aucune donnée patient réelle n’a été utilisée dans la validation provider. Les prompts provider étaient limités à des chaînes synthétiques de contrôle et les preuves enregistrent des longueurs et empreintes SHA-256 plutôt que leur contenu opérationnel.

## 2. Corrections techniques clôturées

### 2.1 Isolation tenant des simulations IA — CLOSED

Les routes et services de simulation propagent désormais `current_user["clinic_id"]`. Les lectures filtrent simultanément la simulation, le patient et la clinique authentifiée. Le patient doit appartenir à la clinique avant consentement, lecture photo ou appel externe. Une tentative Clinic A vers la ressource Clinic B est refusée sans divulgation de la ressource.

### 2.2 Budgets IA par clinique — CLOSED

`reserve_budget` résout le tenant à partir d’un identifiant serveur explicite, d’un sujet backend déjà scoppé ou du contexte clinique authentifié. Il ne fait jamais confiance à un `clinic_id` fourni par la payload frontend. En production Enterprise, l’absence de contexte clinique bloque l’appel.

Redis utilise une réservation atomique partagée pour les requêtes utilisateur, les tokens journaliers, les tokens mensuels et les requêtes par clinique. Le fallback mémoire conserve les mêmes dimensions de quota pour les environnements de test et de développement. La propagation vers les clients LLM, le runtime agent et les services IA concernés a été validée.

### 2.3 Privacy Medical AI fail-closed — CLOSED techniquement

`MEDICAL_AI_PROVIDER_APPROVED=false` et `MEDICAL_AI_STORE_RAW_TRANSCRIPTION=false` sont les valeurs par défaut. Le Scribe vérifie le tenant du patient et du dossier, puis exige l’approbation serveur avant toute sortie externe. L’audio médical et la simulation image passent par le même gate. La transcription brute n’est pas conservée par défaut et les journaux sensibles sont redacted.

L’activation éventuelle exige également `LLM_ENABLED=true`, l’intégration `ai` autorisée, un provider présent dans l’allowlist et une clé provider disponible. Le frontend ne peut pas modifier cette décision.

## 3. Résultats des campagnes de tests

| Contrôle | Résultat final | Preuve principale |
|---|---:|---|
| Campagne configuration/LLM historique | **29/29** | `openai-fixes-evidence/AI_CONFIG_LLM_FINAL.log` |
| Campagne agent/workflow/LLM historique | **28/28** | `openai-fixes-evidence/AI_AGENT_WORKFLOW_FINAL.log` |
| Campagne confirmation/RBAC historique | **19/19** | `openai-fixes-evidence/AI_CONFIRMATION_RBAC_FINAL.log` |
| Total IA historique | **76/76** | Trois campagnes séparées |
| Tests Enterprise security | **17/17** | `openai-fixes-evidence/ENTERPRISE_SECURITY_FINAL.log` |
| Backend complet | **532 passed, 1 skipped** | `evidence-final/backend_full_final_after_rebuild.log` |
| Frontend Vitest | **67 passed dans 12 fichiers** | `evidence-final/frontend_test_final_cleanest.log` |
| Frontend TypeScript | **PASS** | `evidence-final/frontend_check_final_cleanest.log` |
| Frontend build | **PASS** | `evidence-final/frontend_build_final_cleanest.log` |
| Playwright staging Docker | **4/4 passed** | `evidence-final/playwright_final_after_rebuild.log` |

Le test frontend précédent qui avait chargé le fichier Playwright dans Vitest a été corrigé au niveau de la configuration du runner, avec exclusion explicite de `node_modules`, `dist`, `coverage` et `e2e`. Aucun test fonctionnel n’a été modifié pour faire passer artificiellement une assertion.

## 4. Campagne Playwright E2E réelle — 4/4

| Scénario réel | Résultat | Contrôle démontré |
|---|---:|---|
| Authentification, refresh HttpOnly, logout et révocation | **PASS** | Cookie refresh HttpOnly, absence de token dans Web Storage, refresh révoqué après logout |
| Setup, confirmation et vérification MFA | **PASS** | Secret généré côté serveur, OTP réel, nouveau access token, statut activé puis désactivation contrôlée |
| Clinic A/B IDOR et frontière Public/Internal | **PASS** | Patient Clinic B non lisible depuis A, accès B autorisé à B, override `clinic_id=2` sans fuite, endpoints privés anonymes refusés |
| Medical AI fail-closed | **PASS** | Patient synthétique accessible à son tenant, endpoint Scribe privé renvoyant HTTP 503 lorsque les services/politique Medical AI sont désactivés, accès anonyme refusé |

La campagne a utilisé les comptes staging injectés hors dépôt et le seed Clinic B réel. Le scénario Clinic A/B peut attendre la fenêtre du rate limit de login; ce délai reflète le contrôle réel et n’a pas été contourné.

## 5. Validation Redis multi-processus et fail-closed

La campagne `scripts/redis_multi_process_campaign.py` a lancé deux processus Python distincts avec Redis partagé, deux cliniques (`1` et `2`) et une limite de requête clinique égale à `1`. Les deux processus ont terminé proprement. Pour chaque clinique, une réservation a réussi et la réservation concurrente a reçu `Quota IA dépassée`, transformée par l’application en HTTP 429 dans le chemin API.

| Clinique | Réservations acceptées | Réservations refusées | Erreurs processus |
|---:|---:|---:|---:|
| 1 | **1** | **1 × 429** | 0 |
| 2 | **1** | **1 × 429** | 0 |

La sonde `scripts/redis_fail_closed_probe.py` a ensuite arrêté Redis, tenté une réservation en environnement `production`, puis redémarré Redis et attendu son état healthy. Le résultat est : `FAIL_CLOSED_PASS — Compteur IA indisponible : appel refusé en production`. Aucun fallback mémoire n’a été utilisé pour autoriser une consommation sans compteur central en production.

## 6. Validation provider synthétique

Une requête réelle a été envoyée depuis l’environnement sandbox au endpoint OpenAI-compatible configuré par l’environnement : `https://api.manus.im/api/llm-proxy/v1/chat/completions`, modèle `gpt-5-mini`. Il s’agit d’une preuve de fonctionnement provider-compatible avec données synthétiques, et non d’une preuve contractuelle ou d’une validation directe du compte OpenAI de production cible.

| Mesure | Valeur |
|---|---:|
| Statut provider | **PROVIDER_PASS** |
| Prompt synthétique | Deux messages system/user, aucune PHI, aucun patient_id |
| Paramètres | `temperature=0.0`, `max_completion_tokens=16`, `stream=false` |
| Latence observée | **2264 ms** |
| Usage retourné | **108 tokens** : 29 prompt, 79 completion, dont 64 reasoning |
| Modèle | **gpt-5-mini** |
| Test quota clinique | **PASS_429**, limite `1`, clinique synthétique `9982` |

La preuve complète est conservée dans `evidence-final/openai_synthetic_proxy_campaign.json`. Les valeurs d’empreinte permettent de vérifier l’identité des chaînes de test sans réintroduire leur contenu dans le rapport.

## 7. Matrice CLOSED / OPEN-EXTERNAL

| Domaine | Statut | Limite d’interprétation |
|---|---|---|
| Isolation tenant des simulations | **CLOSED** | Prouvé par code, tests ciblés et E2E Clinic A/B |
| Budgets IA par clinique | **CLOSED** | Prouvé par tests mémoire, Redis multi-processus et 429 concurrent |
| Redis indisponible en production | **CLOSED** | Prouvé par arrêt Redis staging et refus fail-closed |
| Privacy Medical AI par défaut | **CLOSED techniquement** | Prouvé par gate serveur, 503 E2E, absence de stockage brut par défaut et logs redacted |
| Frontière Public/Internal et RBAC | **CLOSED** | 17/17 tests Enterprise et E2E privé/public |
| Provider-compatible synthétique | **CLOSED pour le chemin testé** | Appel réel sans PHI; preuve effectuée via proxy sandbox |
| BAA/Healthcare Addendum, rétention, ZDR, résidence | **OPEN / EXTERNAL** | Validation à obtenir auprès de l’organisation et du fournisseur pour le compte cible |
| Éligibilité exacte des modèles/endpoints médicaux | **OPEN / EXTERNAL** | `gpt-5-mini` synthétique ne valide pas les flux audio/image médicaux ni les conditions du compte cible |
| Clé, allowlist et configuration du compte OpenAI production | **OPEN / EXTERNAL** | La présence d’une clé sandbox/proxy ne constitue pas une preuve du compte cible |
| Certification juridique, réglementaire ou contractuelle | **OPEN / EXTERNAL** | Ne peut pas être inventée par ce rapport |

## 8. Limites et éléments non applicables

L’API actuelle ne propose pas de route update/delete pour `SimulationIA`; aucune surface artificielle n’a été ajoutée pour satisfaire un scénario absent. Si ces opérations sont introduites, elles devront recevoir le tenant authentifié et être couvertes par les mêmes tests négatifs.

Le provider synthétique n’a pas utilisé de dossier, transcription, photo, nom, téléphone, email ou identifiant de patient. La campagne ne valide donc pas une autorisation médicale externe; elle valide le comportement technique contrôlé lorsque les données sont synthétiques et les quotas bornés.

## 9. Décision de release

La release est **Enterprise Ready pour un fonctionnement avec Medical AI désactivée**. Elle peut être livrée pour l’exploitation clinique non médicale couverte par les tests et pour une validation staging contrôlée. Les flags de production doivent conserver le fail-closed jusqu’à obtention et vérification des pièces externes.

La release ne doit pas être annoncée comme autorisant l’envoi de données médicales à OpenAI. Pour cette activation ultérieure, l’organisation doit d’abord confirmer par écrit les engagements fournisseur, la rétention, la résidence, l’éligibilité du modèle et de l’endpoint, les contrôles de compte, la supervision des coûts et la procédure de révocation. Ce rapport n’invente aucune preuve juridique ou contractuelle.

## 10. Références officielles

Les recommandations de gouvernance fournisseur et de protection des clés sont comparées aux sources officielles suivantes. OpenAI recommande de ne jamais exposer une clé dans le navigateur et de la conserver côté serveur ou dans un gestionnaire de secrets [1]. Les bonnes pratiques de production recommandent des projets séparés, des limites et alertes de dépense et un contrôle restreint du projet de production [2]. Les contrôles de données précisent que l’utilisation pour l’entraînement est désactivée par défaut, tout en signalant que certains logs d’abus peuvent contenir prompts/réponses et être conservés par défaut; l’éligibilité Zero Data Retention, BAA/Healthcare Addendum, endpoint et modèle doit être validée séparément pour les données de santé [3].

[1]: <https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety> "OpenAI — Best Practices for API Key Safety"
[2]: <https://developers.openai.com/api/docs/guides/production-best-practices> "OpenAI — Production Best Practices"
[3]: <https://developers.openai.com/api/docs/guides/your-data> "OpenAI — Your Data and API Data Controls"
[4]: <https://developers.openai.com/api/reference/resources/images/methods/edit/> "OpenAI — Images Edit API Reference"
[5]: <https://developers.openai.com/api/docs/guides/speech-to-text> "OpenAI — Speech-to-Text Guide"
