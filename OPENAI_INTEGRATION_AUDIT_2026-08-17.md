# AutoCommerce Clinic — Audit de l’intégration OpenAI
## Audit sécurité, confidentialité et readiness Enterprise — 2026-08-17

> **Verdict : l’application est installable avec l’IA désactivée par défaut, mais l’activation OpenAI pour des données médicales, audio ou images en production est `NO-GO CONDITIONNEL` tant que les constats critiques ci-dessous ne sont pas corrigés ou formellement acceptés avec les garanties contractuelles et opérationnelles correspondantes.**

## 1. Périmètre et méthode

L’audit a porté sur la copie `/home/ubuntu/work_autocommerce_reconciliation/` et sur les chemins OpenAI réellement présents dans le code backend. Aucun secret réel n’a été lu ni affiché, et aucun appel réseau OpenAI réel n’a été effectué. Les contrôles ont combiné lecture du code, recherche de secrets, validation statique, tests backend ciblés et comparaison avec la documentation officielle OpenAI consultée le 17 août 2026.

Les chemins examinés sont le client LLM texte `api-server/core/llm_client.py`, la transcription audio `api-server/core/openai_audio.py`, le Scribe médical `api-server/api/v1/scribe_ia.py`, l’édition d’images `api-server/services/simulation_morphing.py`, les routes d’assistant `api-server/api/v1/assistant_ia.py`, l’agent historique `api-server/services/clinic_agent.py`, les outils métier, les budgets LLM, les contrôles de sécurité IA, les consentements, les routes de simulation et les exemples de configuration.

## 2. Inventaire des appels OpenAI

| Flux | Appel réel | Données envoyées | Contrôles présents | État de l’audit |
|---|---|---|---|---|
| Texte LLM | `POST https://api.openai.com/v1/chat/completions` | Messages système, question utilisateur, contexte éventuellement nettoyé | Clé backend, allowlist provider, budgets, retry, timeout, cache mémoire | `PASS PARTIEL` |
| Transcription audio | SDK `OpenAI(...).audio.transcriptions.create` avec `whisper-1` | Audio médical brut jusqu’à 25 Mo | Rôle médecin/directrice/admin, taille, flag IA, allowlist, budget, fichier temporaire supprimé | `HIGH RISK / NON VALIDÉ PHI` |
| Scribe SOAP | Chat LLM après transcription | Transcription médicale brute insérée directement dans le prompt | Rôle, réponse JSON demandée, fallback honnête, persistance locale | `BLOCKER PRIVACY` |
| Édition image | `POST https://api.openai.com/v1/images/edits` avec `gpt-image-1` | Photo clinique déchiffrée du patient | Consentement `simulation_ia`, rôle, scope photo dans la génération, watermark, chiffrement au repos | `HIGH RISK / SCOPE À CORRIGER` |
| Copilote CRM | Client LLM générique | Données CRM pseudonymisées par appel | `pseudonymize_pii`, fallback `LLMUnavailable`, budget | `PASS PARTIEL` |
| Dashboard IA | Client LLM générique pour certaines recommandations | Données préparées/pseudonymisées selon le service | Lecture seule, fallback explicite, budget | `PASS PARTIEL` |
| Agent ReAct | Client LLM générique et outils déclarés | Demande utilisateur, contexte nettoyé, observations de tools | Max steps, max tools, budgets, refus médical, tools limités | `PASS PARTIEL` |

Le frontend ne contient pas de clé OpenAI et ne fait pas d’appel direct au fournisseur. La clé est attendue côté backend, ce qui correspond à la recommandation OpenAI de ne jamais déployer une clé dans un navigateur ou une application cliente [1].

## 3. Verdicts par domaine

### 3.1 Secrets et exposition réseau — `PASS`

La configuration porte `OPENAI_API_KEY` côté backend et le modèle clinique laisse la variable vide par défaut. Le scan de secrets de la release a retourné `OK`, aucun motif de clé `sk-...` exploitable n’a été détecté dans la copie, et l’archive livrée ne contient pas de fichier `.env` réel. Les tests du client LLM vérifient qu’une clé vide explicite dans les settings ne retombe pas silencieusement sur une variable d’environnement résiduelle.

La configuration production refuse également les secrets critiques absents ou placeholders lorsque `ENV=production`. Les contrôles restent toutefois dépendants de la gestion réelle des secrets du VPS : coffre ou secret manager, rotation, permissions du fichier, séparation staging/production et éventuelle IP allowlist OpenAI doivent être configurés hors dépôt. OpenAI recommande notamment un stockage via variables d’environnement ou gestionnaire de secrets, des clés distinctes et la surveillance/rotation des clés [1].

