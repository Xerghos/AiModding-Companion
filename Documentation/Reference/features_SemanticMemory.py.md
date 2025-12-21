# Documentation Technique : `features\SemanticMemory.py`

## En-tête

### Titre
`features\SemanticMemory.py` - Gestionnaire de Mémoire Sémantique Hybride (HMA)

### Description concise
Ce module implémente le `SemanticMemoryManager`, un système avancé de gestion de mémoire pour l'IA, également appelé "Hybrid Memory Agent" (HMA) version 4.0. Il est conçu pour optimiser l'historique de conversation en le transformant en une structure plus compacte et pertinente : un "socle" initial, un "Résumé Consolidé" des interactions passées, et une "Mémoire à Court Terme" (STM) conservant les messages les plus récents. Le module gère le chargement, la sauvegarde et l'optimisation de l'historique de chat, intégrant un mécanisme de "Rolling Summary" basé sur l'IA pour la compression des discussions. Il fournit également des fonctionnalités pour la recherche de contexte dans une Mémoire à Long Terme (LTM) optionnelle via RAG (Retrieval Augmented Generation).

### Dépendances

*   **Bibliothèques Standard Python:**
    *   `os`: Opérations sur le système de fichiers.
    *   `json`: Gestion des données JSON.
    *   `time`: Fonctions liées au temps.
    *   `traceback`: Récupération et formatage des traces d'erreurs.
    *   `logging`: Système de journalisation.
    *   `re`: Expressions régulières.
