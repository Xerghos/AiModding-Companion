# Documentation Technique : features\context\auth.py

## Description Concise

Ce module gère l'authentification avec les services Google, spécifiquement pour Google Drive et Google Sheets. Il prend en charge le flux d'authentification OAuth 2.0, y compris le chargement des identifiants, le rafraîchissement des tokens d'accès et la gestion interactive de l'authentification via le navigateur. Il retourne des objets de service `googleapiclient` pour interagir avec les APIs Drive et Sheets.

## Dépendances

*   **os**: Module standard Python pour interagir avec le système d'exploitation (vérification de l'existence de fichiers).
*   **logging**: Module standard Python pour la journalisation des événements.
*   **google\_auth\_oauthlib.flow.InstalledAppFlow**: Pour gérer le flux d'installation d'applications OAuth 2.0.
*   **google.auth.transport.requests.Request**: Pour gérer les requêtes d'authentification.
*   **google.oauth2.credentials.Credentials**: Pour gérer les identifiants d'authentification Google.
*   **google.auth.exceptions.RefreshError**: Pour gérer les erreurs lors du rafraîchissement des tokens.
*   **googleapiclient.discovery.build**: Pour construire des clients de service pour les APIs Google.
*   **config**: Module local contenant des configurations telles que les chemins de fichiers (`get_path`), les scopes (`GDRIVE_SCOPES`), les noms de fichiers de token (`GDRIVE_TOKEN_FILE`) et de secrets (`GDRIVE_CREDS_FILE`), et un logger personnalisé (`get_logger`).
*   **features.Decorators.trace\_action**: Un décorateur pour tracer les actions.

---

## Fonctions

### `get_google_services(result_queue)`

#### Signature

```python
def get_google_services(result_queue: Any) -> Tuple[Optional[Resource], Optional[Resource]]
```

#### Arguments

*   `result_queue` (`Any`): Une file d'attente (probablement d'un module `multiprocessing` ou `queue`) pour communiquer des mises à jour de l'interface utilisateur, notamment des messages d'état ou d'erreur. Si `None`, aucune mise à jour de l'UI n'est envoyée.

#### Retours

*   Un tuple contenant deux éléments :
    *   `service_drive` (`Optional[Resource]`): L'objet de service construit pour l'API Google Drive v3, ou `None` en cas d'échec.
    *   `service_sheets` (`Optional[Resource]`): L'objet de service construit pour l'API Google Sheets v4, ou `None` en cas d'échec.

#### Logique Interne

1.  Initialise `creds` à `None`.
2.  Détermine les chemins complets pour le fichier de token (`token_path`) et le fichier de secrets du client (`creds_path`) en utilisant `config.get_path`.
3.  **Vérification du fichier de secrets**:
    *   Si `creds_path` n'existe pas, un message d'erreur est journalisé. Si `result_queue` est fourni, un message UI est envoyé indiquant l'absence du fichier et le passage en mode local. La fonction retourne `None, None`.
4.  **Chargement du token existant**:
    *   Si `token_path` existe, tente de charger les identifiants à partir de ce fichier en utilisant `Credentials.from_authorized_user_file` avec les `GDRIVE_SCOPES` définis dans la configuration.
    *   En cas d'exception lors du chargement, `creds` est réinitialisé à `None`.
5.  **Authentification et rafraîchissement**:
    *   Si `creds` est `None` ou si les identifiants ne sont pas valides (`creds.valid` est `False`) :
        *   **Rafraîchissement du token**: Si `creds` existe, qu'il est expiré (`creds.expired`) et qu'il possède un `refresh_token`, la fonction tente de rafraîchir le token en utilisant `creds.refresh(Request())`. En cas d'échec (`RefreshError` ou autre `Exception`), `creds` est réinitialisé à `None`.
        *   **Flux d'authentification interactif**: Si, après la tentative de rafraîchissement, `creds` est toujours `None`, un flux d'authentification interactif est lancé :
            *   Si `result_queue` est fourni, un message UI est envoyé pour indiquer que l'authentification Google est requise via le navigateur.
            *   `InstalledAppFlow.from_client_secrets_file` est utilisé pour créer un objet `flow` avec le fichier de secrets et les scopes.
            *   `flow.run_local_server(port=0)` démarre un serveur web local temporaire pour gérer le flux OAuth. L'utilisateur sera invité à se connecter et autoriser l'application via son navigateur. Les identifiants obtenus sont stockés dans `creds`.
            *   En cas d'exception pendant ce flux, un message d'erreur est journalisé et la fonction retourne `None, None`.
        *   **Sauvegarde du nouveau token**: Une fois de nouveaux `creds` obtenus (soit par rafraîchissement réussi, soit par le flux interactif), ils sont sauvegardés au format JSON dans `token_path` pour une utilisation future. En cas d'échec de sauvegarde, une erreur est journalisée.
6.  **Construction des services Google**:
    *   Si des identifiants valides (`creds`) sont disponibles, les objets de service pour Google Drive (v3) et Google Sheets (v4) sont construits en utilisant `googleapiclient.discovery.build` avec les identifiants.
    *   En cas d'exception lors de la construction des services, un message d'erreur est journalisé et la fonction retourne `None, None`.
7.  Si tout s'est bien passé, la fonction retourne les objets `service_drive` et `service_sheets` construits.

---

## Exemple d'usage

```python
# Supposons que config.py et features/Decorators.py sont correctement configurés
# et que les fichiers GDRIVE_CREDS_FILE et GDRIVE_TOKEN_FILE existent ou peuvent être générés.

from features.context.auth import get_google_services
import queue

# Créer une file d'attente pour recevoir les mises à jour UI
message_queue = queue.Queue()

# Obtenir les services Google
drive_service, sheets_service = get_google_services(message_queue)

if drive_service and sheets_service:
    print("Services Google Drive et Sheets obtenus avec succès.")

    # Exemple d'utilisation de Google Drive API
    try:
        results = drive_service.files().list(pageSize=10, fields="nextPageToken, files(id, name)").execute()
        items = results.get('files', [])
        print("Fichiers dans Google Drive:")
        if not items:
            print('Aucun fichier trouvé.')
        else:
            for item in items:
                print(f"{item['name']} ({item['id']})")
    except Exception as e:
        print(f"Erreur lors de l'accès à Google Drive: {e}")

    # Exemple d'utilisation de Google Sheets API
    try:
        # Remplacer 'YOUR_SPREADSHEET_ID' par un ID de feuille de calcul réel
        spreadsheet_id = 'YOUR_SPREADSHEET_ID'
        sheet = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        print(f"Feuille de calcul '{sheet.get('properties', {}).get('title', 'N/A')}' chargée.")
    except Exception as e:
        print(f"Erreur lors de l'accès à Google Sheets: {e}")

else:
    print("Échec de l'obtention des services Google.")

# Vérifier s'il y a des messages pour l'UI (ex: "Auth Google requise")
while not message_queue.empty():
    message = message_queue.get()
    print(f"Message UI: {message}")