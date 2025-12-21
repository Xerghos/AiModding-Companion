# Documentation Technique pour `scripts/analyze_rag_quality.py`

## Description
Ce document est un *modèle* de documentation technique pour le fichier `scripts/analyze_rag_quality.py`. Le contenu détaillé et précis n'a pas pu être généré car le *code source du fichier n'a pas été fourni*. Les sections suivantes présentent la structure attendue et des exemples hypothétiques basés sur le nom du fichier.

## Dépendances
*   **Librairies externes**:
    *   `[Non spécifié - Dépend du code source]`
    *   Exemples typiques pour l'analyse de qualité RAG: `pandas` (pour la manipulation de données), `openai` ou `langchain` (pour l'interaction avec des LLMs), `json` (pour le parsing de données).
*   **Modules internes**:
    *   `[Non spécifié - Dépend du code source]`

## Classes & Fonctions

Étant donné l'absence de code source, la liste suivante est une projection des fonctions et classes qui pourraient exister dans un tel fichier, avec des signatures et logiques hypothétiques.

### Fonctions principales

*   `**analyze_rag_quality(data_path: str, evaluation_model_name: str, output_path: Optional[str] = None) -> dict**`
    *   **Description**: Fonction principale orchestrant l'analyse de la qualité d'un système RAG (Retrieval Augmented Generation). Elle charge les données, évalue chaque instance de requête/réponse RAG et agrège les résultats.
    *   **Arguments**:
        *   `data_path` (str): Chemin d'accès au fichier de données d'entrée contenant les requêtes, les contextes récupérés et les réponses générées par le système RAG.
        *   `evaluation_model_name` (str): Nom du modèle de langage (LLM) à utiliser pour l'évaluation des réponses (e.g., "gpt-4", "llama-3-70b-chat").
        *   `output_path` (Optional[str]): Chemin facultatif pour sauvegarder les résultats détaillés de l'évaluation. Si `None`, les résultats ne sont pas sauvegardés dans un fichier.
    *   **Retours**:
        *   `dict`: Un dictionnaire contenant les métriques d'évaluation agrégées (e.g., score de pertinence moyen, score de cohérence moyen, taux de non-hallucination).
    *   **Logique interne (hypothétique)**:
        1.  Charge les données depuis `data_path` (CSV, JSON, etc.).
        2.  Initialise le modèle d'évaluation spécifié par `evaluation_model_name`.
        3.  Itère sur chaque entrée dans les données (requête, contexte, réponse RAG).
        4.  Pour chaque entrée, appelle une fonction utilitaire comme `_evaluate_single_instance` pour obtenir les scores détaillés.
        5.  Agrège les scores individuels pour calculer les métriques globales (moyennes, médianes, etc.).
        6.  Optionnellement, sauvegarde les résultats détaillés dans `output_path`.
        7.  Retourne les métriques agrégées.

### Fonctions utilitaires (hypothétiques)

*   `**_evaluate_single_instance(query: str, retrieved_context: str, generated_answer: str, eval_model: Any) -> dict**`
    *   **Description**: Évalue la qualité d'une seule paire (requête, contexte, réponse RAG) en utilisant un modèle d'évaluation. Les métriques peuvent inclure la pertinence, la fidélité, la cohérence et la réduction des hallucinations.
    *   **Arguments**:
        *   `query` (str): La requête originale soumise par l'utilisateur.
        *   `retrieved_context` (str): Le texte ou le document récupéré par le composant de récupération RAG.
        *   `generated_answer` (str): La réponse finale générée par le modèle RAG.
        *   `eval_model` (Any): Une instance du modèle de langage utilisé pour l'évaluation.
    *   **Retours**:
        *   `dict`: Un dictionnaire de scores pour cette instance, par exemple : `{"pertinence": 0.9, "fidelite": 0.85, "coherence": 0.92, "hallucination": False}`.
    *   **Logique interne (hypothétique)**:
        1.  Construit un prompt détaillé pour le `eval_model`, incluant la requête, le contexte et la réponse. Le prompt guide le modèle à évaluer différentes dimensions.
        2.  Appelle le `eval_model` avec ce prompt.
        3.  Parse la sortie du `eval_model` pour extraire les scores ou jugements.
        4.  Gère les erreurs ou les formats de sortie inattendus du modèle.
        5.  Retourne les scores extraits.

