# Documentation Technique : features/FileSystem.py

## Description

Ce module gère les opérations de base sur le système de fichiers, notamment la lecture, l'écriture, la création, la suppression, le déplacement et la copie de fichiers et de dossiers. Il intègre des fonctionnalités de sécurité comme la validation de la syntaxe Python avant écriture, la gestion des erreurs d'encodage, et utilise un système de résolution de chemins intelligent. Il propose également une fonction de comparaison de fichiers avec affichage des différences et une fonction pour lister l'arborescence du projet en filtrant le bruit. Des hooks vers des systèmes externes (RAG, Backup) sont présents pour une intégration plus poussée.

## Dépendances

*   **os**: Pour les interactions système de base (chemins, création/suppression de fichiers/dossiers).
*   **fnmatch**: Pour la correspondance de motifs de noms de fichiers (filtrage).
*   **shutil**: Pour les opérations de haut niveau sur les fichiers (copie, déplacement).
*   **difflib**: Pour la comparaison de fichiers et la génération de diff.
*   **time**: Pour l'accès aux horodatages des fichiers.
*   **ast**: Pour la vérification de la syntaxe Python.
*   **config**: Module personnalisé pour obtenir le chemin racine du projet et le logger.
*   **features.Decorators**: Décorateur `@trace_action` pour le suivi des actions.
*   **features.Shared**: Fonction `log_action` pour l'enregistrement des actions.
*   **features.SearchEngine**: Fonction `omniscient_resolve_path` pour la résolution intelligente des chemins de fichiers.
*   **features.context.database** (Optionnel, conditionnel): Module pour l'intégration RAG (indexation).
*   **features.core\_backup** (Optionnel, conditionnel): Module pour la gestion des sauvegardes.

---

## Classes & Fonctions

### Variables Globales

*   **IGNORED_DIRS**: Liste de chaînes de caractères représentant les noms de dossiers à ignorer systématiquement lors de parcours d'arborescence.
*   **IGNORED_FILES**: Liste de chaînes de caractères au format glob (wildcards) représentant les noms de fichiers à ignorer.

### `lister_arborescence(chemin_relatif=None, profondeur_max=5)`

Liste l'arborescence du projet en filtrant les éléments définis dans `IGNORED_DIRS` et `IGNORED_FILES`.

*   **Arguments:**
    *   `chemin_relatif` (str, optionnel): Chemin relatif à partir duquel commencer le listage. Si `None`, utilise le répertoire courant (`.`).
    *   `profondeur_max` (int, optionnel): Profondeur maximale de l'arborescence à parcourir (par défaut 5).

*   **Retourne:**
    *   (str): Une chaîne de caractères formatée représentant la structure du répertoire, ou un message d'erreur si le chemin n'existe pas.

*   **Logique interne:**
    1.  Obtient le chemin absolu du répertoire racine (`root_path`).
    2.  Vérifie si le `root_path` existe.
    3.  Parcourt l'arborescence en utilisant `os.walk`.
    4.  Pour chaque répertoire rencontré :
        *   Filtre les sous-dossiers (`dirs`) en retirant ceux présents dans `IGNORED_DIRS`. La modification est faite in-place (`dirs[:]`) pour que `os.walk` ne descende pas dans ces dossiers ignorés.
        *   Calcule la profondeur actuelle du répertoire dans l'arborescence.
        *   Si la profondeur dépasse `profondeur_max`, le parcours de ce sous-arbre est arrêté.
        *   Ajoute le nom du répertoire courant à la liste `structure` avec une indentation appropriée.
    5.  Pour chaque fichier rencontré dans le répertoire courant :
        *   Filtre le fichier s'il correspond à l'un des motifs dans `IGNORED_FILES` en utilisant `fnmatch.fnmatch`.
        *   Ajoute le nom du fichier à la liste `structure` avec une indentation appropriée.
    6.  Joint tous les éléments de la liste `structure` avec des sauts de ligne pour former la chaîne de sortie.

### `lire_fichier(chemin)`

Lit le contenu d'un fichier texte en gérant les erreurs d'encodage et en utilisant une résolution de chemin intelligente en cas d'échec.

*   **Arguments:**
    *   `chemin` (str): Le chemin vers le fichier à lire.

