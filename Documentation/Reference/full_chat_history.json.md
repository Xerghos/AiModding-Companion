# Documentation du Fichier `full_chat_history.json`

## 1. En-tête

*   **Titre**: Documentation du Fichier `full_chat_history.json`
*   **Description concise**: Ce fichier JSON représente un journal séquentiel et structuré des interactions complètes au sein d'une session de chat. Il capture les échanges entre un utilisateur et un assistant IA, intégrant des éléments de contexte tels que la mémoire du projet, les résultats de commandes exécutées, les appels d'outils et les réponses générées par l'IA. Il sert à persister l'état conversationnel et le contexte pour une reprise de session ou une analyse ultérieure.
*   **Dépendances**: Aucune dépendance logicielle externe spécifique au format de fichier. Le fichier est un JSON standard. Son interprétation dépend de l'application cliente ou de l'agent IA qui le consomme.

## 2. Structure des Données

Le fichier `full_chat_history.json` est un tableau JSON (`Array`) où chaque élément est un objet (`Object`) représentant un message ou une étape de l'interaction.

### Structure de l'objet "Message"

Chaque objet dans le tableau respecte la structure suivante :

*   **`role`** (string)
    *   **Description**: Indique l'expéditeur du message.
    *   **Valeurs possibles**:
        *   `"user"`: Un message initié par l'utilisateur humain ou une information contextuelle (ex: résumé de mémoire, résultat de commande) présentée comme venant de l'utilisateur pour l'IA.
        *   `"model"`: Un message généré par l'assistant IA. (Peut aussi être `"assistant"` selon la version de l'API ou la configuration).
        *   `"assistant"`: (Synonyme de `"model"`) Un message généré par l'assistant IA, souvent une réponse directe ou un appel d'outil.
*   **`content`** (string)
    *   **Description**: Le contenu textuel du message. Ce champ peut contenir du texte brut, du Markdown, ou des marqueurs spécifiques pour des actions ou des contextes.

### Détails du champ `content`

Le champ `content` peut encapsuler plusieurs types d'informations, identifiables par des motifs spécifiques :

1.  **Messages conversationnels standard**: Texte libre de l'utilisateur ou de l'IA.
2.  **`--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---`**
    *   **Description**: Un bloc de texte Markdown qui fournit un résumé consolidé de l'état actuel du projet ou des activités récentes. Ce contexte est injecté dans la conversation pour informer l'IA. Il est structuré par périodes temporelles et catégories (Architecture, Configuration, Features, RAG/Context, UI/Interface, Débogage/Bugs, Organisation par Périodes Temporelles).
    *   **Exemple**: La première entrée du fichier.
3.  **`## 🔧 Résultat Commande`**
    *   **Description**: Indique que le texte suivant est le résultat d'une commande ou d'un outil exécuté. Ce bloc est généralement précédé par un message de l'IA contenant un appel d'outil (`!native_tool`).
    *   **Exemple**: `\"## 🔧 Résultat Commande\\nListe des outils affichée à l'utilisateur dans l'interface.\"`
4.  **`!native_tool {"name": "tool_name", "args": {...}}`**
    *   **Description**: Un appel explicite de l'assistant IA à un outil natif du système. Le format est un JSON intégré dans la chaîne de caractères, spécifiant le nom de l'outil (`name`) et ses arguments (`args`).
    *   **Exemple**: `\"!native_tool {\\\"name\\\": \\\"lire_fichier\\\", \\\"args\\\": {\\\"chemin\\\": \\\"features/Documentation.py\\\"}}\"`
5.  **`> Instruction Système : ...`**
    *   **Description**: Une directive interne au système d'IA ou à l'interface utilisateur, souvent utilisée pour empêcher la répétition d'informations déjà affichées ou pour guider le comportement de l'IA. Ces instructions ne sont pas destinées à être affichées à l'utilisateur final.

## 3. Exemple d'usage

Ce fichier est typiquement utilisé par un système d'agent IA pour :

1.  **Charger l'historique de chat**: Récupérer le contexte d'une conversation précédente.
2.  **Reconstruire la conversation**: Afficher l'historique dans une interface utilisateur.
3.  **Fournir du contexte à l'IA**: Injecter les messages précédents, y compris les résumés de mémoire et les résultats de commandes, comme contexte d'entrée pour les prochaines requêtes de l'IA.
4.  **Exécuter des actions**: Interpréter les appels d'outils (`!native_tool`) pour déclencher des fonctions du système.

```python
import json

def load_chat_history(file_path="full_chat_history.json"):
    """Charge l'historique de chat depuis un fichier JSON."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            history = json.load(f)
        return history
    except FileNotFoundError:
        print(f"Erreur: Le fichier '{file_path}' n'a pas été trouvé.")
        return []
    except json.JSONDecodeError:
        print(f"Erreur: Le fichier '{file_path}' n'est pas un JSON valide.")
        return []

def process_message(message):
    """Traite un message de l'historique et affiche son contenu."""
    role = message.get("role")
    content = message.get("content")

    if role == "user":
        if content.startswith("--- 📜 MÉMOIRE DU PROJET"):
            print(f"--- [RÔLE: SYSTÈME/CONTEXTE - MÉMOIRE] ---")
        elif content.startswith("## 🔧 Résultat Commande"):
            print(f"--- [RÔLE: SYSTÈME/CONTEXTE - RÉSULTAT COMMANDE] ---")
        elif content.startswith("> Instruction Système :"):
            print(f"--- [RÔLE: SYSTÈME/CONTEXTE - INSTRUCTION INTERNE] ---")
        else:
            print(f"--- [RÔLE: UTILISATEUR] ---")
        print(content)
    elif role in ["model", "assistant"]:
        if content.startswith("!native_tool"):
            print(f"--- [RÔLE: ASSISTANT - APPEL D'OUTIL] ---")
            try:
                # Extraire et afficher l'appel d'outil structuré
                tool_call_str = content.replace("!native_tool ", "")
                tool_call = json.loads(tool_call_str)
                print(f"  Outil: {tool_call['name']}")
                print(f"  Arguments: {json.dumps(tool_call['args'], indent=2)}")
            except json.JSONDecodeError:
                print(f"  Contenu brut: {content}")
        else:
            print(f"--- [RÔLE: ASSISTANT] ---")
        print(content)
    print("-" * 50)

if __name__ == "__main__":
    chat_history = load_chat_history("full_chat_history.json")
    for msg in chat_history:
        process_message(msg)
```