### 3.2 Activation fail-closed — `PASS PARTIEL`

L’IA est désactivée par défaut (`LLM_ENABLED=false`). Le client refuse un provider absent de `LLM_PROVIDER_ALLOWLIST`, refuse l’appel sans clé et renvoie `LLMUnavailable` plutôt qu’un texte fabriqué. En production, l’indisponibilité de Redis bloque la réservation de budget au lieu de laisser passer une consommation non gouvernée.

Le point à améliorer est la centralisation : les appels texte passent par `LLMClient`, mais l’édition image et l’audio possèdent leurs propres garde-fous, leurs modèles et leurs paramètres. Une politique OpenAI unique devrait vérifier provider, modèle autorisé, budget, projet, classification des données et journalisation avant tout flux externe.

### 3.3 Minimisation et données médicales — `FAIL / BLOCKER`

Le projet possède une fonction `pseudonymize_pii` et plusieurs flux CRM l’utilisent correctement avant `llm.chat`. Le Dashboard IA utilise également des structures préparées et pseudonymisées sur les chemins concernés.

Cependant, la minimisation n’est pas une garantie centrale du client LLM. Dans `assistant_ia.ask_llm`, la question utilisateur est envoyée telle quelle après les garde-fous; seule la partie `context` passe par `sanitize_user_context`. Dans `scribe_ia.process`, la transcription médicale brute est directement interpolée dans le prompt SOAP et est ensuite persistée telle quelle dans `MedicalScribeSession`. Le chemin audio envoie par définition l’enregistrement médical brut à OpenAI. Ces flux ne doivent pas être considérés comme pseudonymisés.

L’absence de données utilisées pour l’entraînement OpenAI ne signifie pas absence de traitement ou de conservation opérationnelle. La documentation OpenAI indique que les données API ne sont pas utilisées pour entraîner les modèles par défaut, mais que les logs de surveillance d’abus peuvent contenir des prompts/réponses et être conservés jusqu’à 30 jours par défaut; les contrôles Zero Data Retention ou Modified Abuse Monitoring nécessitent une éligibilité et une approbation [3]. Pour des données de santé, l’équipe doit donc valider contractuellement le BAA/Healthcare Addendum, les paramètres de rétention, l’éligibilité des endpoints/modèles et les exigences réglementaires applicables avant activation.

### 3.4 Prompt injection, extraction de secrets et escalade médicale — `PASS PARTIEL`

Les garde-fous déterministes bloquent les motifs d’injection de prompt, d’extraction de secret et les demandes d’escalade médicale avant appel LLM ou agent. La campagne `test_ai_security_campaign.py` couvre ces catégories et vérifie l’absence d’appel LLM pour une demande de diagnostic/posologie. Les sorties indiquent clairement l’indisponibilité du LLM au lieu de fabriquer une réponse.

La couverture est principalement fondée sur des motifs regex et des tests représentatifs. Elle ne constitue pas une garantie de détection universelle contre l’obfuscation, les langues supplémentaires, les images/audio adversariaux ou les attaques multi-tours. Une campagne de red-team indépendante reste nécessaire avant exposition clinique.

### 3.5 Actions sensibles et confirmation humaine — `PASS PARTIEL`

L’agent historique `clinic_agent` possède une chaîne de confirmation persistée : demande initiale, code de confirmation, consommation du code, exécution, journal d’audit et contrôle RBAC. Les tests `test_assistant_agent.py` passent avec 19 tests, dont confirmation d’annulation de rendez-vous et refus RBAC après confirmation.

Le runtime ReAct `assistant_ia.py` actuellement exposé construit toutefois un registre différent, limité à `search_patient`, `revenue_30d`, `draft_whatsapp` et `at_risk_patients`. Sa politique système demande une confirmation pour les actions sensibles, mais l’exécution générique de `AgentRuntime` appelle directement le tool sélectionné; elle ne contient pas de vérification indépendante d’un objet de confirmation. Les tools sensibles du catalogue historique ne semblent donc pas être le même registre que celui du runtime ReAct. Cette divergence doit être résolue par une source de vérité unique et un garde-fou applicatif non contournable par le modèle.

### 3.6 Isolation tenant et RBAC — `FAIL / HIGH`