*   **Retourne:**
    *   (str): Le contenu du fichier s'il est lu avec succès.
    *   (str): Un message d'erreur spécifique si le fichier n'existe pas, s'il s'agit d'un fichier binaire, ou si une autre exception se produit.

*   **Logique interne:**
    1.  Obtient le chemin absolu (`abs_path`) du fichier.
    2.  Tente d'ouvrir et de lire le fichier directement.
    3.  Si `os.path.exists(abs_path)` est faux :
        *   Log une tentative de résolution.
        *   Appelle `omniscient_resolve_path(chemin)` pour trouver le fichier.
        *   Si résolu, met à jour `chemin` et `abs_path`.
        *   Si non résolu, retourne un message d'erreur indiquant que le fichier est introuvable.
    4.  Tente d'ouvrir le fichier en mode lecture (`'r'`) avec l'encodage UTF-8.
    5.  En cas de `UnicodeDecodeError`, retourne une erreur spécifique pour les fichiers binaires ou à encodage non supporté.
    6.  En cas d'autre `Exception`, retourne un message d'erreur générique incluant l'exception.

### `_verifier_syntaxe_python(contenu, nom_fichier="<string>")`

[Fonction Helper Interne] Vérifie la validité syntaxique d'un contenu Python donné.

*   **Arguments:**
    *   `contenu` (str): Le code Python à vérifier.
    *   `nom_fichier` (str, optionnel): Le nom du fichier simulé pour le rapport d'erreur (par défaut `"<string>"`).

*   **Retourne:**
    *   (tuple): `(True, None)` si la syntaxe est valide.
    *   (tuple): `(False, str)` où `str` est le message d'erreur de la syntaxe si elle est invalide.

*   **Logique interne:**
    1.  Utilise `ast.parse()` pour tenter de parser le `contenu`.
    2.  Si `ast.parse()` réussit, retourne `(True, None)`.
    3.  Si une `SyntaxError` est levée, capture l'erreur et retourne `(False, error_msg)` contenant le numéro de ligne et le message d'erreur.
    4.  Capture toute autre `Exception` et retourne `(False, str(e))`.

### `ecrire_fichier(chemin, contenu)`

Écrit le `contenu` dans le fichier spécifié par `chemin`. Inclut la validation de la syntaxe Python, un mécanisme de sauvegarde (commenté) et un hook pour l'indexation RAG.

*   **Arguments:**
    *   `chemin` (str): Le chemin du fichier à écrire.
    *   `contenu` (str): Le texte à écrire dans le fichier.

*   **Retourne:**
    *   (str): Un message de succès ou un message d'erreur détaillé.

*   **Logique interne:**
    1.  Obtient le chemin absolu (`abs_path`).
    2.  Si le fichier se termine par `.py`, appelle `_verifier_syntaxe_python`. Si invalide, log une alerte et retourne un message d'erreur spécifique.
    3.  Crée récursivement les répertoires parents nécessaires avec `os.makedirs(..., exist_ok=True)`.
    4.  **[Commenté]** Vérifie si le fichier existe et si `backup_manager` est disponible pour déclencher une sauvegarde (logique à implémenter si nécessaire).
    5.  Ouvre le fichier en mode écriture (`'w'`) avec encodage UTF-8 et écrit le `contenu`.
    6.  Si le module `database` est disponible, tente d'appeler `database.add_file_to_db(chemin)` pour ré-indexer le fichier dans le système RAG. Log un avertissement en cas d'erreur.
    7.  Retourne un message de succès.
    8.  En cas d'exception pendant la création des dossiers ou l'écriture, retourne un message d'erreur.

### `creer_dossier(chemin)`

Crée un dossier à l'emplacement spécifié, y compris les répertoires parents si nécessaire.

*   **Arguments:**
    *   `chemin` (str): Le chemin du dossier à créer.

*   **Retourne:**
    *   (str): Un message de succès ou un message d'erreur.

*   **Logique interne:**
    1.  Obtient le chemin absolu (`abs_path`).
    2.  Utilise `os.makedirs(abs_path, exist_ok=True)` pour créer le dossier.
    3.  Retourne un message de succès ou d'erreur.

