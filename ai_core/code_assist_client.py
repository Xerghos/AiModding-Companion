"""
Client CodeAssist pour l'API Gemini avec authentification OAuth.
Utilise l'endpoint cloudcode-pa.googleapis.com comme gemini-cli.
"""

import os
import json
import time
import requests
from typing import Optional, Dict, List, Any, Iterator, Generator
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.transport.requests import AuthorizedSession

from features.UnifiedLogger import UnifiedLogger
from ai_core.oauth_validator import load_and_validate_oauth_credentials
from ai_core.code_assist_converter import (
    to_generate_content_request,
    from_generate_content_response
)
from ai_core.sessions import _save_codeassist_payload_log


class QuotaExceededException(Exception):
    """Exception levée quand le quota journalier est épuisé."""
    pass


class FunctionCallObject:
    """
    Objet pour transporter les métadonnées d'un functionCall détecté dans le stream.
    Permet de préserver l'ID de corrélation et thoughtSignature pour l'injection.
    """
    def __init__(self, name, args, call_id=None, thought_signature=None):
        self.name = name
        self.args = args
        self.id = call_id
        self.thought_signature = thought_signature
    
    def __repr__(self):
        return f"FunctionCallObject(name={self.name}, id={self.id})"

# Flag pour activer les logs détaillés du stream (désactivé par défaut)
DEBUG_STREAM = os.environ.get("CODEASSIST_DEBUG_STREAM", "false").lower() == "true"