*   `**_load_data(data_path: str) -> List[dict]**`
    *   **Description**: Charge les données d'évaluation RAG depuis un fichier spécifié.
    *   **Arguments**:
        *   `data_path` (str): Chemin vers le fichier de données (e.g., `.json`, `.csv`).
    *   **Retours**:
        *   `List[dict]`: Une liste de dictionnaires, chaque dictionnaire représentant une instance d'évaluation avec des clés comme "query", "context", "answer".
    *   **Logique interne (hypothétique)**:
        1.  Détermine le type de fichier basé sur l'extension (`.json`, `.csv`).
        2.  Utilise la bibliothèque appropriée (e.g., `json.load`, `pandas.read_csv`) pour charger les données.
        3.  Valide la structure des données chargées.

### Classes (hypothétiques, si une approche orientée objet est adoptée)

*   `**RagQualityEvaluator**`
    *   **Description**: Classe pour encapsuler la logique d'évaluation de la qualité RAG, permettant potentiellement de pré-charger les modèles d'évaluation et de gérer la configuration.
    *   **Méthodes principales (hypothétiques)**:
        *   `__init__(self, evaluation_model_name: str, api_key: Optional[str] = None)`: Initialise l'évaluateur avec le modèle LLM à utiliser.
        *   `evaluate_dataset(self, data_path: str) -> dict`: Prend un chemin de données et retourne les métriques agrégées.
        *   `_call_eval_model(self, prompt: str) -> str`: Méthode interne pour interagir avec le LLM d'évaluation.

## Exemple d'usage

Étant donné l'absence de code source, un exemple d'usage fonctionnel ne peut pas être fourni. Cependant, voici comment ce script pourrait être utilisé s'il est conçu pour être exécuté directement ou importé :

```python
# Exemple d'exécution directe via la ligne de commande (si le script est un exécutable)
# Supposons que le script prend des arguments --data et --model
# python scripts/analyze_rag_quality.py --data "data/my_rag_eval_data.json" --model "gpt-4-turbo" --output "results/rag_evaluation_report.json"

# Exemple d'intégration dans un autre script Python
from scripts.analyze_rag_quality import analyze_rag_quality # Ou RagQualityEvaluator si une classe est utilisée
import json

if __name__ == "__main__":
    # Définir les chemins et le modèle
    data_file = "data/sample_rag_data.json"
    eval_model = "claude-3-sonnet"
    results_output_file = "results/rag_quality_summary.json"

    print(f"Démarrage de l'analyse de qualité RAG pour {data_file} avec {eval_model}...")

    try:
        # Appel de la fonction principale d'analyse
        overall_metrics = analyze_rag_quality(
            data_path=data_file,
            evaluation_model_name=eval_model,
            output_path="results/detailed_rag_evaluations.csv" # Pour les résultats détaillés par instance
        )

        print("\n--- Résultats agrégés de l'évaluation RAG ---")
        for metric, value in overall_metrics.items():
            print(f"- {metric.replace('_', ' ').capitalize()}: {value:.2f}")

        # Sauvegarder les métriques agrégées
        with open(results_output_file, 'w', encoding='utf-8') as f:
            json.dump(overall_metrics, f, indent=4)
        print(f"\nRésultats agrégés sauvegardés dans {results_output_file}")

    except FileNotFoundError:
        print(f"Erreur: Le fichier de données '{data_file}' n'a pas été trouvé.")
    except Exception as e:
        print(f"Une erreur inattendue est survenue: {e}")