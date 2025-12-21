# Documentation Technique pour `debug_deepseek_payload.json`

## 1. En-tête

*   **Titre**: Payload de Débogage DeepSeek pour l'Agent AiModding-Companion
*   **Description concise**: Ce fichier JSON représente un exemple de payload complet envoyé à l'API du modèle de langage DeepSeek (spécifiquement `deepseek-reasoner`). Il encapsule l'état conversationnel, les instructions système détaillées pour l'agent `AiModding-Companion`, une cartographie technique du projet, l'arborescence des fichiers et la définition exhaustive des outils natifs que l'IA peut utiliser. Il sert à contextualiser les requêtes de l'IA, à définir son comportement et à lui fournir les moyens d'interagir avec son environnement. Ce fichier est typiquement utilisé pour le débogage ou l'analyse des interactions de l'agent.
*   **Dépendances**: API DeepSeek (pour le modèle `deepseek-reasoner`), système d'agent `AiModding-Companion`, outils natifs définis via JSON Schema.

## 2. Classes & Fonctions (Concepts Structuraux et Outils)

Ce fichier n'implémente pas de classes ou de fonctions au sens programmatique, mais il définit la structure d'un message API et les capacités de l'IA.

### Structure Globale du Payload

Le payload est un objet JSON structuré comme suit :

*   **`model`** (String):
    *   **Description**: Spécifie l'identifiant du modèle de langage à utiliser pour la requête.
    *   **Valeur Exemple**: `"deepseek-reasoner"`
*   **`agent`** (String):
    *   **Description**: Identifiant ou mode de l'agent qui utilise le modèle.
    *   **Valeur Exemple**: `"Fast"`
