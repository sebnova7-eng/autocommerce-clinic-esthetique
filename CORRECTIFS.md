# Rapport de Rectification Technique — AutoCommerce Clinic

Le présent document expose les mesures correctives apportées à l'architecture logicielle de la solution AutoCommerce Clinic. Suite à l'audit technique identifiant plusieurs régressions et bugs bloquants, une intervention complète a été réalisée pour restaurer l'intégrité du système de déploiement et renforcer la sécurité globale de l'application.

L'intervention s'est concentrée sur la résolution des erreurs de structure du monorepo, la sécurisation des conteneurs Docker et la mise à jour des dépendances critiques. Le tableau ci-dessous synthétise les corrections majeures apportées par rapport à la version précédente.

| Composant | Nature du Problème | Solution Appliquée |
| :--- | :--- | :--- |
| **Monorepo** | Absence de `pnpm-lock.yaml` local | Régénération et synchronisation du lockfile racine et local |
| **Backend API** | Dépendance système manquante | Intégration de `poppler-utils` pour le traitement PDF |
| **Sécurité Docker** | Permissions de fichiers incorrectes | Création préventive des dossiers de données avec `chown` |
| **Frontend** | Version pnpm non définie | Épinglage de la version 10.15.1 pour la cohérence du build |
| **Infrastructure** | En-têtes HTTP manquants | Configuration des politiques CSP et X-Frame-Options dans Nginx |

### Optimisation du Déploiement Conteneurisé

La restructuration du projet en monorepo avait introduit une rupture dans le processus de construction des images Docker. Le fichier `pnpm-lock.yaml`, essentiel pour garantir des installations reproductibles, a été restauré au sein du répertoire `autocommerce-app`. Cette modification permet à la commande `docker compose build` de s'exécuter sans erreur lors de l'étape de copie des fichiers de configuration. Parallèlement, le fichier de verrouillage à la racine a été mis en conformité avec les dépendances patchées, notamment pour le paquet `wouter`.

### Sécurisation et Mise à Jour des Dépendances

Le serveur API a bénéficié d'une révision de sa configuration de sécurité. Les vulnérabilités identifiées dans les bibliothèques Python ont été éliminées par une montée en version ciblée. Le tableau suivant détaille les changements de versions effectués dans le fichier `requirements.txt`.

| Bibliothèque | Ancienne Version | Nouvelle Version | Impact |
| :--- | :--- | :--- | :--- |
| **cryptography** | 49.0.0 | 50.0.0 | Résolution de vulnérabilités CVE |
| **pytest** | 8.3.5 | 9.0.3 | Amélioration de la stabilité des tests |
| **starlette** | >=0.46.2 | 0.46.2 (fixe) | Prévention des régressions mineures |

Enfin, l'image Nginx servant l'application frontend intègre désormais des en-têtes de sécurité conformes aux standards industriels. Ces mesures protègent l'application contre les attaques de type *Clickjacking* et *Content Sniffing*, tout en définissant une politique de sécurité du contenu (CSP) stricte pour limiter les vecteurs d'injection de scripts.

L'archive ainsi produite constitue une version stable, vérifiée et prête pour une mise en production immédiate. Il est recommandé de suivre scrupuleusement le guide de déploiement actualisé pour finaliser l'installation sur le serveur cible.