def get_tools_from_mcp_server() -> Optional[List[Dict[str, Any]]]:
    """
    Récupère les outils depuis le serveur MCP HTTP long-running.
    Convertit le format MCP vers le format Gemini/OpenAI.
    
    Returns:
        Liste des outils au format Gemini/OpenAI, ou None en cas d'erreur
    """
    try:
        mcp_http_port = int(os.environ.get("MCP_HTTP_PORT", "8000"))
        mcp_http_host = os.environ.get("MCP_HTTP_HOST", "127.0.0.1")
        mcp_url = f"http://{mcp_http_host}:{mcp_http_port}/mcp/tools"
        
        # Faire une requête GET au serveur MCP HTTP
        response = requests.get(mcp_url, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        mcp_tools = data.get("tools", [])
        
        if not mcp_tools:
            UnifiedLogger.write(
                "AI_CORE",
                "WARNING",
                "⚠️ Aucun outil retourné par le serveur MCP HTTP"
            )
            return None
        
        # Convertir le format MCP vers le format Gemini/OpenAI
        gemini_tools = []
        for mcp_tool in mcp_tools:
            # Format MCP: {"name": "...", "description": "...", "inputSchema": {...}}
            # Format Gemini/OpenAI: {"name": "...", "description": "...", "parameters": {...}}
            gemini_tool = {
                "name": mcp_tool.get("name"),
                "description": mcp_tool.get("description", ""),
                "parameters": mcp_tool.get("inputSchema", {})
            }
            
            # Convertir les types en majuscules pour Gemini (Gemini utilise uppercase)
            def convert_types_to_uppercase(obj):
                """Convertit récursivement les types en majuscules."""
                if isinstance(obj, dict):
                    result = {}
                    for k, v in obj.items():
                        if k == "type" and isinstance(v, str):
                            result[k] = v.upper()
                        else:
                            result[k] = convert_types_to_uppercase(v)
                    return result
                elif isinstance(obj, list):
                    return [convert_types_to_uppercase(item) for item in obj]
                else:
                    return obj
            
            gemini_tool["parameters"] = convert_types_to_uppercase(gemini_tool["parameters"])
            gemini_tools.append(gemini_tool)
        
        UnifiedLogger.write(
            "AI_CORE",
            "INFO",
            f"✅ {len(gemini_tools)} outils récupérés depuis le serveur MCP HTTP"
        )
        
        # Retourner au format attendu par Gemini API: [{"functionDeclarations": [...]}]
        return [{"functionDeclarations": gemini_tools}]
        
    except requests.exceptions.RequestException as e:
        UnifiedLogger.write(
            "AI_CORE",
            "WARNING",
            f"⚠️ Impossible de récupérer les outils depuis le serveur MCP HTTP: {e}. Utilisation des outils par défaut."
        )
        # Fallback vers TOOLS_SCHEMA si le serveur MCP n'est pas disponible
        try:
            from config.tools_schema import TOOLS_SCHEMA
            return [{"functionDeclarations": TOOLS_SCHEMA}]
        except ImportError:
            return None
    except Exception as e:
        UnifiedLogger.write(
            "AI_CORE",
            "ERROR",
            f"❌ Erreur lors de la récupération des outils MCP: {e}"
        )
        return None


class CodeAssistClient:
    """
    Client CodeAssist pour l'API Gemini avec OAuth.
    Utilise l'endpoint cloudcode-pa.googleapis.com comme gemini-cli.
    """
    
    BASE_ENDPOINT = "https://cloudcode-pa.googleapis.com"
    API_VERSION = "v1internal"
    
    # Headers capturés depuis le vrai client Gemini CLI (v0.22.5)
    # Permet d'éviter le rate-limiting agressif appliqué aux clients génériques "python-requests"
    GEMINI_CLI_USER_AGENT = "GeminiCLI/0.22.5/gemini-3-pro-preview (win32; x64) google-api-nodejs-client/9.15.1"
    GEMINI_CLI_CLIENT_HEADER = "gl-node/25.2.1"
    
    def __init__(self, project_id: Optional[str] = None, session_id: Optional[str] = None, use_personal_quota: bool = True):
        """
        Initialise le client CodeAssist.
        
        Args:
            project_id: ID du projet Google Cloud (optionnel, peut être obtenu via setupUser)
            session_id: ID de session pour maintenir le contexte (optionnel)
            use_personal_quota: Si True (défaut), utilise le quota personnel Google AI Pro sans projet GCP.
                                Si False, utilise un projet GCP (project_id requis ou depuis env)
        """
        self.token_path = os.path.join(
            os.path.expanduser("~"), 
            ".config", 
            "google", 
            "gemini_oauth_token.json"
        )
        self._creds: Optional[Credentials] = None
        self._access_token: Optional[str] = None
        self._session: Optional[AuthorizedSession] = None  # Session autorisée (comme gemini-cli)
        
        # Pour utiliser le quota personnel (comme gemini-cli), on ne doit PAS définir project
        # Seulement utiliser project_id si explicitement fourni ET si use_personal_quota=False
        if use_personal_quota:
            # Par défaut : utiliser quota personnel (projet par défaut de Gemini CLI)
            # Même si project_id est fourni ou dans l'environnement, on l'ignore
            # Utiliser le projet magique "main-keyword-qhv63" qui semble être requis par l'API v1internal
            self.project_id = "main-keyword-qhv63"
        else:
            # Utilisation d'un projet GCP : utiliser project_id fourni ou depuis l'environnement
            if project_id:
                self.project_id = project_id
            else:
                self.project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT_ID")
        
        self.session_id = session_id
    
    def _get_authorized_session(self) -> Optional[AuthorizedSession]:
        """
        Récupère une session autorisée (comme gemini-cli).
        AuthorizedSession gère automatiquement le refresh du token et les headers.
        """
        try:
            from ai_core.oauth_validator import should_refresh_token, save_oauth_credentials

            # Refresh proactif: si aucun refresh depuis 30 minutes
            force_refresh = should_refresh_token(self.token_path)
            if force_refresh:
                UnifiedLogger.write(
                    "AI_CORE",
                    "AUTH",
                    "🔄 Token OAuth > 30min, refresh proactif..."
                )

            if self._creds is None or not self._creds.valid or force_refresh:
                creds, error_msg = load_and_validate_oauth_credentials(self.token_path)
                if creds is None:
                    UnifiedLogger.write(
                        "AI_CORE",
                        "ERROR",
                        f"❌ Impossible de charger les credentials OAuth: {error_msg}"
                    )
                    return None
                self._creds = creds
                # Recréer la session si les credentials ont changé
                self._session = None
            
            # Rafraîchir si nécessaire OU si refresh proactif demandé
            if (force_refresh or not self._creds.valid) and self._creds.refresh_token:
                self._creds.refresh(Request())
                save_oauth_credentials(self._creds, self.token_path)
                # Recréer la session après refresh
                self._session = None
            
            # Créer ou réutiliser la session autorisée
            if self._creds and self._creds.valid:
                if self._session is None:
                    # AuthorizedSession gère automatiquement :
                    # - Le header Authorization avec le token
                    # - Le refresh du token si nécessaire
                    # - Les headers supplémentaires requis par Google
                    self._session = AuthorizedSession(self._creds)
                    
                    # MIMIC GEMINI CLI: Injecter les headers exacts pour éviter le rate-limiting
                    self._session.headers.update({
                        "User-Agent": self.GEMINI_CLI_USER_AGENT,
                        "x-goog-api-client": self.GEMINI_CLI_CLIENT_HEADER
                    })
                    
                    UnifiedLogger.write(
                        "AI_CORE",
                        "AUTH",
                        f"✅ Session autorisée configurée avec User-Agent: {self.GEMINI_CLI_USER_AGENT[:20]}..."
                    )
                return self._session
            
            return None
        except Exception as e:
            UnifiedLogger.write(
                "AI_CORE",
                "ERROR",
                f"❌ Erreur lors de la création de la session autorisée: {e}"
            )
            return None
    
    def _get_access_token(self) -> Optional[str]:
        """Récupère un access token valide (OAuth) - méthode legacy pour compatibilité."""
        session = self._get_authorized_session()
        if session and self._creds and self._creds.valid:
            return self._creds.token
        return None
    
    def _get_method_url(self, method: str) -> str:
        """
        Construit l'URL pour une méthode CodeAssist.
        
        Args:
            method: Nom de la méthode (ex: "generateContent", "streamGenerateContent")
            
        Returns:
            URL complète pour la méthode
        """
        endpoint = os.environ.get("CODE_ASSIST_ENDPOINT", self.BASE_ENDPOINT)
        return f"{endpoint}/{self.API_VERSION}:{method}"
    
    def _request_post(
        self,
        method: str,
        payload: Dict[str, Any],
        signal: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Effectue une requête POST vers l'API CodeAssist.
        
        Args:
            method: Nom de la méthode (ex: "generateContent")
            payload: Données à envoyer
            signal: Signal d'annulation (optionnel)
            
        Returns:
            Réponse JSON de l'API
        """
        MAX_RETRIES = 3
        RETRY_DELAYS = [1, 2, 4]  # Backoff exponentiel

        last_exc: Optional[Exception] = None

        for attempt in range(MAX_RETRIES):
            # Utiliser AuthorizedSession (comme gemini-cli) au lieu de requests.post() manuel
            session = self._get_authorized_session()
            if not session:
                raise ValueError("Impossible d'obtenir une session autorisée OAuth valide")

            url = self._get_method_url(method)

            UnifiedLogger.write(
                "AI_CORE",
                "START",
                f"CodeAssist API: {method} (OAuth AuthorizedSession) try {attempt + 1}/{MAX_RETRIES}"
            )

            # Log du payload final juste avant l'envoi HTTP (comme gemini-cli)
            # Sauvegarder seulement au premier essai pour éviter les doublons
            if attempt == 0:
                try:
                    _save_codeassist_payload_log(
                        payload.get("model", "unknown"),
                        payload,
                        {
                            "method": method,
                            "attempt": attempt + 1,
                            "max_retries": MAX_RETRIES,
                            "is_streaming": False,
                            "endpoint": url
                        }
                    )
                except Exception as log_err:
                    UnifiedLogger.write("AI_CORE", "WARN", f"Echec logging payload final: {log_err}")

            # Solution 1 : Sérialisation manuelle JSON pour garantir l'ordre exact des clés
            payload_json = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
            payload_size = len(payload_json.encode('utf-8'))
            
            # Solution 4 : Logging détaillé du JSON sérialisé + vérification ordre des clés (DEBUG seulement)
            if DEBUG_STREAM:
                request_data = payload.get("request", {})
                request_keys = list(request_data.keys()) if isinstance(request_data, dict) else []
                UnifiedLogger.write(
                    "AI_CORE",
                    "DEBUG",
                    f"Payload JSON sérialisé: {payload_size} bytes, ordre clés dans request: {request_keys}"
                )
            UnifiedLogger.write(
                "AI_CORE",
                "DEBUG",
                f"Preview JSON (1000 chars): {payload_json[:1000]}"
            )

            try:
                # Utiliser AuthorizedSession.post() (comme gemini-cli)
                # AuthorizedSession gère automatiquement :
                # - Le header Authorization avec le token
                # - Le refresh du token si nécessaire
                # - Les headers supplémentaires requis par Google
                response = session.post(
                    url,
                    data=payload_json.encode('utf-8'),
                    headers={
                        'Content-Type': 'application/json'
                    },
                    timeout=300  # 5 minutes timeout
                )
                response.raise_for_status()

                result = response.json()

                UnifiedLogger.write(
                    "AI_CORE",
                    "SUCCESS",
                    f"CodeAssist API: {method} réussi"
                )

                return result
            except requests.exceptions.HTTPError as e:
                last_exc = e
                status_code = e.response.status_code if getattr(e, "response", None) is not None else 0

                # Log détail erreur si possible
                try:
                    if getattr(e, "response", None) is not None:
                        error_detail = e.response.json()
                        UnifiedLogger.write(
                            "AI_CORE",
                            "DEBUG",
                            f"Détails erreur: {json.dumps(error_detail, indent=2)}"
                        )
                except Exception:
                    pass

                # 401 -> token expiré / invalide : forcer refresh au prochain tour
                if status_code == 401:
                    UnifiedLogger.write(
                        "AI_CORE",
                        "AUTH",
                        f"Token expiré (401), retry {attempt + 1}/{MAX_RETRIES}"
                    )
                    self._creds = None
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAYS[attempt])
                        continue

                # 429 -> Rate Limit ou Quota Exhausted : distinguer les deux cas
                if status_code == 429:
                    try:
                        error_detail = e.response.json() if getattr(e, "response", None) is not None else {}
                        error_message = str(error_detail.get("error", {}).get("message", "")).lower()
                        
                        # Détecter si c'est un quota épuisé (arrêt définitif)
                        if "quota" in error_message or "exceeded" in error_message or "limit" in error_message:
                            # Vérifier si c'est vraiment un quota épuisé (pas juste un rate limit)
                            if "daily" in error_message or "quota" in error_message:
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "ERROR",
                                    f"❌ Quota journalier épuisé (429) - Arrêt définitif"
                                )
                                raise QuotaExceededException(f"Quota journalier épuisé: {error_message}")
                        
                        # Sinon, c'est un rate limit (retry avec backoff exponentiel + jitter)
                        import random
                        base_delay = 1.0
                        max_delay = 60.0
                        delay = min(max_delay, base_delay * (2 ** attempt) + random.uniform(0, 1))
                        
                        UnifiedLogger.write(
                            "AI_CORE",
                            "WARNING",
                            f"⚠️ Rate Limit (429), retry {attempt + 1}/{MAX_RETRIES} après {delay:.2f}s"
                        )
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(delay)
                            continue
                        else:
                            # Après tous les retries, lever une exception
                            raise Exception(f"Rate Limit persistant après {MAX_RETRIES} tentatives")
                    except QuotaExceededException:
                        raise
                    except Exception as quota_err:
                        # Si on ne peut pas distinguer, traiter comme rate limit
                        import random
                        base_delay = 1.0
                        max_delay = 60.0
                        delay = min(max_delay, base_delay * (2 ** attempt) + random.uniform(0, 1))
                        UnifiedLogger.write(
                            "AI_CORE",
                            "WARNING",
                            f"⚠️ Rate Limit (429) - détection quota échouée, retry {attempt + 1}/{MAX_RETRIES} après {delay:.2f}s"
                        )
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(delay)
                        continue

                # 500 -> erreurs serveur / session : retry simple
                if status_code == 500:
                    UnifiedLogger.write(
                        "AI_CORE",
                        "ERROR",
                        f"Erreur serveur (500), retry {attempt + 1}/{MAX_RETRIES}"
                    )
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAYS[attempt])
                        continue

                raise
            except requests.exceptions.RequestException as e:
                last_exc = e
                UnifiedLogger.write(
                    "AI_CORE",
                    "ERROR",
                    f"❌ Erreur CodeAssist API {method}: {e}"
                )
                raise

        if last_exc:
            raise last_exc
        raise Exception(f"Echec apres {MAX_RETRIES} tentatives")
    
    def _request_streaming_post(
        self,
        method: str,
        payload: Dict[str, Any],
        signal: Optional[Any] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Effectue une requête POST streaming vers l'API CodeAssist.
        Utilise Server-Sent Events (SSE).
        
        Args:
            method: Nom de la méthode (ex: "streamGenerateContent")
            payload: Données à envoyer
            signal: Signal d'annulation (optionnel)
            
        Yields:
            Chunks de réponse JSON
        """
        MAX_RETRIES = 3
        RETRY_DELAYS = [1, 2, 4]

        # Ajouter le paramètre alt=sse pour le streaming
        params = {"alt": "sse"}

        last_exc: Optional[Exception] = None

        for attempt in range(MAX_RETRIES):
            # Utiliser AuthorizedSession (comme gemini-cli) au lieu de requests.post() manuel
            session = self._get_authorized_session()
            if not session:
                raise ValueError("Impossible d'obtenir une session autorisée OAuth valide")

            url = self._get_method_url(method)

            UnifiedLogger.write(
                "AI_CORE",
                "START",
                f"CodeAssist API Streaming: {method} (OAuth AuthorizedSession) try {attempt + 1}/{MAX_RETRIES}"
            )

            # Log du payload final juste avant l'envoi HTTP (comme gemini-cli)
            # Sauvegarder seulement au premier essai pour éviter les doublons
            if attempt == 0:
                try:
                    _save_codeassist_payload_log(
                        payload.get("model", "unknown"),
                        payload,
                        {
                            "method": method,
                            "attempt": attempt + 1,
                            "max_retries": MAX_RETRIES,
                            "is_streaming": True,
                            "endpoint": url
                        }
                    )
                except Exception as log_err:
                    UnifiedLogger.write("AI_CORE", "WARN", f"Echec logging payload final: {log_err}")

            # Solution 1 : Sérialisation manuelle JSON pour garantir l'ordre exact des clés
            payload_json = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
            payload_size = len(payload_json.encode('utf-8'))
            
            # Solution 4 : Logging détaillé du JSON sérialisé + vérification ordre des clés (DEBUG seulement)
            if DEBUG_STREAM:
                request_data = payload.get("request", {})
                request_keys = list(request_data.keys()) if isinstance(request_data, dict) else []
                UnifiedLogger.write(
                    "AI_CORE",
                    "DEBUG",
                    f"Payload JSON sérialisé: {payload_size} bytes, ordre clés dans request: {request_keys}"
                )
            UnifiedLogger.write(
                "AI_CORE",
                "DEBUG",
                f"Preview JSON (1000 chars): {payload_json[:1000]}"
            )

            try:
                # Utiliser AuthorizedSession.post() (comme gemini-cli)
                # AuthorizedSession gère automatiquement :
                # - Le header Authorization avec le token
                # - Le refresh du token si nécessaire
                # - Les headers supplémentaires requis par Google
                response = session.post(
                    url,
                    data=payload_json.encode('utf-8'),
                    headers={
                        'Content-Type': 'application/json'
                    },
                    params=params,
                    stream=True,
                    timeout=300
                )
                response.raise_for_status()

                # Parser les chunks SSE
                line_count = 0
                chunk_count = 0
                for line in response.iter_lines():
                    if line:
                        try:
                            line_text = line.decode('utf-8')
                            line_count += 1
                            
                            # Log chaque ligne brute (DEBUG seulement pour réduire I/O)
                            if DEBUG_STREAM:
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "STREAM_RAW",
                                    f"Ligne {line_count} reçue ({len(line_text)} chars): {line_text[:200]}"
                                )
                            
                            # Parser les chunks SSE de CodeAssist
                            # Format: chaque ligne "data: {...}" est un chunk complet
                            # CodeAssist envoie chaque chunk sur une ligne séparée, pas avec \n\n
                            if line_text.startswith("data: "):
                                data_json = line_text[6:].strip()
                                if data_json:
                                    try:
                                        data = json.loads(data_json)
                                        chunk_count += 1
                                        
                                        # Log structure du chunk (DEBUG seulement)
                                        if DEBUG_STREAM and isinstance(data, dict):
                                            keys = list(data.keys())
                                            UnifiedLogger.write(
                                                "AI_CORE",
                                                "STREAM_STRUCT",
                                                f"Chunk {chunk_count} - Clés: {keys}"
                                            )
                                        
                                        # Log contenu complet (mode DEBUG seulement)
                                        if DEBUG_STREAM:
                                            try:
                                                data_str = json.dumps(data, indent=2, ensure_ascii=False)
                                                UnifiedLogger.write(
                                                    "AI_CORE",
                                                    "STREAM_PARSE",
                                                    f"Chunk {chunk_count} complet:\n{data_str[:1000]}"
                                                )
                                            except Exception:
                                                pass
                                        
                                        yield data
                                    except json.JSONDecodeError as e:
                                        # Erreurs de parsing toujours loggées (important pour diagnostic)
                                        UnifiedLogger.write(
                                            "AI_CORE",
                                            "STREAM_ERROR",
                                            f"Erreur parsing JSON chunk {chunk_count + 1}: {e}"
                                        )
                                        if DEBUG_STREAM:
                                            UnifiedLogger.write(
                                                "AI_CORE",
                                                "STREAM_ERROR",
                                                f"Ligne qui a échoué: {line_text[:500]}"
                                            )
                            elif DEBUG_STREAM:
                                # Ligne qui ne commence pas par "data: " - log seulement en DEBUG
                                if line_text.strip() and not line_text.startswith("event:") and not line_text.startswith("id:"):
                                    UnifiedLogger.write(
                                        "AI_CORE",
                                        "STREAM_RAW",
                                        f"Ligne non-data ignorée ({line_count}): {line_text[:200]}"
                                    )
                        except Exception as e:
                            # Erreurs toujours loggées (important pour diagnostic)
                            UnifiedLogger.write(
                                "AI_CORE",
                                "STREAM_ERROR",
                                f"Erreur traitement ligne {line_count}: {e}"
                            )
                            if DEBUG_STREAM:
                                import traceback
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "STREAM_ERROR",
                                    f"Traceback: {traceback.format_exc()}"
                                )
                
                # Log résumé du parsing SSE (toujours, mais concis)
                if DEBUG_STREAM or chunk_count == 0:
                    UnifiedLogger.write(
                        "AI_CORE",
                        "STREAM_SUMMARY",
                        f"Parsing SSE terminé: {line_count} lignes reçues, {chunk_count} chunks parsés"
                    )
                
                # Si aucun chunk n'a été parsé, logger un avertissement
                if chunk_count == 0:
                    UnifiedLogger.write(
                        "AI_CORE",
                        "STREAM_ERROR",
                        f"Aucun chunk parsé malgré {line_count} lignes reçues."
                    )

                UnifiedLogger.write(
                    "AI_CORE",
                    "SUCCESS",
                    f"CodeAssist API Streaming: {method} terminé"
                )
                return

            except requests.exceptions.HTTPError as e:
                last_exc = e
                status_code = e.response.status_code if getattr(e, "response", None) is not None else 0

                # Log détail erreur si possible
                try:
                    if getattr(e, "response", None) is not None:
                        error_detail = e.response.json()
                        UnifiedLogger.write(
                            "AI_CORE",
                            "DEBUG",
                            f"Détails erreur: {json.dumps(error_detail, indent=2)}"
                        )
                except Exception:
                    pass

                # 400 -> Bad Request : log détaillé pour diagnostic
                if status_code == 400:
                    try:
                        # 🔍 Capturer la réponse HTTP complète
                        response_obj = getattr(e, "response", None)
                        if response_obj is not None:
                            # Log des headers de réponse
                            response_headers = dict(response_obj.headers) if hasattr(response_obj, 'headers') else {}
                            UnifiedLogger.write(
                                "AI_CORE",
                                "DEBUG",
                                f"🔍 Headers réponse HTTP (400): {json.dumps(response_headers, indent=2, ensure_ascii=False)}"
                            )
                            
                            # Log du body brut (avant parsing JSON)
                            try:
                                response_text = response_obj.text if hasattr(response_obj, 'text') else str(response_obj.content)
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "DEBUG",
                                    f"🔍 Body réponse HTTP brut (400): {response_text[:2000]}..."  # Limiter à 2000 chars
                                )
                            except Exception as text_err:
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "WARN",
                                    f"Impossible de lire body réponse: {text_err}"
                                )
                        
                        error_detail = e.response.json() if getattr(e, "response", None) is not None else {}
                        error_message = error_detail.get("error", {}).get("message", "")
                        error_code = error_detail.get("error", {}).get("code", "")
                        error_status = error_detail.get("error", {}).get("status", "")
                        
                        UnifiedLogger.write(
                            "AI_CORE",
                            "ERROR",
                            f"❌ Erreur 400 Bad Request: {error_message} (code: {error_code}, status: {error_status})"
                        )
                        
                        # 🔍 Log des fieldViolations (champs problématiques)
                        error_obj = error_detail.get("error", {})
                        details = error_obj.get("details", [])
                        if details:
                            UnifiedLogger.write(
                                "AI_CORE",
                                "DEBUG",
                                f"🔍 Détails erreur complets: {json.dumps(error_detail, indent=2, ensure_ascii=False)}"
                            )
                            for detail in details:
                                if isinstance(detail, dict):
                                    field_violations = detail.get("fieldViolations", [])
                                    if field_violations:
                                        UnifiedLogger.write(
                                            "AI_CORE",
                                            "ERROR",
                                            f"❌ Field Violations détectées: {len(field_violations)} violation(s)"
                                        )
                                        for violation in field_violations:
                                            field = violation.get("field", "unknown")
                                            description = violation.get("description", "no description")
                                            UnifiedLogger.write(
                                                "AI_CORE",
                                                "ERROR",
                                                f"❌ VIOLATION: field='{field}', description='{description}'"
                                            )
                        else:
                            # Si pas de details, log quand même l'erreur complète
                            UnifiedLogger.write(
                                "AI_CORE",
                                "DEBUG",
                                f"🔍 Erreur complète (sans details): {json.dumps(error_detail, indent=2, ensure_ascii=False)}"
                        )
                        
                        # Log détaillé de la structure du payload qui a causé l'erreur
                        try:
                            request_data = payload.get("request", {})
                            contents = request_data.get("contents", [])
                            UnifiedLogger.write(
                                "AI_CORE",
                                "DEBUG",
                                f"📋 Structure payload (400): {len(contents)} messages dans contents"
                            )
                            
                            # 🔍 Sauvegarder le payload problématique dans un fichier séparé
                            try:
                                from datetime import datetime
                                logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
                                os.makedirs(logs_dir, exist_ok=True)
                                timestamp = datetime.now().strftime("%d-%b_%Hh%M_%S")
                                error_payload_file = os.path.join(logs_dir, f"error_400_payload_{timestamp}.json")
                                
                                # 🔍 Analyser le payload pour identifier les problèmes potentiels
                                payload_analysis = {
                                    "error": error_detail,
                                    "payload": payload,
                                    "timestamp": datetime.now().isoformat(),
                                    "analysis": {
                                        "functionCall_with_id": False,
                                        "functionResponse_with_id": False,
                                        "id_mismatch": False,
                                        "id_generated_by_client": False
                                    }
                                }
                                
                                # Analyser les IDs dans le payload
                                request_data = payload.get("request", {})
                                contents = request_data.get("contents", [])
                                for idx, msg in enumerate(contents):
                                    if msg.get("role") == "model":
                                        parts = msg.get("parts", [])
                                        for part in parts:
                                            if "functionCall" in part:
                                                func_call = part["functionCall"]
                                                if func_call.get("id"):
                                                    payload_analysis["analysis"]["functionCall_with_id"] = True
                                    elif msg.get("role") == "function":
                                        parts = msg.get("parts", [])
                                        for part in parts:
                                            if "functionResponse" in part:
                                                func_resp = part["functionResponse"]
                                                if func_resp.get("id"):
                                                    payload_analysis["analysis"]["functionResponse_with_id"] = True
                                                    # Vérifier si l'ID semble être un UUID généré (format standard)
                                                    resp_id = func_resp.get("id")
                                                    if resp_id and len(resp_id) == 36 and resp_id.count('-') == 4:
                                                        payload_analysis["analysis"]["id_generated_by_client"] = True
                                
                                with open(error_payload_file, "w", encoding="utf-8") as f:
                                    json.dump(payload_analysis, f, indent=2, ensure_ascii=False)
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "ERROR",
                                    f"💾 Payload problématique sauvegardé: {error_payload_file}"
                                )
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "DEBUG",
                                    f"🔍 Analyse payload: {json.dumps(payload_analysis['analysis'], indent=2, ensure_ascii=False)}"
                                )
                            except Exception as save_err:
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "WARN",
                                    f"Impossible de sauvegarder payload: {save_err}"
                                )
                            
                            # Vérifier chaque message dans contents avec plus de détails
                            for idx, msg in enumerate(contents):
                                role = msg.get("role", "unknown")
                                parts = msg.get("parts", [])
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "DEBUG",
                                    f"📋 Message {idx}: role={role}, {len(parts)} parts"
                                )
                                
                                # Vérifier les functionCall et functionResponse avec TOUS les champs
                                for part_idx, part in enumerate(parts):
                                    if "functionCall" in part:
                                        func_call = part["functionCall"]
                                        # 🔍 Log de TOUS les champs du functionCall
                                        all_keys = list(func_call.keys())
                                        has_thought_sig = "thoughtSignature" in func_call or "thought_signature" in func_call
                                        UnifiedLogger.write(
                                            "AI_CORE",
                                            "DEBUG",
                                            f"📋 Part {part_idx} - functionCall: name={func_call.get('name')}, "
                                            f"id={func_call.get('id', 'ABSENT')}, "
                                            f"keys={all_keys}, "
                                            f"has_thoughtSignature={has_thought_sig}"
                                        )
                                        # 🔍 Log du contenu complet du functionCall
                                        UnifiedLogger.write(
                                            "AI_CORE",
                                            "DEBUG",
                                            f"📋 Part {part_idx} - functionCall complet: {json.dumps(func_call, indent=2, ensure_ascii=False)}"
                                        )
                                    if "functionResponse" in part:
                                        func_resp = part["functionResponse"]
                                        resp_content = func_resp.get("response", {}).get("output", "")  # ✅ "output" au lieu de "content"
                                        output_type = type(resp_content).__name__
                                        output_len = len(str(resp_content))
                                        UnifiedLogger.write(
                                            "AI_CORE",
                                            "DEBUG",
                                            f"📋 Part {part_idx} - functionResponse: name={func_resp.get('name')}, "
                                            f"id={func_resp.get('id', 'ABSENT')}, "
                                            f"output_type={output_type}, output_len={output_len}"
                                        )
                                        # 🔍 Vérifier la corrélation ID
                                        if idx > 0:
                                            prev_msg = contents[idx - 1]
                                            if prev_msg.get("role") == "model":
                                                prev_parts = prev_msg.get("parts", [])
                                                for prev_part in prev_parts:
                                                    if "functionCall" in prev_part:
                                                        prev_func_call = prev_part["functionCall"]
                                                        prev_id = prev_func_call.get("id")
                                                        resp_id = func_resp.get("id")
                                                        if prev_id and resp_id:
                                                            if prev_id != resp_id:
                                                                UnifiedLogger.write(
                                                                    "AI_CORE",
                                                                    "ERROR",
                                                                    f"❌ ID MISMATCH: functionCall.id={prev_id} != functionResponse.id={resp_id}"
                                                                )
                                                        elif not prev_id and resp_id:
                                                            UnifiedLogger.write(
                                                                "AI_CORE",
                                                                "WARNING",
                                                                f"⚠️ functionCall.id ABSENT mais functionResponse.id={resp_id} présent"
                                        )
                                        # Log un extrait du contenu pour voir le format
                                        if output_len > 0:
                                            output_preview = str(resp_content)[:500]
                                            UnifiedLogger.write(
                                                "AI_CORE",
                                                "DEBUG",
                                                f"📋 functionResponse.output preview: {output_preview}..."
                                            )
                        except Exception as payload_err:
                            UnifiedLogger.write(
                                "AI_CORE",
                                "WARN",
                                f"Erreur analyse payload (400): {payload_err}"
                            )
                    except Exception as err_detail:
                        UnifiedLogger.write(
                            "AI_CORE",
                            "WARN",
                            f"Erreur extraction détails 400: {err_detail}"
                        )

                if status_code == 401:
                    UnifiedLogger.write(
                        "AI_CORE",
                        "AUTH",
                        f"Token expiré (401), retry {attempt + 1}/{MAX_RETRIES}"
                    )
                    self._creds = None
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAYS[attempt])
                        continue

                # 429 -> Rate Limit ou Quota Exhausted : distinguer les deux cas
                if status_code == 429:
                    try:
                        error_detail = e.response.json() if getattr(e, "response", None) is not None else {}
                        error_message = str(error_detail.get("error", {}).get("message", "")).lower()
                        
                        # Détecter si c'est un quota épuisé (arrêt définitif)
                        if "quota" in error_message or "exceeded" in error_message or "limit" in error_message:
                            # Vérifier si c'est vraiment un quota épuisé (pas juste un rate limit)
                            if "daily" in error_message or "quota" in error_message:
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "ERROR",
                                    f"❌ Quota journalier épuisé (429) streaming - Arrêt définitif"
                                )
                                raise QuotaExceededException(f"Quota journalier épuisé: {error_message}")
                        
                        # Sinon, c'est un rate limit (retry avec backoff exponentiel + jitter)
                        import random
                        base_delay = 1.0
                        max_delay = 60.0
                        delay = min(max_delay, base_delay * (2 ** attempt) + random.uniform(0, 1))
                        
                        UnifiedLogger.write(
                            "AI_CORE",
                            "WARNING",
                            f"⚠️ Rate Limit (429) streaming, retry {attempt + 1}/{MAX_RETRIES} après {delay:.2f}s"
                        )
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(delay)
                            continue
                        else:
                            # Après tous les retries, lever une exception
                            raise Exception(f"Rate Limit persistant après {MAX_RETRIES} tentatives")
                    except QuotaExceededException:
                        raise
                    except Exception as quota_err:
                        # Si on ne peut pas distinguer, traiter comme rate limit
                        import random
                        base_delay = 1.0
                        max_delay = 60.0
                        delay = min(max_delay, base_delay * (2 ** attempt) + random.uniform(0, 1))
                        UnifiedLogger.write(
                            "AI_CORE",
                            "WARNING",
                            f"⚠️ Rate Limit (429) streaming - détection quota échouée, retry {attempt + 1}/{MAX_RETRIES} après {delay:.2f}s"
                        )
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(delay)
                        continue

                if status_code == 500:
                    UnifiedLogger.write(
                        "AI_CORE",
                        "ERROR",
                        f"Erreur serveur (500), retry {attempt + 1}/{MAX_RETRIES}"
                    )
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAYS[attempt])
                        continue

                raise

            except requests.exceptions.RequestException as e:
                last_exc = e
                UnifiedLogger.write(
                    "AI_CORE",
                    "ERROR",
                    f"❌ Erreur CodeAssist API Streaming {method}: {e}"
                )
                raise

        if last_exc:
            raise last_exc
        raise Exception(f"Echec apres {MAX_RETRIES} tentatives")
    
    def generate_content(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        system_instruction: Optional[str] = None,
        shadow_history: Optional[List[Dict]] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Génère du contenu via l'API CodeAssist.
        
        Args:
            model: Nom du modèle (ex: "gemini-3-flash-preview")
            messages: Liste de messages au format OpenAI
            stream: Mode streaming
            temperature: Température
            max_tokens: Nombre max de tokens
            tools: Outils (tool calling)
            system_instruction: Instruction système
            **kwargs: Paramètres additionnels
            
        Returns:
            Réponse de l'API ou générateur si stream=True
        """
        import uuid
        import os
        # Format Gemini CLI: hex string de 14 caractères (ex: "c59ec6dbb5bc58")
        user_prompt_id = os.urandom(7).hex()

        # Mapper les paramètres camelCase vers snake_case pour compatibilité
        # Aligné sur les paramètres Vertex AI/Code Assist
        mapped_kwargs = kwargs.copy()

        # Paramètres de sécurité et configuration
        if "safetySettings" in kwargs:
            mapped_kwargs["safety_settings"] = kwargs["safetySettings"]
        if "cachedContent" in kwargs:
            mapped_kwargs["cached_content"] = kwargs["cachedContent"]

        # Paramètres de génération (cas où ils seraient passés en camelCase)
        if "responseMimeType" in kwargs:
            mapped_kwargs["response_mime_type"] = kwargs["responseMimeType"]
        if "responseSchema" in kwargs:
            mapped_kwargs["response_schema"] = kwargs["responseSchema"]
        if "responseJsonSchema" in kwargs:
            mapped_kwargs["response_json_schema"] = kwargs["responseJsonSchema"]
        if "thinkingConfig" in kwargs:
            mapped_kwargs["thinking_config"] = kwargs["thinkingConfig"]
        if "routingConfig" in kwargs:
            mapped_kwargs["routing_config"] = kwargs["routingConfig"]
        if "modelSelectionConfig" in kwargs:
            mapped_kwargs["model_selection_config"] = kwargs["modelSelectionConfig"]
        if "responseModalities" in kwargs:
            mapped_kwargs["response_modalities"] = kwargs["responseModalities"]
        if "mediaResolution" in kwargs:
            mapped_kwargs["media_resolution"] = kwargs["mediaResolution"]
        if "speechConfig" in kwargs:
            mapped_kwargs["speech_config"] = kwargs["speechConfig"]
        if "audioTimestamp" in kwargs:
            mapped_kwargs["audio_timestamp"] = kwargs["audioTimestamp"]

        # RÉSOLUTION DES OUTILS MCP
        # Si tools contient des entrées de type "mcp" (référence MCP), les remplacer par les vraies définitions
        if tools is not None and len(tools) > 0:
            has_mcp_reference = any(
                isinstance(t, dict) and t.get("type") == "mcp" 
                for t in tools
            )
            if has_mcp_reference:
                UnifiedLogger.write(
                    "AI_CORE",
                    "MCP",
                    "🔧 Détection d'outils MCP (références). Résolution vers définitions réelles..."
                )
                # Remplacer par les vraies définitions d'outils depuis le serveur MCP
                resolved_tools = get_tools_from_mcp_server()
                if resolved_tools and len(resolved_tools) > 0:
                    tools = resolved_tools
                    tool_count = len(tools[0].get('functionDeclarations', [])) if isinstance(tools[0], dict) else 0
                    UnifiedLogger.write(
                        "AI_CORE",
                        "MCP",
                        f"✅ {tool_count} outils MCP résolus vers définitions réelles"
                    )
                else:
                    UnifiedLogger.write(
                        "AI_CORE",
                        "WARNING",
                        "⚠️ Échec résolution outils MCP, utilisation sans outils"
                    )
                    tools = None
        
        # FALLBACK: Récupérer automatiquement les outils depuis le serveur MCP HTTP si non fournis
        if tools is None:
            tools = get_tools_from_mcp_server()
            if tools and len(tools) > 0:
                tool_count = len(tools[0].get('functionDeclarations', [])) if isinstance(tools[0], dict) else 0
                UnifiedLogger.write(
                    "AI_CORE",
                    "INFO",
                    f"✅ {tool_count} outils récupérés depuis le serveur MCP HTTP"
                )
        
        # Log des outils si présents
        if tools:
            # Compter le nombre réel de fonctions
            total_funcs = 0
            for tool in tools:
                if "functionDeclarations" in tool:
                    total_funcs += len(tool["functionDeclarations"])
            
            UnifiedLogger.write(
                "AI_CORE",
                "DEBUG",
                f"Outils passés à CodeAssist: {total_funcs} fonctions (dans {len(tools)} groupe(s))"
            )
            try:
                tools_str = json.dumps(tools, indent=2, ensure_ascii=False)
                UnifiedLogger.write(
                    "AI_CORE",
                    "DEBUG",
                    f"Détails outils:\n{tools_str[:1000]}"  # Limiter à 1000 chars
                )
            except:
                pass
        
        # Convertir au format CodeAssist
        ca_request = to_generate_content_request(
            model=model,
            messages=messages,
            shadow_history=shadow_history,  # Passer shadow_history pour continuation après tool call
            user_prompt_id=user_prompt_id,
            project_id=self.project_id,
            session_id=self.session_id,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            system_instruction=system_instruction,
            **mapped_kwargs
        )
        
        # Vérification post-conversion
        request_data = ca_request.get("request", {})
        if tools:
            # Log des outils convertis pour débogage
            try:
                tools_converted = request_data.get("tools", [])
                tools_count = len(tools_converted)
                UnifiedLogger.write(
                    "AI_CORE",
                    "DEBUG",
                    f"Outils convertis dans request: {tools_count} groupes d'outils"
                )
            except:
                pass
        
        if stream:
            # Mode streaming
            method = "streamGenerateContent"
            chunks = self._request_streaming_post(method, ca_request)
            
            # Convertir les chunks au format LiteLLM
            def stream_generator():
                full_text = ""
                total_chunks = 0
                chunks_with_text = 0
                chunks_with_metrics = 0
                
                for chunk in chunks:
                    total_chunks += 1
                    
                    # Log chunk brut (mode DEBUG seulement)
                    if DEBUG_STREAM:
                        try:
                            chunk_str = json.dumps(chunk, indent=2, ensure_ascii=False)
                            UnifiedLogger.write(
                                "AI_CORE",
                                "STREAM_CHUNK_RAW",
                                f"Chunk {total_chunks} brut:\n{chunk_str[:1000]}"
                            )
                        except Exception:
                            UnifiedLogger.write(
                                "AI_CORE",
                                "STREAM_CHUNK_RAW",
                                f"Chunk {total_chunks} brut (non-serializable): {type(chunk)}"
                            )
                    
                    # DEBUG: Log la structure du chunk si usageMetadata est présent
                    if isinstance(chunk, dict):
                        # Vérifier usageMetadata dans le chunk original (avant conversion)
                        if "usageMetadata" in chunk:
                            chunks_with_metrics += 1
                            usage = chunk["usageMetadata"]
                            prompt_tokens = usage.get("promptTokenCount", 0)
                            candidates_tokens = usage.get("candidatesTokenCount", 0)
                            total_tokens = usage.get("totalTokenCount", 0)
                            UnifiedLogger.write(
                                "AI_CORE",
                                "METRICS",
                                f"Usage (chunk direct): Prompt={prompt_tokens}, Candidates={candidates_tokens}, Total={total_tokens}"
                            )
                        # Vérifier aussi dans response si présent
                        if "response" in chunk and isinstance(chunk["response"], dict):
                            if "usageMetadata" in chunk["response"]:
                                chunks_with_metrics += 1
                                usage = chunk["response"]["usageMetadata"]
                                prompt_tokens = usage.get("promptTokenCount", 0)
                                candidates_tokens = usage.get("candidatesTokenCount", 0)
                                total_tokens = usage.get("totalTokenCount", 0)
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "METRICS",
                                    f"Usage (response): Prompt={prompt_tokens}, Candidates={candidates_tokens}, Total={total_tokens}"
                                )
                    
                    # Convertir chaque chunk
                    gemini_chunk = from_generate_content_response(chunk)
                    
                    # Log chunk converti (mode DEBUG seulement)
                    if DEBUG_STREAM:
                        try:
                            gemini_str = json.dumps(gemini_chunk, indent=2, ensure_ascii=False)
                            UnifiedLogger.write(
                                "AI_CORE",
                                "STREAM_CHUNK_CONV",
                                f"Chunk {total_chunks} converti:\n{gemini_str[:1000]}"
                            )
                        except Exception:
                            UnifiedLogger.write(
                                "AI_CORE",
                                "STREAM_CHUNK_CONV",
                                f"Chunk {total_chunks} converti (non-serializable): {type(gemini_chunk)}"
                            )
                    
                    # Log structure candidates (toujours)
                    if "candidates" in gemini_chunk:
                        UnifiedLogger.write(
                            "AI_CORE",
                            "STREAM_CANDIDATES",
                            f"Chunk {total_chunks} - Nombre de candidates: {len(gemini_chunk['candidates'])}"
                        )
                        if len(gemini_chunk['candidates']) > 0:
                            candidate = gemini_chunk['candidates'][0]
                            candidate_keys = list(candidate.keys()) if isinstance(candidate, dict) else []
                            UnifiedLogger.write(
                                "AI_CORE",
                                "STREAM_CANDIDATES",
                                f"Chunk {total_chunks} - Clés candidate[0]: {candidate_keys}"
                            )
                    else:
                        UnifiedLogger.write(
                            "AI_CORE",
                            "STREAM_CANDIDATES",
                            f"Chunk {total_chunks} - Aucun candidate présent"
                        )
                    
                    # Extraire le texte du chunk
                    if "candidates" in gemini_chunk and len(gemini_chunk["candidates"]) > 0:
                        candidate = gemini_chunk["candidates"][0]
                        
                        # Log structure du candidate
                        if DEBUG_STREAM:
                            if isinstance(candidate, dict):
                                candidate_keys = list(candidate.keys())
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "STREAM_CANDIDATES",
                                    f"Chunk {total_chunks} - Structure candidate: {candidate_keys}"
                                )
                        
                        if "content" in candidate:
                            if isinstance(candidate["content"], dict) and "parts" in candidate["content"]:
                                # Log nombre de parts
                                parts_count = len(candidate["content"]["parts"])
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "STREAM_CANDIDATES",
                                    f"Chunk {total_chunks} - Nombre de parts: {parts_count}"
                                )
                                
                                chunk_text = ""
                                chunk_thinking = ""
                                
                                for i, part in enumerate(candidate["content"]["parts"]):
                                    if isinstance(part, dict):
                                        # Vérifier si c'est du thinking (thought: true) ou de la réponse finale
                                        # Le champ 'thought' peut être un booléen directement dans la part
                                        # IMPORTANT: Si 'thought' n'est pas présent ou est False, c'est de la réponse finale
                                        thought_value = part.get("thought", False)
                                        is_thinking = (thought_value is True) or (thought_value == True)
                                        
                                        # Debug: log la structure de la part pour vérifier
                                        if DEBUG_STREAM and i == 0:
                                            part_keys = list(part.keys())
                                            UnifiedLogger.write(
                                                "AI_CORE",
                                                "STREAM_CANDIDATES",
                                                f"Chunk {total_chunks} - Part {i} keys: {part_keys}, thought={part.get('thought', 'NOT_FOUND')}"
                                            )
                                        
                                        if "text" in part:
                                            part_text = part["text"]
                                            
                                            if is_thinking:
                                                # C'est du thinking → accumuler séparément
                                                chunk_thinking += part_text
                                                if DEBUG_STREAM:
                                                    UnifiedLogger.write(
                                                        "AI_CORE",
                                                        "STREAM_CANDIDATES",
                                                        f"Chunk {total_chunks} - Part {i} (thinking): {len(part_text)} caractères"
                                                    )
                                            else:
                                                # C'est la réponse finale
                                                chunk_text += part_text
                                                if DEBUG_STREAM:
                                                    UnifiedLogger.write(
                                                        "AI_CORE",
                                                        "STREAM_CANDIDATES",
                                                        f"Chunk {total_chunks} - Part {i} (text): {len(part_text)} caractères"
                                                    )
                                        elif "functionCall" in part:
                                            # L'IA veut appeler un outil - détecter directement sans conversion texte
                                            func_call = part["functionCall"]
                                            func_name = func_call.get("name", "unknown_tool")
                                            func_args = func_call.get("args", {})
                                            
                                            # Extraire l'ID de corrélation (id ou call_id)
                                            # L'ID peut être dans func_call directement ou dans part
                                            # NOTE: Le vrai Gemini CLI ne reçoit SOUVENT PAS d'ID dans le functionCall du modèle
                                            # C'est le client qui en génère un pour la réponse.
                                            func_call_id = (
                                                func_call.get("id") or 
                                                func_call.get("call_id") or
                                                part.get("id") or
                                                part.get("call_id")
                                            )
                                            
                                            # Extraire thoughtSignature si présent (peut être dans func_call ou part)
                                            thought_sig = (
                                                func_call.get("thoughtSignature") or
                                                part.get("thoughtSignature")
                                            )
                                            
                                            # Si pas d'ID, on en générera un côté worker ou on laissera None
                                            # L'important est de capturer le call
                                            if not func_call_id:
                                                UnifiedLogger.write(
                                                    "AI_CORE",
                                                    "WARNING",
                                                    f"FunctionCall sans ID (normal pour Gemini CLI). Name={func_name}"
                                                )
                                            
                                            # Créer un objet FunctionCallObject pour transporter les métadonnées
                                            func_call_obj = FunctionCallObject(
                                                name=func_name,
                                                args=func_args,
                                                call_id=func_call_id,
                                                thought_signature=thought_sig
                                            )
                                            
                                            UnifiedLogger.write(
                                                "AI_CORE",
                                                "STREAM_CANDIDATES",
                                                f"Chunk {total_chunks} - FunctionCall détecté: {func_name}, id={func_call_id}, thoughtSignature={'présent' if thought_sig else 'absent'}"
                                            )
                                            
                                            # Yielder l'objet directement au lieu de convertir en texte
                                            # Le worker détectera cet objet et gérera l'exécution
                                            yield func_call_obj
                                            
                                            # Ne pas ajouter au chunk_text, le functionCall est géré séparément
                                            # Sortir de la boucle des parts car on a trouvé un functionCall
                                            break
                                
                                # Envoyer le thinking séparément si présent (avec marqueur)
                                if chunk_thinking:
                                    chunks_with_text += 1
                                    full_text += chunk_thinking  # Garder pour l'historique complet
                                    
                                    UnifiedLogger.write(
                                        "AI_CORE",
                                        "STREAM_CANDIDATES",
                                        f"Chunk {total_chunks} - Thinking extrait: {len(chunk_thinking)} caractères"
                                    )
                                    
                                    # Créer un objet marqué comme thinking pour identification
                                    class ThinkingDeltaObject:
                                        def __init__(self, content):
                                            self.content = content
                                            self.text = content
                                            self.is_thinking = True  # Marqueur pour identification
                                        
                                        def __repr__(self):
                                            return f"ThinkingDeltaObject(is_thinking={self.is_thinking}, text_len={len(self.text)})"
                                    
                                    class ThinkingChoiceObject:
                                        def __init__(self, delta):
                                            self.delta = delta
                                    
                                    class ThinkingChunkObject:
                                        def __init__(self, choice):
                                            self.choices = [choice]
                                    
                                    thinking_delta = ThinkingDeltaObject(chunk_thinking)
                                    thinking_choice = ThinkingChoiceObject(thinking_delta)
                                    thinking_chunk = ThinkingChunkObject(thinking_choice)
                                    
                                    # TOUJOURS logger pour vérifier que l'objet est créé correctement
                                    UnifiedLogger.write(
                                        "AI_CORE",
                                        "STREAM_CANDIDATES",
                                        f"Chunk {total_chunks} - Thinking chunk créé: is_thinking={thinking_delta.is_thinking}, type={type(thinking_delta).__name__}, hasattr={hasattr(thinking_delta, 'is_thinking')}"
                                    )
                                    
                                    # Vérifier aussi la structure complète
                                    UnifiedLogger.write(
                                        "AI_CORE",
                                        "STREAM_CANDIDATES",
                                        f"Chunk {total_chunks} - Thinking chunk structure: choices[0].delta.type={type(thinking_chunk.choices[0].delta).__name__}, delta.is_thinking={getattr(thinking_chunk.choices[0].delta, 'is_thinking', 'NOT_FOUND')}"
                                    )
                                    
                                    yield thinking_chunk
                                
                                # Envoyer le texte normal si présent
                                if chunk_text:
                                    chunks_with_text += 1
                                    full_text += chunk_text
                                    
                                    UnifiedLogger.write(
                                        "AI_CORE",
                                        "STREAM_CANDIDATES",
                                        f"Chunk {total_chunks} - Texte extrait: {len(chunk_text)} caractères"
                                    )
                                    
                                    # Créer un objet compatible avec le format LiteLLM
                                    class DeltaObject:
                                        def __init__(self, content):
                                            self.content = content
                                            self.text = content
                                    
                                    class ChoiceObject:
                                        def __init__(self, delta):
                                            self.delta = delta
                                    
                                    class ChunkObject:
                                        def __init__(self, choice):
                                            self.choices = [choice]
                                    
                                    delta = DeltaObject(chunk_text)
                                    choice = ChoiceObject(delta)
                                    chunk_obj = ChunkObject(choice)
                                    
                                    yield chunk_obj
                                else:
                                    UnifiedLogger.write(
                                        "AI_CORE",
                                        "STREAM_CANDIDATES",
                                        f"Chunk {total_chunks} - Aucun texte extrait des parts"
                                    )
                            else:
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "STREAM_CANDIDATES",
                                    f"Chunk {total_chunks} - candidate.content n'est pas un dict avec 'parts'"
                                )
                        else:
                            UnifiedLogger.write(
                                "AI_CORE",
                                "STREAM_CANDIDATES",
                                f"Chunk {total_chunks} - candidate n'a pas de 'content'"
                            )
                    
                    # LOGGING DES METRICS (Usage Metadata) - après conversion
                    if "usageMetadata" in gemini_chunk:
                        chunks_with_metrics += 1
                        usage = gemini_chunk["usageMetadata"]
                        prompt_tokens = usage.get("promptTokenCount", 0)
                        candidates_tokens = usage.get("candidatesTokenCount", 0)
                        total_tokens = usage.get("totalTokenCount", 0)
                        UnifiedLogger.write(
                            "AI_CORE",
                            "METRICS",
                            f"Usage (gemini_chunk): Prompt={prompt_tokens}, Candidates={candidates_tokens}, Total={total_tokens}"
                        )
                    # Vérifier aussi dans candidates[0] si présent
                    elif "candidates" in gemini_chunk and len(gemini_chunk["candidates"]) > 0:
                        candidate = gemini_chunk["candidates"][0]
                        if isinstance(candidate, dict) and "usageMetadata" in candidate:
                            chunks_with_metrics += 1
                            usage = candidate["usageMetadata"]
                            prompt_tokens = usage.get("promptTokenCount", 0)
                            candidates_tokens = usage.get("candidatesTokenCount", 0)
                            total_tokens = usage.get("totalTokenCount", 0)
                            UnifiedLogger.write(
                                "AI_CORE",
                                "METRICS",
                                f"Usage (candidate): Prompt={prompt_tokens}, Candidates={candidates_tokens}, Total={total_tokens}"
                            )
                
                # Résumé final du stream
                UnifiedLogger.write(
                    "AI_CORE",
                    "STREAM_SUMMARY",
                    f"Résumé stream: {total_chunks} chunks reçus, {chunks_with_text} avec texte, "
                    f"{chunks_with_metrics} avec métriques, {len(full_text)} caractères totaux"
                )
                
                # NOTE: On ne renvoie plus le texte complet à la fin car il a déjà été envoyé chunk par chunk
                # Cela évite la duplication du texte dans le chat
            
            return stream_generator()
        else:
            # Mode non-streaming
            method = "generateContent"
            response = self._request_post(method, ca_request)
            
            # Convertir la réponse au format Gemini API
            gemini_response = from_generate_content_response(response)
            
            # Créer un objet compatible avec LiteLLM
            class UniversalResponseWrapper:
                def __init__(self, content, data):
                    self.content = content
                    self.data = data
                    # Compatibilité avec le format attendu
                    if "candidates" in data and len(data["candidates"]) > 0:
                        candidate = data["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            self.text = "".join(
                                part.get("text", "") 
                                for part in candidate["content"]["parts"] 
                                if "text" in part
                            )
                        else:
                            self.text = str(content)
                    else:
                        self.text = str(content)
            
            # Extraire le contenu texte
            content = ""
            if "candidates" in gemini_response and len(gemini_response["candidates"]) > 0:
                candidate = gemini_response["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    content = "".join(
                        part.get("text", "") 
                        for part in candidate["content"]["parts"] 
                        if "text" in part
                    )
            
            return UniversalResponseWrapper(content, gemini_response)
    
    def completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> Any:
        """
        Alias pour generate_content pour compatibilité avec LiteLLMProxy.
        """
        return self.generate_content(
            model=model,
            messages=messages,
            stream=stream,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            **kwargs
        )