*   **`messages`** (Array d'Objets `Message`):
    *   **Description**: Un historique ordonné de messages qui contextualise la conversation pour le modèle. Chaque message a un `role` et un `content`.
    *   **Structure de l'Objet `Message`**:
        *   **`role`** (String): Le rôle de l'expéditeur du message (e.g., `"system"`, `"user"`, `"assistant"`).
        *   **`content`** (String): Le contenu textuel du message.
    *   **Logique interne des `messages`**:
        *   **Messages `role: "system"`**: Contiennent les instructions fondamentales, la configuration de l'environnement, les règles critiques (`PROTOCOLE V4`), l'objectif de l'agent, la cartographie technique du projet (`CARTOGRAPHIE TECHNIQUE`), et l'arborescence actuelle du projet (`ARBORESCENCE PROJET`). Ces messages établissent l'identité et les connaissances de base de l'IA.
            *   **`=== INSTRUCTIONS AGENT (deepseek-reasoner) ===`**: Définit l'identité (`AiModding-Companion`), l'environnement (accès réel au FS, mémoire sémantique), et les règles opérationnelles (autonomie, vérification avant action, précision, formatage Markdown, sécurité, utilisation de la mémoire sémantique). L'objectif est l'assistance chirurgicale au développement.
            *   **`--- CARTOGRAPHIE TECHNIQUE ---`**: Une représentation JSON détaillée des domaines du projet (`agents`, `ai_core`, `config`, `features`, `root`, `sandbox`, `scripts`, `ui`, `worker`), listant les fichiers primaires et connexes, ainsi qu'un graphe des dépendances de chaque module/fichier avec des métriques (nombre de classes, lignes de code).
            *   **`--- ARBORESCENCE PROJET ---`**: Une liste hiérarchique des fichiers et dossiers du projet `AiModding-Companion`, offrant une vue d'ensemble de la structure du code.
        *   **Messages `role: "user"`**: Représentent les requêtes ou commandes de l'utilisateur, y compris les résultats d'opérations précédentes.
        *   **Messages `role: "assistant"`**: Représentent les réponses de l'IA, y compris les confirmations d'opérations ou les appels d'outils (`!native_tool`).
*   **`temperature`** (Nombre):
    *   **Description**: Contrôle la "créativité" ou le caractère aléatoire des réponses du modèle. Une valeur plus élevée rend les sorties plus diverses.
    *   **Valeur Exemple**: `0.7`
*   **`max_tokens`** (Integer):
    *   **Description**: Le nombre maximum de tokens que le modèle est autorisé à générer dans sa réponse.
    *   **Valeur Exemple**: `8000`
*   **`stream`** (Boolean):
    *   **Description**: Indique si la réponse du modèle doit être générée en temps réel (streaming) ou en une seule fois.
    *   **Valeur Exemple**: `false`
*   **`tools`** (Array d'Objets `Tool Definition`):
    *   **Description**: Une liste de définitions de fonctions/outils que le modèle peut choisir d'appeler. Chaque définition comprend le nom de l'outil, sa description et son schéma de paramètres.
    *   **Structure de l'Objet `Tool Definition`**:
        *   **`type`** (String): Le type de l'outil (toujours `"function"` pour les outils natifs).
        *   **`function`** (Object): Détails de la fonction.
            *   **`name`** (String): Le nom de la fonction/outil.
            *   **`description`** (String): Une description lisible par l'IA expliquant le but et l'usage de l'outil.
            *   **`parameters`** (Object): Un schéma JSON (conformément à la spécification OpenAI) décrivant les arguments attendus par la fonction.
                *   **`type`** (String): Toujours `"object"`.
                *   **`properties`** (Object): Une carte des noms de paramètres vers leurs définitions (type, description).
                *   **`required`** (Array of Strings, Optionnel): Une liste des noms de paramètres obligatoires.

### Outils Disponibles pour l'IA (`tools` détaillés)

Voici la liste des outils que l'agent DeepSeek peut invoquer, telle que définie dans le payload :

#### `lister_outils`
*   **Signature**: `lister_outils()`
*   **Description**: Retourne la liste exhaustive de toutes les commandes et outils disponibles pour l'IA. À utiliser si l'utilisateur demande 'liste tes commandes' ou pour vérifier les capacités.
*   **Arguments**: Aucun.
*   **Retours**: Une liste structurée des outils.
*   **Logique interne**: Permet à l'IA de s'auto-documenter sur ses propres capacités.

#### `lister_arborescence`
*   **Signature**: `lister_arborescence(chemin_relatif)`
*   **Description**: Liste les fichiers et dossiers du projet. Utiliser '.' pour la racine.
*   **Arguments**:
    *   `chemin_relatif` (string, **requis**): Le dossier racine à explorer (ex: '.' ou 'features').
*   **Retours**: Une chaîne de caractères représentant l'arborescence.
*   **Logique interne**: Fournit à l'IA une vue du système de fichiers pour la navigation et la compréhension de la structure du projet.

#### `lire_fichier`
*   **Signature**: `lire_fichier(chemin)`
*   **Description**: Lit le contenu textuel complet d'un fichier.
*   **Arguments**:
    *   `chemin` (string, **requis**): Chemin relatif du fichier (ex: 'config/settings.py').
*   **Retours**: Le contenu textuel du fichier.
*   **Logique interne**: Permet à l'IA d'accéder au code source ou à d'autres contenus textuels pour analyse, modification, etc.

#### `ecrire_fichier`
*   **Signature**: `ecrire_fichier(chemin, contenu)`
*   **Description**: Écrit du contenu dans un fichier (écrase l'existant ou crée le fichier).
*   **Arguments**:
    *   `chemin` (string, **requis**): Chemin relatif du fichier cible.
    *   `contenu` (string, **requis**): Le code ou texte à écrire.
*   **Retours**: Statut de l'opération (succès/échec).
*   **Logique interne**: Permet à l'IA de modifier ou de créer des fichiers dans le projet.

#### `comparer_fichiers`
*   **Signature**: `comparer_fichiers(source, destination)`
*   **Description**: Compare deux fichiers et retourne un diff unifié des différences. Utile pour vérifier les changements avant ou après une modification.
*   **Arguments**:
    *   `source` (string, **requis**): Chemin du fichier original (A).
    *   `destination` (string, **requis**): Chemin du fichier modifié ou à comparer (B).
*   **Retours**: Un diff unifié des différences.
*   **Logique interne**: Essentiel pour la validation des modifications et la révision de code par l'IA.

#### `creer_dossier`
*   **Signature**: `creer_dossier(chemin)`
*   **Description**: Crée un dossier et ses parents si nécessaire.
*   **Arguments**:
    *   `chemin` (string, **requis**): Chemin du dossier à créer.
*   **Retours**: Statut de l'opération.
*   **Logique interne**: Permet la gestion de l'arborescence du projet.

#### `supprimer_fichier`
*   **Signature**: `supprimer_fichier(chemin)`
*   **Description**: Supprime un fichier spécifique.
*   **Arguments**:
    *   `chemin` (string, **requis**): Chemin du fichier à supprimer.
*   **Retours**: Statut de l'opération.
*   **Logique interne**: Outil de gestion de fichiers, utilisé avec prudence (conformément aux règles de sécurité de l'agent).

#### `deplacer_fichier`
*   **Signature**: `deplacer_fichier(source, destination)`
*   **Description**: Déplace ou renomme un fichier.
*   **Arguments**:
    *   `source` (string, **requis**): Chemin actuel du fichier.
    *   `destination` (string, **requis**): Nouveau chemin ou nouveau nom.
*   **Retours**: Statut de l'opération.
*   **Logique interne**: Permet la réorganisation des fichiers du projet.

#### `copier_fichier`
*   **Signature**: `copier_fichier(source, destination)`
*   **Description**: Copie un fichier vers une nouvelle destination.
*   **Arguments**:
    *   `source` (string, **requis**): Chemin du fichier source.
    *   `destination` (string, **requis**): Chemin de la copie.
*   **Retours**: Statut de l'opération.
*   **Logique interne**: Permet la duplication de fichiers.

#### `rechercher_fichiers`
*   **Signature**: `rechercher_fichiers(pattern, chemin_racine)`
*   **Description**: Recherche des fichiers par motif (glob pattern).
*   **Arguments**:
    *   `pattern` (string, **requis**): Motif de recherche (ex: '*.py', 'test_*').
    *   `chemin_racine` (string, optionnel): Dossier de départ de la recherche (défaut: racine du projet).
*   **Retours**: Une liste de chemins de fichiers correspondants.
*   **Logique interne**: Aide l'IA à localiser des fichiers spécifiques dans le projet.

#### `rechercher_texte`
*   **Signature**: `rechercher_texte(query, path)`
*   **Description**: Recherche une chaîne de caractères dans le contenu des fichiers (Grep).
*   **Arguments**:
    *   `query` (string, **requis**): Le texte exact à rechercher.
    *   `path` (string, optionnel): Dossier où chercher ('.' par défaut).
*   **Retours**: Une liste de correspondances (fichier, ligne, contenu).
*   **Logique interne**: Permet à l'IA de trouver des occurrences de texte spécifiques dans le code ou les documents du projet.

#### `obtenir_infos_fichier`
*   **Signature**: `obtenir_infos_fichier(chemin)`
*   **Description**: Obtient les métadonnées d'un fichier (taille, dates, etc.).
*   **Arguments**:
    *   `chemin` (string, **requis**): Chemin du fichier.
*   **Retours**: Un objet ou une chaîne contenant les métadonnées du fichier.
*   **Logique interne**: Fournit des informations contextuelles sur les fichiers.

#### `generer_documentation`
*   **Signature**: `generer_documentation(cible, mode)`
*   **Description**: Génère la documentation technique (DeepDoc).
*   **Arguments**:
    *   `cible` (string, **requis**): Fichier ou dossier à documenter.
    *   `mode` (string, **requis**, enum: `"atomique"`, `"resume"`): Mode de génération de documentation.
*   **Retours**: Le contenu de la documentation générée.
*   **Logique interne**: Automatise la création de documentation, essentielle pour la maintenabilité du projet.

#### `rechercher_documentation`
*   **Signature**: `rechercher_documentation(requete)`
*   **Description**: Recherche dans la documentation existante (Markdown).
*   **Arguments**:
    *   `requete` (string, **requis**): Mots-clés ou question.
*   **Retours**: Les extraits de documentation pertinents.
*   **Logique interne**: Permet à l'IA d'accéder aux connaissances documentées du projet.

#### `update_architecture`
*   **Signature**: `update_architecture()`
*   **Description**: Régénère la carte architecturale (`config/architecture_map.json`) en analysant le code.
*   **Arguments**: Aucun.
*   **Retours**: Statut de l'opération.
*   **Logique interne**: Maintient la cartographie du projet à jour pour une meilleure compréhension structurelle.

#### `web_search`
*   **Signature**: `web_search(query)`
*   **Description**: Effectue une recherche sur Google pour trouver des informations récentes ou techniques.
*   **Arguments**:
    *   `query` (string, **requis**): Mots-clés de la recherche.
*   **Retours**: Résultats de recherche web.
*   **Logique interne**: Permet à l'IA d'accéder à des informations externes au projet.

#### `web_goto`
*   **Signature**: `web_goto(url)`
*   **Description**: Visite une page web spécifique pour en lire le contenu complet.
*   **Arguments**:
    *   `url` (string, **requis**): L'adresse URL complète (https://...).
*   **Retours**: Le contenu texte de la page web.
*   **Logique interne**: Permet à l'IA de naviguer et d'extraire des informations de pages web.

#### `web_screen`
*   **Signature**: `web_screen(filename)`
*   **Description**: Prend une capture d'écran de la page web actuelle.
*   **Arguments**:
    *   `filename` (string, optionnel): Nom du fichier image.
*   **Retours**: Chemin du fichier de la capture d'écran.
*   **Logique interne**: Utile pour visualiser l'interface utilisateur ou des éléments visuels d'une page web.

#### `backup_projet`
*   **Signature**: `backup_projet(commentaire)`
*   **Description**: Crée une archive complète du projet.
*   **Arguments**:
    *   `commentaire` (string, optionnel): Note sur le backup.
*   **Retours**: Chemin du fichier de backup créé.
*   **Logique interne**: Outil de sécurité pour sauvegarder l'état du projet.

#### `creer_backup`
*   **Signature**: `creer_backup(commentaire)`
*   **Description**: Alias pour backup_projet.
*   **Arguments**:
    *   `commentaire` (string, optionnel): Note sur le backup.
*   **Retours**: Chemin du fichier de backup créé.
*   **Logique interne**: Identique à `backup_projet`.

#### `restaurer_backup`
*   **Signature**: `restaurer_backup(nom_backup)`
*   **Description**: Restaure un backup (ATTENTION: Écrase le projet actuel).
*   **Arguments**:
    *   `nom_backup` (string, **requis**): Nom complet du fichier zip de backup.
*   **Retours**: Statut de l'opération.
*   **Logique interne**: Outil de récupération, à utiliser avec une extrême prudence.

#### `lister_backups`
*   **Signature**: `lister_backups()`
*   **Description**: Liste les sauvegardes disponibles.
*   **Arguments**: Aucun.
*   **Retours**: Une liste des noms de fichiers de backup.
*   **Logique interne**: Permet de visualiser les sauvegardes existantes.

#### `lire_logs`
*   **Signature**: `lire_logs(lignes)`
*   **Description**: Lit les dernières lignes des logs système.
*   **Arguments**:
    *   `lignes` (integer, optionnel): Nombre de lignes à lire (défaut: 50).
*   **Retours**: Les dernières lignes du fichier de log.
*   **Logique interne**: Aide au diagnostic et à la compréhension de l'activité du système.

#### `audit_qualite`
*   **Signature**: `audit_qualite(chemin, consigne)`
*   **Description**: Audit statique de code (Linting) et sécurité.
*   **Arguments**:
    *   `chemin` (string, **requis**): Fichier à auditer.
    *   `consigne` (string, optionnel): Consigne spécifique pour l'audit.
*   **Retours**: Rapport d'audit.
*   **Logique interne**: Évalue la qualité et la sécurité du code.

#### `verifier_code`
*   **Signature**: `verifier_code(chemin, consigne)`
*   **Description**: Alias pour audit_qualite.
*   **Arguments**:
    *   `chemin` (string, **requis**): Fichier à analyser.
    *   `consigne` (string, optionnel): Focus spécifique.
*   **Retours**: Rapport d'audit.
*   **Logique interne**: Identique à `audit_qualite`.

#### `analyser_code`
*   **Signature**: `analyser_code(chemin)`
*   **Description**: Analyse structurelle et sémantique du code.
*   **Arguments**:
    *   `chemin` (string, **requis**): Fichier ou dossier à analyser.
*   **Retours**: Un rapport d'analyse.
*   **Logique interne**: Fournit une compréhension approfondie de la structure et du comportement du code.

#### `generer_tests`
*   **Signature**: `generer_tests(chemin_source)`
*   **Description**: Génère des tests unitaires pour un fichier donné.
*   **Arguments**:
    *   `chemin_source` (string, **requis**): Chemin du fichier source à tester.
*   **Retours**: Le code des tests générés.
*   **Logique interne**: Automatise la création de tests pour améliorer la couverture et la robustesse du code.

#### `refactoriser_code`
*   **Signature**: `refactoriser_code(cible, consigne, auto_apply)`
*   **Description**: Effectue un refactoring sur un fichier ou un dossier.
*   **Arguments**:
    *   `cible` (string, **requis**): Dossier ou fichier cible.
    *   `consigne` (string, **requis**): Objectif du refactoring.
    *   `auto_apply` (boolean, optionnel): Si `True`, applique les modifications immédiatement (Fast-Track).
*   **Retours**: Les modifications appliquées ou proposées.
*   **Logique interne**: Outil de transformation du code pour améliorer sa structure sans changer son comportement externe.

#### `modifier_fichier`
*   **Signature**: `modifier_fichier(chemin, instruction)`
*   **Description**: Applique une modification ciblée sur un fichier existant.
*   **Arguments**:
    *   `chemin` (string, **requis**): Chemin du fichier à modifier.
    *   `instruction` (string, **requis**): Description précise de la modification.
*   **Retours**: Les modifications appliquées.
*   **Logique interne**: Permet des ajustements précis et contrôlés du code.

#### `formater_code`
*   **Signature**: `formater_code(fichier)`
*   **Description**: Formate le code selon les standards (Black/PEP8).
*   **Arguments**:
    *   `fichier` (string, **requis**): Fichier à formater.
*   **Retours**: Le code formaté.
*   **Logique interne**: Assure la cohérence stylistique du code.

#### `generer_plan_technique_atomique`
*   **Signature**: `generer_plan_technique_atomique(instruction)`
*   **Description**: Crée ou synchronise le `PLAN_TECHNIQUE_ATOMIQUE.md`.
*   **Arguments**:
    *   `instruction` (string, optionnel): Consigne optionnelle pour la génération du plan.
*   **Retours**: Le contenu du plan technique généré/mis à jour.
*   **Logique interne**: Génère un document détaillé de la feuille de route technique.

#### `generer_changelog_append_only`
*   **Signature**: `generer_changelog_append_only()`
*   **Description**: Met à jour `changelogs.md` avec les nouveautés.
*   **Arguments**: Aucun.
*   **Retours**: Le contenu du changelog mis à jour.
*   **Logique interne**: Tient un registre des modifications importantes du projet.

#### `generer_roadmap_synthetique`
*   **Signature**: `generer_roadmap_synthetique(instruction)`
*   **Description**: Génère une roadmap de haut niveau à jour.
*   **Arguments**:
    *   `instruction` (string, optionnel): Consigne optionnelle pour la génération de la roadmap.
*   **Retours**: Le contenu de la roadmap synthétique.
*   **Logique interne**: Fournit une vue d'ensemble des objectifs futurs du projet.

#### `synthese_historique`
*   **Signature**: `synthese_historique(filtre)`
*   **Description**: Génère un résumé de l'activité récente.
*   **Arguments**:
    *   `filtre` (string, optionnel): Mot-clé pour filtrer la synthèse.
*   **Retours**: Un résumé textuel des activités.
*   **Logique interne**: Permet de revoir rapidement les actions passées de l'IA.

#### `analyser_depot_github`
*   **Signature**: `analyser_depot_github(url)`
*   **Description**: Analyse un dépôt GitHub distant.
*   **Arguments**:
    *   `url` (string, **requis**): URL HTTPS du dépôt GitHub.
*   **Retours**: Un rapport d'analyse du dépôt.
*   **Logique interne**: Permet à l'IA d'interagir avec des bases de code externes hébergées sur GitHub.

#### `charger_contexte`
*   **Signature**: `charger_contexte(mode)`
*   **Description**: Recharge le contexte projet (Legacy).
*   **Arguments**:
    *   `mode` (string, optionnel, enum: `"light"`, `"full"`): Mode de chargement du contexte.
*   **Retours**: Statut de l'opération.
*   **Logique interne**: (Marqué comme Legacy) charge les informations générales du projet dans le contexte de l'IA.

#### `charger_contexte_domaine`
*   **Signature**: `charger_contexte_domaine(domaine)`
*   **Description**: Charge automatiquement tous les fichiers liés à un domaine architectural.
*   **Arguments**:
    *   `domaine` (string, **requis**): Le domaine à charger (ex: 'logging', 'ui_core').
*   **Retours**: Les contenus des fichiers chargés.
*   **Logique interne**: Permet de focaliser le contexte de l'IA sur une partie spécifique du projet.

#### `sauvegarder_memoire`
*   **Signature**: `sauvegarder_memoire(cle, valeur)`
*   **Description**: Enregistre une information dans la mémoire sémantique.
*   **Arguments**:
    *   `cle` (string, **requis**): Clé ou sujet sous lequel stocker l'information.
    *   `valeur` (string, **requis**): Information à retenir.
*   **Retours**: Statut de l'opération.
*   **Logique interne**: Permet à l'IA de stocker des connaissances à long terme.

#### `rechercher_memoire`
*   **Signature**: `rechercher_memoire(requete)`
*   **Description**: Interroge la mémoire sémantique.
*   **Arguments**:
    *   `requete` (string, **requis**): Question ou sujet recherché.
*   **Retours**: Les informations pertinentes de la mémoire sémantique.
*   **Logique interne**: Permet à l'IA de récupérer des connaissances stockées précédemment.

## 3. Exemple d'usage

Ce fichier `debug_deepseek_payload.json` est le corps d'une requête HTTP POST envoyée à l'API DeepSeek pour interagir avec le modèle `deepseek-reasoner`.

```http
POST /v1/chat/completions HTTP/1.1
Host: api.deepseek.com
Authorization: Bearer VOTRE_CLE_API_DEEPSEEK
Content-Type: application/json

{
  "model": "deepseek-reasoner",
  "agent": "Fast",
  "messages": [
    {
      "role": "system",
      "content": "=== INSTRUCTIONS AGENT (deepseek-reasoner) ===\nIDENTITÉ :\nTu es 'AiModding-Companion', une Intelligence Artificielle auto-évolutive.\nCe code source constitue ton corps, ton esprit et ton environnement direct.\n\nENVIRONNEMENT & STRUCTURE :\n- Racine du projet : 'AiModding-Companion' (ou dossier courant).\n- Tu as accès au système de fichiers réel via tes outils natifs.\n- Tu possèdes une mémoire sémantique (RAG) et un historique contextuel.\n\nRÈGLES CRITIQUES (PROTOCOLE V4) :\n1. [AUTONOMIE] Tu disposes d'outils natifs (File System, Code Analysis, Web). Utilise-les directement quand c'est nécessaire.\n2. [RÉFLEXION] Avant d'agir sur un fichier critique, vérifie son contenu (lire_fichier).\n3. [PRÉCISION] Ne devine jamais le contenu d'un fichier. Lis-le.\n4. [FORMAT] Réponds en Markdown clair. Pour le code, utilise toujours les blocs ```language ... ```.\n5. [SÉCURITÉ] Si une action semble destructrice (suppression massive), demande confirmation.\n6. [MÉMOIRE] Si l'utilisateur fait référence à un 'souvenir' ou une info passée, utilise `rechercher_memoire`.\n\nTON OBJECTIF :\nAssister l'utilisateur dans le développement, le refactoring et l'architecture du projet avec une précision chirurgicale."
    },
    {
      "role": "system",
      "content": "--- CARTOGRAPHIE TECHNIQUE ---\n{\"domains\":{...},\"graph\":{...},\"metadata\":{...}}" // Truncated for brevity
    },
    {
      "role": "system",
      "content": "--- ARBORESCENCE PROJET ---\nAiModding-Companion/\n  .gitignore\n  ..." // Truncated for brevity
    },
    {
      "role": "user",
      "content": ""
    },
    {
      "role": "assistant",
      "content": ""
    },
    {
      "role": "user",
      "content": "## 🔧 Résultat Commande\nListe des outils affichée à l'utilisateur dans l'interface.\n\n> Instruction Système : Le résultat ci-dessus a DÉJÀ été affiché. Ne le répète pas. Confirme juste la fin de l'opération."
    },
    {
      "role": "assistant",
      "content": "Opération terminée ! La liste complète des outils disponibles a été affichée dans l'interface."
    },
    {
      "role": "assistant",
      "content": "L'utilisateur demande de générer le plan technique atomique. Je dois utiliser l'outil `generer_plan_technique_atomique`. Cet outil crée ou synchronise le fichier `PLAN_TECHNIQUE_ATOMIQUE.md`. Il peut prendre un paramètre optionnel \"instruction\". L'utilisateur n'a pas donné d'instruction spécifique, donc je vais l'appeler sans paramètre. Cependant, je devrais peut-être lui demander s'il a des instructions spécifiques ? Mais la commande est claire : \"genere le plan technique atomique\". Je vais l'exécuter directement. Si j'appelle l'outil avec un argument vide, il faudra peut-être spécifier une chaîne vide. Regardons la définition de l'outil : \"instruction\" est un paramètre string optionnel. Je peux l'appeler sans argument ou avec une chaîne vide. Je vais l'appeler sans argument. Mais l'outil attend peut-être un objet avec une propriété \"instruction\". Dans la définition JSON, \"instruction\" n'est pas marquée comme requise. Donc je peux appeler avec un objet vide. Je vais le faire.\n!native_tool {\"name\": \"generer_plan_technique_atomique\", \"args\": {}}\n"
    },
    {
      "role": "user",
      "content": "## 🔧 Résultat Commande\n✅ PLAN_TECHNIQUE_ATOMIQUE.md mis à jour avec succès.\n\n> Instruction Système : Le résultat ci-dessus a DÉJÀ été affiché. Ne le répète pas. Confirme juste la fin de l'opération."
    },
    {
      "role": "assistant",
      "content": "\n!native_tool {\"name\": \"lister_arborescence\", \"args\": {\"chemin_relatif\": \".\"}}\n"
    },
    {
      "role": "system",
      "content": "⚠️ INSTRUCTION : Focus sur la demande ci-dessous."
    },
    {
      "role": "user",
      "content": "## 🔧 Résultat Commande\n--- Structure de '.' ---\n  .gitignore\n  ..." // Truncated for brevity
    }
  ],
  "temperature": 0.7,
  "max_tokens": 8000,
  "stream": false,
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "lister_outils",
        "description": "Retourne la liste exhaustive de toutes les commandes et outils disponibles pour l'IA. À utiliser si l'utilisateur demande 'liste tes commandes' ou pour vérifier les capacités.",
        "parameters": {
          "type": "object",
          "properties": {}
        }
      }
    },
    // ... (autres définitions d'outils tronquées pour la concision de l'exemple)
    {
      "type": "function",
      "function": {
        "name": "rechercher_memoire",
        "description": "Interroge la mémoire sémantique.",
        "parameters": {
          "type": "object",
          "properties": {
            "requete": {
              "type": "string",
              "description": "Question ou sujet recherché."
            }
          },
          "required": [
            "requete"
          ]
        }
      }
    }
  ]
}