### `supprimer_fichier(chemin)`

Supprime un fichier s'il existe.

*   **Arguments:**
    *   `chemin` (str): Le chemin du fichier à supprimer.

*   **Retourne:**
    *   (str): Un message indiquant le succès, l'échec ou si le fichier était introuvable.

*   **Logique interne:**
    1.  Obtient le chemin absolu (`abs_path`).
    2.  Vérifie si le fichier existe (`os.path.exists`).
    3.  Si oui, utilise `os.remove(abs_path)` pour le supprimer et retourne un message de succès.
    4.  Si non, retourne "Fichier introuvable."
    5.  Capture et retourne toute exception survenue.

### `comparer_fichiers(chemin_a, chemin_b)`

Compare le contenu de deux fichiers et retourne un diff au format unifié.

*   **Arguments:**
    *   `chemin_a` (str): Chemin du premier fichier.
    *   `chemin_b` (str): Chemin du second fichier.

*   **Retourne:**
    *   (str): Un message d'erreur si l'un des fichiers est introuvable.
    *   (str): La chaîne "✅ Les fichiers sont identiques." si les contenus sont les mêmes.
    *   (str): Un bloc de code `diff` formaté Markdown contenant les différences entre les deux fichiers.
    *   (str): Un message d'erreur en cas d'exception lors de la lecture ou de la comparaison.

*   **Logique interne:**
    1.  Obtient les chemins absolus `path_a` et `path_b`.
    2.  Vérifie l'existence des deux fichiers.
    3.  Lit les deux fichiers ligne par ligne dans `text_a` et `text_b`.
    4.  Utilise `difflib.unified_diff` pour générer le diff.
    5.  Joint les lignes du diff.
    6.  Si le diff est vide, retourne le message d'identité.
    7.  Sinon, formate le diff dans un bloc de code Markdown et le retourne.
    8.  Capture et retourne toute exception survenue.

### `deplacer_fichier(source, destination)`

Déplace ou renomme un fichier de `source` vers `destination`.

*   **Arguments:**
    *   `source` (str): Chemin source du fichier.
    *   `destination` (str): Chemin destination du fichier.

*   **Retourne:**
    *   (str): Message de succès ou d'erreur (source introuvable, destination existante, ou exception).

*   **Logique interne:**
    1.  Obtient les chemins absolus `src_path` et `dst_path`.
    2.  Vérifie l'existence de la source.
    3.  Vérifie si la destination existe déjà.
    4.  Utilise `shutil.move(src_path, dst_path)` pour effectuer le déplacement.
    5.  Retourne un message de succès ou d'erreur.

### `copier_fichier(source, destination)`

Copie un fichier de `source` vers `destination`.

*   **Arguments:**
    *   `source` (str): Chemin source du fichier.
    *   `destination` (str): Chemin destination du fichier.

*   **Retourne:**
    *   (str): Message de succès ou d'erreur (source introuvable, ou exception).

*   **Logique interne:**
    1.  Obtient les chemins absolus `src_path` et `dst_path`.
    2.  Vérifie l'existence de la source.
    3.  Utilise `shutil.copy2(src_path, dst_path)` pour effectuer la copie (en préservant les métadonnées).
    4.  Retourne un message de succès ou d'erreur.

### `obtenir_infos_fichier(chemin)`

Récupère les métadonnées d'un fichier (taille, dates de création et modification).

*   **Arguments:**
    *   `chemin` (str): Chemin du fichier.

*   **Retourne:**
    *   (str): Message d'erreur si le fichier est introuvable.
    *   (str): Une chaîne formatée contenant les informations du fichier.
    *   (str): Message d'erreur en cas d'exception.

*   **Logique interne:**
    1.  Obtient le chemin absolu (`abs_path`).
    2.  Vérifie l'existence du fichier.
    3.  Utilise `os.stat(abs_path)` pour obtenir les statistiques du fichier.
    4.  Formate et retourne les informations : taille (`st_size`), date de création (`st_ctime`), date de modification (`st_mtime`).

---

## Fonctions Wrappers pour Dispatcher

Ces fonctions sont conçues pour être appelées par un dispatcher (comme celui de `ai_helper.py`). Elles acceptent des arguments supplémentaires (`session`, `action_log_path`, `result_queue`, `**kwargs`) et appellent les fonctions principales du module, tout en assurant le logging de l'action.