Les tools de recherche et de chiffre d’affaires appliquent des contrôles de clinique/rôle sur leurs chemins principaux. La génération de simulation vérifie le `clinic_id` lors de la sélection de la photo source, et les consentements interrogent également `clinic_id` lorsqu’il est fourni.

Deux problèmes de conception sont toutefois visibles dans les routes de simulation :

1. `post_simulation` reçoit `current_user` mais n’envoie pas `current_user["clinic_id"]` à `generer_simulation_ia`. En mode Enterprise, où `settings.clinic_id` doit rester globalement absent, le service peut échouer avec « Contexte clinique obligatoire » au lieu d’utiliser le tenant authentifié.
2. `view_simulation` reçoit `current_user` mais appelle `get_decrypted_simulation` avec seulement `simulation_id` et `patient_id`. Le service de lecture filtre sur ces deux identifiants, pas sur la clinique de l’utilisateur. La route ne réalise pas de vérification explicite que le patient et la simulation appartiennent au tenant courant.

Ces deux chemins doivent être corrigés et testés avec deux cliniques distinctes avant toute activation image. Le fait que le backend général dispose de tests d’isolation ne suffit pas à valider ces routes IA spécifiques.

### 3.7 Budgets, coûts et rate limits — `FAIL / HIGH`

Le projet réserve les tokens avant les appels texte/audio et refuse l’appel en production lorsque Redis est indisponible. Les limites déclarées comprennent requêtes par utilisateur/jour, tokens/jour, tokens/mois et requêtes par clinique/jour.

La clé de quota clinique de `reserve_budget` est cependant dérivée de `settings.clinic_id`, alors que le mode Enterprise interdit précisément un `CLINIC_ID` global implicite. Les appels transmettent un sujet `clinic:<current_user clinic>:user:<id>`, mais la limite clinique utilise une autre valeur issue des settings. En Enterprise, les compteurs de clinique risquent donc de devenir globaux au serveur au lieu d’être réellement séparés par clinique. De plus, le fallback mémoire de développement ne vérifie que les limites par sujet et tokens, pas la limite de requêtes par clinique; cette différence doit être explicitement couverte ou supprimée.

La gouvernance applicative doit être complétée par des projets OpenAI séparés staging/production, des alertes de dépense, des limites du projet et une procédure de rotation. OpenAI recommande les projets séparés pour isoler staging et production ainsi que le suivi des limites et dépenses [2].

### 3.8 Compatibilité API et modèles — `PASS PARTIEL / À REVALIDER`

Le flux texte utilise `/v1/chat/completions`, qui reste documenté. Le flux image utilise `gpt-image-1` et une édition multipart; le modèle et le retour base64 sont cohérents avec la documentation actuelle, qui indique que GPT Image supporte l’édition et retourne `b64_json` par défaut [4]. Le code ajoute néanmoins `response_format=b64_json` dans le formulaire; ce paramètre n’est pas présenté comme nécessaire pour GPT Image dans la référence actuelle et doit être vérifié par un test contractuel fournisseur.

Le flux audio utilise `whisper-1`, toujours documenté, mais la documentation actuelle recommande `gpt-transcribe` pour une nouvelle transcription générale et conserve `whisper-1` notamment pour certains usages de timestamps/traduction [5]. Ce n’est pas une vulnérabilité directe, mais le choix doit être documenté, testé sur le français clinique et suivi côté coût/qualité.

Aucun `organization`, `project`, endpoint régional, paramètre de résidence, contrôle de rétention ou BAA n’est configuré dans le code ou les exemples inspectés. L’absence dans le dépôt ne prouve pas l’absence dans le tableau de bord OpenAI, mais elle signifie que cette partie de la conformité n’est pas auditable depuis la release.

## 4. Résultats des validations exécutées