*   **Modules Internes:**
    *   `config.settings`: Pour `APP_SETTINGS` (paramètres de l'application).
    *   `config.paths`: Pour `get_path` (gestion des chemins de fichiers).
    *   `features.UnifiedLogger`: Pour `UnifiedLogger` (journalisation unifiée).
    *   `ai_core.factory`: Pour `SessionFactory` (création de sessions AI).
    *   `ai_core.sessions`: Pour `call_ai_robust` (appels robustes à l'IA) et `_save_payload_log` (enregistrement des payloads AI).
    *   `features.Decorators`: Pour `trace_action` (décorateur de traçage des actions).
    *   `features.context.database` (import conditionnel): Pour l'intégration à la base de données de mémoire à long terme (LTM).
    *   `features.Shared`: Pour `log_action` (journalisation partagée des actions).

## Classes & Fonctions

### `class SemanticMemoryManager`

**Description:**
Gestionnaire de Mémoire Hybride (HMA) - V4.0 (Rolling Summary). Cette classe est responsable de la gestion de la mémoire du système, transformant un historique de conversation linéaire en une structure optimisée pour les modèles d'IA. Elle implémente une fenêtre de mémoire à court terme (STM), un mécanisme de consolidation (Rolling Summary) via un modèle d'IA, et l'intégration à une mémoire à long terme (LTM) pour la recherche de contexte.

#### `__init__(self)`

*   **Signature:** `__init__(self)`
*   **Arguments:**
    *   `self`: Instance de la classe.
*   **Logique interne:**
    *   Initialise les paramètres internes de la mémoire avec des valeurs par défaut :
        *   `self.stm_window`: Nombre de messages récents à conserver intacts (par défaut 4, soit 2 tours de conversation).
        *   `self.compression_threshold`: Seuil en caractères pour déclencher la consolidation de l'historique par l'IA (par défaut 2000).
        *   `self.max_active_tokens`: (Legacy) Gardé pour compatibilité de configuration, mais moins central dans la V4.0.
        *   `self.ltm_enabled`: Indique si la mémoire à long terme est activée (dépend de la disponibilité de la base de données).
        *   `self.enabled`: Active/désactive l'optimisation de la mémoire.
    *   Appelle `self._reload_config()` pour charger la configuration dynamique de l'application.

#### `_reload_config(self)`

*   **Signature:** `@trace_action(source="SemanticMemory") def _reload_config(self)`
*   **Arguments:**
    *   `self`: Instance de la classe.
*   **Logique interne:**
    *   Charge les paramètres de configuration liés à l'optimisation de la mémoire (`memory_optimization`) depuis `APP_SETTINGS`.
    *   Met à jour `self.enabled`, `self.stm_window`, `self.compression_threshold`, et `self.max_active_tokens` avec les valeurs configurées.
    *   Met à jour `self.ltm_enabled` en vérifiant si l'objet `database` a été importé et est disponible.

#### `load_history_into_session(self, session)`

*   **Signature:** `@trace_action(source="SemanticMemory") def load_history_into_session(self, session)`
*   **Arguments:**
    *   `self`: Instance de la classe.
    *   `session`: L'objet de session de l'IA (ex: `GeminiSession`) contenant l'attribut `chat` avec un historique.
*   **Retours:** Aucun.
*   **Logique interne:**
    *   Charge l'historique complet de la conversation depuis le fichier `full_chat_history.json` situé sur le disque.
    *   Si le fichier n'existe pas, un message est logué et la fonction se termine.
    *   Applique une rétention maximale (`max_history_retention`) pour limiter la taille de l'historique chargé.
    *   Convertit l'historique stocké en un format compatible avec la session Gemini (rôles `model`/`user` et `parts`).
    *   Met à jour `session.chat.history` avec l'historique restauré.
    *   Journalise l'action de chargement avec `UnifiedLogger`.

#### `save_session_history(self, session)`

*   **Signature:** `@trace_action(source="SemanticMemory") def save_session_history(self, session)`
*   **Arguments:**
    *   `self`: Instance de la classe.
    *   `session`: L'objet de session de l'IA.
*   **Retours:** Aucun.
*   **Logique interne:**
    *   Sauvegarde l'historique actuel de `session.chat.history` sur le disque dans le fichier `full_chat_history.json`.
    *   Transforme les messages de l'historique en un format sérialisable (dictionnaires avec `role` et `content`).
    *   Utilise `_extract_text` pour obtenir le contenu textuel de manière robuste, gérant les différents formats de messages (objets Gemini ou dictionnaires).
    *   Écrit l'historique sérialisé en JSON, avec une indentation pour la lisibilité.

#### `optimize_history(self, session)`

*   **Signature:** `@trace_action(source="SemanticMemory") def optimize_history(self, session)`
*   **Arguments:**
    *   `self`: Instance de la classe.
    *   `session`: L'objet de session de l'IA.
*   **Retours:** Aucun.
*   **Logique interne:**
    *   C'est la méthode principale pour la consolidation de la mémoire (Rolling Summary V4).
    *   Vérifie si l'optimisation est activée et si la session a un historique. Si non, sauvegarde l'historique et sort.
    *   Sépare l'historique en deux parties : `active_slice` (les `stm_window` derniers messages) et `archive_slice` (les messages plus anciens).
    *   Calcule la taille en caractères de `archive_slice`. Si elle est inférieure à `compression_threshold`, aucune compression n'est nécessaire ; l'historique est sauvegardé et la fonction se termine.
    *   Appelle `_generate_rolling_summary` pour générer un résumé du `archive_slice`.
    *   Si un résumé est généré avec succès :
        *   Crée un nouveau message unique pour le résumé (`summary_msg`), marqué comme "MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ)".
        *   Ajoute un message d'acquittement (`ack_msg`) de l'IA pour stabiliser le modèle.
        *   Reconstruit `session.chat.history` avec la structure `[summary_msg, ack_msg] + active_slice`.
        *   Journalise l'opération de consolidation avec `UnifiedLogger`.
        *   Sauvegarde immédiatement le nouvel historique optimisé.

#### `_generate_rolling_summary(self, text_block)`

*   **Signature:** `_generate_rolling_summary(self, text_block)`
*   **Arguments:**
    *   `self`: Instance de la classe.
    *   `text_block` (str): Le bloc de texte à compresser (l'historique archivé).
*   **Retours:** `str` ou `None`. Le résumé structuré généré par l'IA, ou `None` si la génération échoue ou est vide.
*   **Logique interne:**
    *   Crée une session IA spécifique avec le modèle `compressor` (souvent un modèle rapide comme Flash), sans outils.
    *   Construit un prompt détaillé pour l'IA, lui demandant de consolider l'historique en un résumé technique structuré, organisé par périodes et thèmes, avec un format Markdown spécifique.
    *   Inclut des règles de compression (conserver les faits techniques, ignorer les politesses, intégrer les résumés précédents, concision).
    *   Enregistre un payload spécifique pour le modèle `compressor`.
    *   Appelle l'IA via `call_ai_robust` en forçant la sortie texte pour éviter le JSON.
    *   Désactive temporairement le logging de session standard pour éviter les doublons.
    *   Valide le résumé obtenu (non vide, pas d'erreurs internes).

#### `get_compressed_history_block(self)`

*   **Signature:** `get_compressed_history_block(self)`
*   **Arguments:**
    *   `self`: Instance de la classe.
*   **Retours:** `str`. Le contenu du résumé consolidé formaté pour être injecté dans le contexte du modèle, ou une chaîne vide si aucun résumé n'est trouvé.
*   **Logique interne:**
    *   Lit le fichier `full_chat_history.json` depuis le disque.
    *   Parcourt l'historique à l'envers pour trouver le message le plus récent contenant la balise "📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ)".
    *   Extrait le contenu du résumé, en supprimant les en-têtes et pieds de page spécifiques.
    *   Tronque le résumé à 5000 caractères si nécessaire pour éviter de saturer le contexte.
    *   Retourne le résumé formaté avec un en-tête "MÉMOIRE LONG TERME (Résumé Consolidé)".

#### `retrieve_relevant_context(self, user_query)`

*   **Signature:** `@trace_action(source="SemanticMemory") def retrieve_relevant_context(self, user_query)`
*   **Arguments:**
    *   `self`: Instance de la classe.
    *   `user_query` (str): La requête de l'utilisateur pour rechercher des informations pertinentes.
*   **Retours:** `str`. Un bloc de texte formaté contenant les "souvenirs" pertinents de la LTM, ou une chaîne vide si la LTM est désactivée ou si aucun résultat n'est trouvé.
*   **Logique interne:**
    *   Vérifie si la LTM est activée et si l'objet `database` est disponible.
    *   Appelle la méthode `search_memories` ou `search_vector_db` de l'objet `database` pour effectuer une recherche vectorielle (RAG) avec `user_query`.
    *   Limite les résultats à 3.
    *   Formate les résultats trouvés dans un bloc de texte avec un en-tête "🕰️ SOUVENIRS PERTINENTS (LTM)".
    *   Implémente une logique de dédoublonnage simple basée sur le début du contenu.

#### `_clean_json_string(self, text)`

*   **Signature:** `_clean_json_string(self, text)`
*   **Arguments:**
    *   `self`: Instance de la classe.
    *   `text` (str): La chaîne à nettoyer, potentiellement au format JSON.
*   **Retours:** `str`. La chaîne nettoyée ou le JSON reformatté.
*   **Logique interne:**
    *   Si la chaîne ressemble à du JSON, elle tente de la parser.
    *   Recherche des clés spécifiques comme "tool_output" ou "result" pour extraire la valeur la plus pertinente de l'objet JSON imbriqué.
    *   Si elle ne peut pas extraire une valeur spécifique mais que c'est un JSON valide, elle le reformate pour la lisibilité.
    *   Sinon, retourne la chaîne telle quelle.

#### `_extract_text(self, message)`

*   **Signature:** `@trace_action(source="SemanticMemory") def _extract_text(self, message)`
*   **Arguments:**
    *   `self`: Instance de la classe.
    *   `message`: Un objet message de l'IA (peut être un objet natif du modèle ou un dictionnaire sérialisé).
*   **Retours:** `str`. Le contenu textuel consolidé et nettoyé du message.
*   **Logique interne:**
    *   Extrait le contenu textuel de manière robuste, gérant différents formats de messages.
    *   **Pour les objets Gemini natifs:** Itère sur `message.parts` et extrait `part.text`, `function_call` (avec arguments), et `function_response` (avec `_clean_json_string` pour les payloads).
    *   **Pour les dictionnaires (legacy/sérialisés):** Recherche `content` ou `parts` pour extraire le texte.
    *   Joint toutes les parties textuelles extraites en une seule chaîne.

#### `_update_message_text(self, message, new_text)`

*   **Signature:** `@trace_action(source="SemanticMemory") def _update_message_text(self, message, new_text)`
*   **Arguments:**
    *   `self`: Instance de la classe.
    *   `message`: L'objet message à modifier (peut être un objet natif du modèle ou un dictionnaire).
    *   `new_text` (str): Le nouveau contenu textuel à attribuer au message.
*   **Retours:** Aucun.
*   **Logique interne:**
    *   Met à jour le contenu textuel d'un message en essayant de préserver sa structure.
    *   **Pour les objets Gemini natifs:** Cherche la première partie (`part`) avec un attribut `text` et met à jour sa valeur.
    *   **Pour les dictionnaires:** Met à jour le `text` de la première partie dans `parts`, ou le `content` si `parts` n'est pas présent ou n'a pas de texte.

### `GlobalMemoryManager`

**Description:**
Instance singleton de la classe `SemanticMemoryManager`. C'est le point d'accès central pour toutes les opérations de gestion de mémoire dans l'application.

### `execute_sauvegarder_memoire(cle, valeur, session, action_log_path, result_queue, **kwargs)`

**Description:**
Fonction wrapper utilisée par le dispatcher (ex: `ai_helper`) pour permettre à l'IA de sauvegarder explicitement une information dans la mémoire à long terme (LTM).

*   **Signature:** `execute_sauvegarder_memoire(cle, valeur, session, action_log_path, result_queue, **kwargs)`
*   **Arguments:**
    *   `cle` (str): La clé ou le sujet de l'information à sauvegarder.
    *   `valeur` (str): Le contenu de l'information à sauvegarder.
    *   `session` (object): L'objet de session actuel (peut être utilisé pour le contexte, bien que non directement dans cette fonction).
    *   `action_log_path` (str): Chemin vers le fichier de log des actions.
    *   `result_queue` (queue.Queue): File d'attente pour communiquer les résultats.
    *   `**kwargs`: Arguments supplémentaires.
*   **Retours:** `str`. Un message indiquant le succès ou l'échec de l'opération de sauvegarde.
*   **Logique interne:**
    *   Vérifie si la LTM est activée.
    *   Utilise `database.store_memory` (méthode préférée) ou `database.add_memory_fragment` (fallback) pour stocker la valeur avec des métadonnées.
    *   Journalise l'action via `features.Shared.log_action`.

### `execute_rechercher_memoire(requete, session, action_log_path, result_queue, **kwargs)`

**Description:**
Fonction wrapper utilisée par le dispatcher pour permettre à l'IA de rechercher activement des informations dans la mémoire sémantique (LTM).

*   **Signature:** `execute_rechercher_memoire(requete, session, action_log_path, result_queue, **kwargs)`
*   **Arguments:**
    *   `requete` (str): La requête de recherche soumise par l'IA.
    *   `session` (object): L'objet de session actuel.
    *   `action_log_path` (str): Chemin vers le fichier de log des actions.
    *   `result_queue` (queue.Queue): File d'attente pour communiquer les résultats.
    *   `**kwargs`: Arguments supplémentaires.
*   **Retours:** `str`. Les résultats formatés de la recherche ou un message indiquant qu'aucun souvenir n'a été trouvé ou une erreur.
*   **Logique interne:**
    *   Vérifie si la LTM est activée.
    *   Appelle `GlobalMemoryManager.retrieve_relevant_context` pour effectuer la recherche RAG.
    *   Journalise l'action via `features.Shared.log_action`.
    *   Formate les résultats pour les retourner à l'IA.

## Exemple d'usage

Voici comment interagir avec le `SemanticMemoryManager` dans un contexte typique d'application AI :

```python
import os
import json
from unittest.mock import MagicMock
from features.SemanticMemory import GlobalMemoryManager
from config.paths import get_path

# Assurez-vous que le chemin du fichier d'historique est défini pour l'exemple
# Pour cet exemple, nous allons simuler un chemin temporaire.
# Dans une vraie application, get_path serait configuré pour pointer vers le bon dossier.
def mock_get_path(filename):
    return os.path.join("temp_memory_data", filename)

# Patch de get_path pour l'exemple (normalement géré par la config)
from features import SemanticMemory
SemanticMemory.get_path = mock_get_path

# Créez un dossier temporaire pour l'historique si nécessaire
os.makedirs("temp_memory_data", exist_ok=True)
history_file = mock_get_path("full_chat_history.json")

# 1. Initialisation (automatique via GlobalMemoryManager)
memory_manager = GlobalMemoryManager
print(f"Mémoire manager initialisé. LTM activée: {memory_manager.ltm_enabled}")

# 2. Simulation d'une session IA
mock_session = MagicMock()
mock_session.chat.history = []

# Créer un historique de base
initial_history = [
    {"role": "user", "parts": [{"text": "Bonjour, nous allons travailler sur la refactorisation du module 'utils.py'."}]},
    {"role": "model", "parts": [{"text": "D'accord, je suis prêt. Quels sont les premiers changements ?"}]},
    {"role": "user", "parts": [{"text": "Le fichier [utils.py] doit être divisé en [file_io.py] et [string_helpers.py]."}]},
    {"role": "model", "parts": [{"text": "Compris. Je vais préparer les modifications."}]},
    {"role": "user", "parts": [{"text": "Assurez-vous que les fonctions d'E/S soient dans [file_io.py] et le reste dans [string_helpers.py]."}]},
    {"role": "model", "parts": [{"text": "C'est noté. Je commence le refactoring."}]},
    {"role": "user", "parts": [{"text": "J'ai aussi remarqué un bug dans la fonction `parse_config` dans [config_parser.py]. Elle ne gère pas les commentaires inline."}]},
    {"role": "model", "parts": [{"text": "Merci de l'information. Je l'ajouterai à ma liste de tâches."}]}
]
mock_session.chat.history.extend(initial_history)

print("\n--- Étape 1: Sauvegarde de l'historique initial ---")
memory_manager.save_session_history(mock_session)
print(f"Historique sauvegardé sur disque: {history_file}")

# Afficher le contenu du fichier (pour vérification)
if os.path.exists(history_file):
    with open(history_file, 'r', encoding='utf-8') as f:
        print("Contenu du fichier d'historique après sauvegarde:")
        print(json.dumps(json.load(f), indent=2, ensure_ascii=False))

# Simuler une nouvelle session pour charger l'historique
new_mock_session = MagicMock()
new_mock_session.chat.history = []

print("\n--- Étape 2: Chargement de l'historique dans une nouvelle session ---")
memory_manager.load_history_into_session(new_mock_session)
print(f"Historique chargé. Nombre de messages: {len(new_mock_session.chat.history)}")


# 3. Optimisation de l'historique (compression)
# Pour déclencher la compression, il faut simuler plus de messages que la STM_WINDOW
# et que le seuil de compression soit atteint.
print(f"\n--- Étape 3: Optimisation de l'historique ---")
print(f"Paramètres: STM Window={memory_manager.stm_window}, Compression Threshold={memory_manager.compression_threshold}")

# Ajout de messages pour dépasser le seuil et déclencher la compression
for i in range(10): # Ajoutons 10 messages supplémentaires
    new_mock_session.chat.history.append({"role": "user", "parts": [{"text": f"Message de test {i} pour allonger l'historique."}]})
    new_mock_session.chat.history.append({"role": "model", "parts": [{"text": f"Réponse au test {i}."}]})

# Le simulateur pour _generate_rolling_summary est nécessaire car il appelle un modèle AI
# Dans un environnement réel, cela ferait un appel API.
class MockSessionFactory:
    @staticmethod
    def create_session(model_type, enable_tools):
        mock_ai_session = MagicMock()
        mock_ai_session.model_name = "mock_compressor_model"
        return mock_ai_session

SemanticMemory.SessionFactory = MockSessionFactory
SemanticMemory.call_ai_robust = lambda session, prompt, force_text: (
    "## Période Récente (2023-10-27)\n"
    "### Refactorisation\n"
    "- [utils.py] Divisé en [file_io.py] et [string_helpers.py] (2023-10-27)\n"
    "### Bugs\n"
    "- [config_parser.py] Bug `parse_config` avec commentaires inline identifié (2023-10-27)"
    "### Discussions Diverses\n"
    "- 10 messages de test ont été ajoutés."
)
SemanticMemory._save_payload_log = lambda *args, **kwargs: None


original_history_len = len(new_mock_session.chat.history)
memory_manager.optimize_history(new_mock_session)
print(f"Historique optimisé. Longueur avant: {original_history_len}, après: {len(new_mock_session.chat.history)}")

# Afficher l'historique optimisé
print("\n--- Historique après optimisation ---")
for msg in new_mock_session.chat.history:
    role = msg.get('role', 'unknown') if isinstance(msg, dict) else msg.role
    content = memory_manager._extract_text(msg)
    print(f"[{role.upper()}]: {content[:100]}...") # Tronque pour la lisibilité

# 4. Récupération du bloc de mémoire compressée (pour l'injection de contexte)
print("\n--- Étape 4: Récupération du bloc de mémoire compressée ---")
compressed_block = memory_manager.get_compressed_history_block()
print(compressed_block)


# 5. Recherche de contexte LTM (si activée)
print("\n--- Étape 5: Recherche de contexte LTM (si la base de données est connectée) ---")
if memory_manager.ltm_enabled:
    # Simuler une base de données avec une méthode search_memories
    mock_db = MagicMock()
    mock_db.search_memories.return_value = [
        "Le projet a pour objectif de créer un assistant de modding IA.",
        "Le framework principal est basé sur Gemini/LangChain."
    ]
    SemanticMemory.database = mock_db # Patch la variable globale 'database'

    query = "quel est l'objectif du projet?"
    relevant_context = memory_manager.retrieve_relevant_context(query)
    print(relevant_context)
else:
    print("La mémoire à long terme (LTM) n'est pas activée ou la base de données n'est pas connectée.")

# Nettoyage des fichiers temporaires
# os.remove(history_file)
# os.rmdir("temp_memory_data")
print("\nExemple terminé.")