*   `execute_lister_arborescence(chemin_relatif, session, action_log_path, result_queue, **kwargs)`
*   `execute_lire_fichier(chemin, session, action_log_path, result_queue, **kwargs)`
*   `execute_lire_fichiers(session, action_log_path, result_queue, **kwargs)`: Alias robuste pour `lire_fichier`, gère un chemin unique ou une liste de chemins.
*   `execute_ecrire_fichier(chemin, contenu, session, action_log_path, result_queue, **kwargs)`: Appelle `ecrire_fichier` et déclenche potentiellement une sauvegarde projet si `backup_manager` est présent et si l'écriture a réussi.
*   `execute_creer_dossier(chemin, session, action_log_path, result_queue, **kwargs)`
*   `execute_supprimer_fichier(chemin, session, action_log_path, result_queue, **kwargs)`
*   `execute_comparer_fichiers(source, destination, session, action_log_path, result_queue, **kwargs)`: Gère les arguments `source`/`destination` ou `chemin_a`/`chemin_b`.
*   `execute_deplacer_fichier(source, destination, session, action_log_path, result_queue, **kwargs)`
*   `execute_copier_fichier(source, destination, session, action_log_path, result_queue, **kwargs)`
*   `execute_obtenir_infos_fichier(chemin, session, action_log_path, result_queue, **kwargs)`

Chacune de ces fonctions wrapper :
1.  Applique le décorateur `@trace_action(source="FileSystem")`.
2.  Appelle la fonction métier correspondante du module.
3.  Utilise `log_action` pour enregistrer l'opération effectuée, ses arguments principaux et le contexte.
4.  Retourne le résultat de la fonction métier.

---

## Exemple d'usage

```python
# Assurez-vous que les imports nécessaires sont faits
# from features.FileSystem import lister_arborescence, lire_fichier, ecrire_fichier, comparer_fichiers, creer_dossier

# 1. Lister l'arborescence du projet (profondeur limitée)
structure_projet = lister_arborescence(profondeur_max=3)
print(structure_projet)

# 2. Lire le contenu d'un fichier de configuration
try:
    config_content = lire_fichier("config.py")
    print("\n--- Contenu de config.py ---")
    print(config_content[:500] + "..." if len(config_content) > 500 else config_content) # Affiche les 500 premiers caractères
except Exception as e:
    print(f"Erreur lors de la lecture : {e}")

# 3. Écrire un nouveau fichier (ou le modifier)
nouveau_code = """
def ma_nouvelle_fonction():
    print("Hello from new function!")

ma_nouvelle_fonction()
"""
resultat_ecriture = ecrire_fichier("temp_test_file.py", nouveau_code)
print(f"\n{resultat_ecriture}")

# 4. Vérifier la syntaxe avant écriture (implicite dans ecrire_fichier pour .py)
code_invalide = "def ma_fonction_cassée(\n print('erreur')"
resultat_syntaxe = ecrire_fichier("syntax_error.py", code_invalide)
print(f"\n{resultat_syntaxe}") # Devrait afficher une erreur de syntaxe

# 5. Créer un nouveau dossier
resultat_creation_dossier = creer_dossier("mes_nouveaux_fichiers")
print(f"\n{resultat_creation_dossier}")

# 6. Comparer deux fichiers
# Supposons que 'fichier_original.txt' et 'fichier_modifie.txt' existent
# diff_resultat = comparer_fichiers("fichier_original.txt", "fichier_modifie.txt")
# print(f"\n{diff_resultat}")

# 7. Obtenir des informations sur un fichier
# infos = obtenir_infos_fichier("temp_test_file.py")
# print(f"\n{infos}")

# 8. Déplacer un fichier
# deplacer_fichier("temp_test_file.py", "mes_nouveaux_fichiers/fichier_deplace.py")

# 9. Copier un fichier
# copier_fichier("config.py", "config_copie.py")

# 10. Supprimer un fichier
# supprimer_fichier("syntax_error.py")
# supprimer_fichier("mes_nouveaux_fichiers/fichier_deplace.py") # si déplacé