| Contrôle | Commande | Résultat | Preuve |
|---|---|---|---|
| Sécurité IA, config et client LLM | `ENV=test pytest -q tests/test_ai_security_campaign.py tests/test_llm_client_unavailable.py tests/test_config_security.py` | `29 passed` | `openai-audit-evidence/TARGETED_AI_CONFIG_LLM_TESTS.log` |
| Agent/workflows/CRM/LLM | `ENV=test pytest -q tests/test_block_llm_integration.py tests/test_copilote_crm_coverage.py tests/test_workflow_hardened.py tests/test_workflow_engine_coverage.py tests/test_llm_client_unavailable.py` | `28 passed` | `openai-audit-evidence/AGENT_WORKFLOW_LLM_TESTS.log` |
| Confirmation et RBAC agent historique | `ENV=test pytest -q tests/test_assistant_agent.py` | `19 passed` | `openai-audit-evidence/CONFIRMATION_RBAC_TESTS.log` |
| Compilation Python | `python3 -m compileall -q api-server` | `PASS, exit 0` | `openai-audit-evidence/COMPILEALL.log` |
| Ruff ciblé IA/OpenAI | `ruff check` sur les fichiers audités | `PASS, exit 0` | `openai-audit-evidence/RUFF.log` |
| Dépendances Python | `pip-audit -r api-server/requirements.txt` | `No known vulnerabilities found` | `openai-audit-evidence/PIP_AUDIT.log` |
| Secret scan release | `bash scripts/release_secret_scan.sh` | `PASS` | `SECRET_SCAN_FINAL.log` et scan de frontière |
| Appel OpenAI réel | Aucun appel avec une clé réelle | `NOT TESTED volontairement` | Aucun secret lu |
| Audio réel, image réelle et production Enterprise | Aucun environnement externe fourni | `NOT TESTED` | Validation contractuelle requise |

Les tests vérifient le comportement mocké et les garde-fous locaux; ils ne prouvent pas la conformité contractuelle OpenAI, la latence réelle, les limites de compte, la résidence des données ni la qualité clinique des sorties.

## 5. Actions obligatoires avant activation OpenAI avec données cliniques

| Priorité | Action requise | Critère de sortie |
|---|---|---|
| P0 | Décider formellement si audio, transcription SOAP et images patients sont autorisés vers OpenAI | BAA/Healthcare Addendum, rétention approuvée, endpoint/modèle éligible et validation DPO/clinique documentés, ou fonctionnalités désactivées |
| P0 | Corriger le Scribe médical | Minimisation/pseudonymisation documentée ou fournisseur configuré pour PHI; tests garantissant qu’aucun PII non autorisé ne part dans le prompt |
| P0 | Corriger le scope clinique des routes simulation | `clinic_id` issu de la session propagé à génération, consentement et lecture; tests Clinic A/B et IDOR négatifs |
| P0 | Corriger le budget Enterprise | Compteurs par `current_user.clinic_id`, limite clinique effectivement testée avec Redis, aucun compteur global implicite |
| P1 | Centraliser la politique LLM | Un wrapper impose provider/model allowlist, classification de données, budget, trace d’audit, timeout et refus fail-closed pour tous les flux |
| P1 | Rendre la confirmation non contournable | Une action sensible ne s’exécute que via un objet de confirmation valide côté serveur; le prompt ne doit jamais être la seule barrière |
| P1 | Ajouter les tests Scribe/audio/image | Tests de taille, clé absente, flag désactivé, tenant, consentement, suppression temporaire, payload fournisseur et erreurs 4xx/5xx |
| P1 | Configurer la gouvernance OpenAI hors dépôt | Projet staging séparé, projet production restreint, IP allowlist si disponible, alertes de dépense, limites du projet, rotation et journal de changements |
| P2 | Revalider modèles et paramètres | Contrat image multipart, modèle audio, retour JSON, quotas et coûts testés contre le compte OpenAI cible |

## 6. Conclusion opérationnelle

La release conserve une bonne base de sécurité locale : clé côté backend, IA désactivée par défaut, allowlist provider, budgets, refus sans clé, garde-fous d’injection/secrets/escalade, contrôle de consentement image et confirmation agent historique. Les tests ciblés exécutés sont verts et aucune clé réelle n’a été exposée.

Le statut ne doit toutefois pas être confondu avec une autorisation d’envoyer des données de santé à OpenAI. **Le mode commercial recommandé immédiatement est `LLM_ENABLED=false` pour les flux cliniques sensibles.** Une activation texte limitée à des données non sensibles et pseudonymisées peut être envisagée en staging avec un projet OpenAI dédié. L’activation audio/Scribe/image en production doit rester bloquée jusqu’à la résolution des constats P0 et à la validation contractuelle des données de santé.

## Références

[1]: https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety "OpenAI — Best Practices for API Key Safety"

[2]: https://developers.openai.com/api/docs/guides/production-best-practices "OpenAI — Production best practices"

[3]: https://developers.openai.com/api/docs/guides/your-data "OpenAI — Data controls in the OpenAI platform"

[4]: https://developers.openai.com/api/reference/resources/images/methods/edit/ "OpenAI API Reference — Create image edit"

[5]: https://developers.openai.com/api/docs/guides/speech-to-text "OpenAI — File transcription"
