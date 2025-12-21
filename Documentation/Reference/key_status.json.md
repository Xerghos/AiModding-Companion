# Documentation Technique - `key_status.json`

## 1. En-tête

### Titre
Fichier de statut des clés API (`key_status.json`)

### Description concise
Ce fichier JSON sert de référentiel pour stocker l'état actuel et les métriques d'utilisation des différentes clés API. Il permet de gérer la disponibilité, la santé, la rotation et les restrictions d'utilisation (comme les périodes de "cooldown") des clés pour divers fournisseurs de services (par exemple, Google Gemini, OpenAI, Deepseek, Groq). Chaque clé API est identifiée par un `short_id` unique et contient des informations détaillées sur son historique d'utilisation et son statut de santé.

### Dépendances
Ce fichier est une source de données autonome. Il est typiquement lu par un gestionnaire de clés ou un orchestrateur d'API qui s'appuie sur ces informations pour prendre des décisions sur quelle clé utiliser pour une requête donnée. Il est également mis à jour par ce même système après chaque utilisation ou événement (succès/erreur) pour maintenir un état cohérent. Il ne dépend pas directement d'autres fichiers spécifiques, mais son contenu est directement lié aux API externes qu'il gère.

## 2. Structure de Données

Le fichier `key_status.json` est un objet JSON de niveau racine. Chaque clé de cet objet est un `short_id` identifiant de manière unique une clé API. La valeur associée à chaque `short_id` est un objet `KeyStatus` contenant les métadonnées et l'état de cette clé.

### `Root Object`
| Nom du Champ | Type    | Description                                                     |
| :----------- | :------ | :-------------------------------------------------------------- |
| `{short_id}` | `Object` | Un identifiant court et unique pour la clé API. Chaque `{short_id}` est une instance de l'objet `KeyStatus`. |

### Objet `KeyStatus`

Représente l'état et les métriques d'une clé API spécifique.

| Nom du Champ   | Type     | Description                                                     | Exemple                               |
| :------------- | :------- | :-------------------------------------------------------------- | :------------------------------------ |
| `alias`        | `String` | Un nom lisible et descriptif pour la clé, souvent incluant le fournisseur et un identifiant numérique. | `"Clé Google_gemini 1 (Migrated)"`      |
| `short_id`     | `String` | L'identifiant court et unique de la clé. Il est utilisé comme clé dans l'objet racine du JSON. | `"ifA_gA"`                            |
| `provider`     | `String` | Le nom du fournisseur de l'API auquel cette clé est associée.    | `"google_gemini"`, `"openai"`, `"deepseek"`, `"groq"` |
| `health`       | `Float`  | Un indicateur de santé de la clé, généralement une valeur entre 0.0 et 100.0. Une valeur plus faible peut indiquer des problèmes ou des erreurs fréquentes. | `100.0`, `99.9`, `98.40000000000009` |
| `last_used`    | `Float`  | L'horodatage Unix (en secondes, avec décimales pour les millisecondes) de la dernière fois que cette clé a été utilisée. `0` si jamais utilisée. | `1766188297.751449`, `0`              |
| `cooldown_until` | `Float`  | L'horodatage Unix (en secondes) jusqu'où la clé est en période de "cooldown" et ne doit pas être utilisée. `0` si pas en cooldown. | `1766191897.8719492`, `0`             |
| `usage_count`  | `Integer`| Le nombre total de fois que cette clé a été utilisée.           | `1`, `107`, `0`                       |
| `errors`       | `Integer`| Le nombre total d'erreurs rencontrées lors de l'utilisation de cette clé. | `2`, `12`, `0`                        |

## 3. Exemple d'usage

Ce fichier est conçu pour être géré dynamiquement par un service. Voici un scénario d'usage typique :

1.  **Chargement initial** : Au démarrage du service, `key_status.json` est lu et parsé pour initialiser l'état interne de toutes les clés API disponibles.

2.  **Sélection d'une clé** : Lorsqu'une requête API est nécessaire, le service interroge son gestionnaire de clés pour obtenir la meilleure clé disponible pour un `provider` donné. Le gestionnaire de clés pourrait implémenter une logique comme :
    *   Filtrer les clés par `provider`.
    *   Éliminer les clés dont `cooldown_until` est supérieur à l'heure actuelle.
    *   Sélectionner la clé avec le `health` le plus élevé et/ou le `last_used` le plus ancien pour la rotation.

3.  **Utilisation de la clé** : La clé sélectionnée est utilisée pour faire la requête API.

4.  **Mise à jour de l'état** : Après la requête :
    *   Si la requête réussit : `last_used` est mis à jour avec l'horodatage actuel, et `usage_count` est incrémenté.
    *   Si la requête échoue : `errors` est incrémenté. Selon la nature de l'erreur, `health` pourrait être décrémenté, et `cooldown_until` pourrait être défini pour mettre la clé en pause temporairement.

5.  **Sauvegarde périodique** : L'état interne des clés est régulièrement sauvegardé dans `key_status.json` pour persister les changements et les rendre disponibles lors du prochain démarrage du service.

### Exemple de logique de sélection (pseudo-code) :

```python
import json
import time

def get_available_key(provider_name: str, key_status_data: dict) -> str | None:
    """
    Sélectionne une clé API disponible pour un fournisseur donné.
    """
    current_time = time.time()
    available_keys = []

    for key_id, key_info in key_status_data.items():
        if key_info["provider"] == provider_name:
            if key_info["cooldown_until"] <= current_time and key_info["health"] > 0:
                available_keys.append((key_id, key_info))

    if not available_keys:
        return None  # Aucune clé disponible

    # Simple logique: choisir la clé avec le plus haut "health"
    # ou celle qui a été utilisée le plus récemment/le moins récemment
    # Ici, nous pourrions trier par health décroissant puis last_used croissant pour la rotation.
    available_keys.sort(key=lambda x: (x[1]["health"], -x[1]["last_used"]), reverse=True)

    if available_keys:
        return available_keys[0][0] # Retourne le short_id de la clé

    return None

# Chargement des données
with open("key_status.json", "r") as f:
    key_statuses = json.load(f)

# Exemple de sélection pour Google Gemini
selected_key_id = get_available_key("google_gemini", key_statuses)

if selected_key_id:
    print(f"Clé sélectionnée pour Google Gemini: {selected_key_id}")
    # Mise à jour de la clé après utilisation
    key_statuses[selected_key_id]["last_used"] = time.time()
    key_statuses[selected_key_id]["usage_count"] += 1

    # ... effectuez la requête API ...
    # Si la requête échoue:
    # key_statuses[selected_key_id]["errors"] += 1
    # key_statuses[selected_key_id]["health"] -= 1.0 # Dégradation de la santé
    # key_statuses[selected_key_id]["cooldown_until"] = time.time() + 3600 # 1 heure de cooldown

    # Sauvegarde de l'état mis à jour
    # with open("key_status.json", "w") as f:
    #     json.dump(key_statuses, f, indent=2)
else:
    print("Aucune clé Google Gemini disponible pour le moment.")