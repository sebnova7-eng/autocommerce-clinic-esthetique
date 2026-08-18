# Sources externes de l’audit OpenAI — 2026-08-17

## [1] API key safety
URL: https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety

Faits retenus : OpenAI recommande des clés uniques, interdit l’exposition des clés dans les environnements client/browser/mobile, déconseille de committer une clé, recommande les variables d’environnement ou un gestionnaire de secrets, la rotation/surveillance et l’IP allowlisting lorsque disponible.

## [2] Production best practices
URL: https://developers.openai.com/api/docs/guides/production-best-practices

Faits retenus : utiliser des projets staging/production séparés, limiter l’accès au projet de production, configurer limites et alertes de dépense, gérer les clés hors code et suivre les rate limits/coûts.

## [3] Data controls
URL: https://developers.openai.com/api/docs/guides/your-data

Faits retenus : les données API ne sont pas utilisées pour l’entraînement par défaut; les logs d’abus peuvent contenir prompts/réponses et être conservés jusqu’à 30 jours par défaut; Zero Data Retention/Modified Abuse Monitoring sont soumis à éligibilité/approbation; les contrôles BAA/Healthcare Addendum et l’éligibilité endpoint/modèle doivent être validés pour des données de santé.

## [4] Image edits API reference
URL: https://developers.openai.com/api/reference/resources/images/methods/edit/

Faits retenus : l’endpoint d’édition supporte les modèles GPT Image, dont gpt-image-1; les images peuvent être envoyées en référence; les sorties GPT Image comprennent b64_json par défaut; l’API documente prompt, modèle, taille, qualité et output_format.

## [5] Speech-to-text
URL: https://developers.openai.com/api/docs/guides/speech-to-text

Faits retenus : l’API audio accepte des fichiers jusqu’à 25 MB; gpt-transcribe est recommandé pour une nouvelle transcription générale; whisper-1 reste documenté pour certains usages; les modèles et paramètres doivent être vérifiés pour la qualité française clinique et la conformité.

## Constat local corrélé

Le code utilise actuellement /v1/chat/completions, OpenAI Images Edits avec gpt-image-1 et Audio Transcriptions avec whisper-1. Aucun appel OpenAI réel n’a été réalisé pendant l’audit et aucune clé réelle n’a été lue ou affichée.
