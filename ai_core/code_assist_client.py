"""
Client CodeAssist pour l'API Gemini avec authentification OAuth.
Utilise l'endpoint cloudcode-pa.googleapis.com comme gemini-cli.
"""

import os
import json
import requests
from typing import Optional, Dict, List, Any, Iterator, Generator
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from features.UnifiedLogger import UnifiedLogger
from ai_core.oauth_validator import load_and_validate_oauth_credentials
from ai_core.code_assist_converter import (
    to_generate_content_request,
    from_generate_content_response
)


class CodeAssistClient:
    """
    Client CodeAssist pour l'API Gemini avec OAuth.
    Utilise l'endpoint cloudcode-pa.googleapis.com comme gemini-cli.
    """
    
    BASE_ENDPOINT = "https://cloudcode-pa.googleapis.com"
    API_VERSION = "v1internal"
    
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
        
        # Pour utiliser le quota personnel (comme gemini-cli), on ne doit PAS définir project
        # Seulement utiliser project_id si explicitement fourni ET si use_personal_quota=False
        if use_personal_quota:
            # Par défaut : utiliser quota personnel (pas de project_id)
            # Même si project_id est fourni ou dans l'environnement, on l'ignore
            self.project_id = None
        else:
            # Utilisation d'un projet GCP : utiliser project_id fourni ou depuis l'environnement
            if project_id:
                self.project_id = project_id
            else:
                self.project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT_ID")
        
        self.session_id = session_id
    
    def _get_access_token(self) -> Optional[str]:
        """Récupère un access token valide (OAuth)."""
        try:
            if self._creds is None or not self._creds.valid:
                creds, error_msg = load_and_validate_oauth_credentials(self.token_path)
                if creds is None:
                    UnifiedLogger.write(
                        "AI_CORE",
                        "ERROR",
                        f"❌ Impossible de charger les credentials OAuth: {error_msg}"
                    )
                    return None
                self._creds = creds
            
            # Rafraîchir si nécessaire
            if not self._creds.valid:
                if self._creds.expired and self._creds.refresh_token:
                    self._creds.refresh(Request())
                    from ai_core.oauth_validator import save_oauth_credentials
                    save_oauth_credentials(self._creds, self.token_path)
            
            if self._creds.valid:
                return self._creds.token
            return None
        except Exception as e:
            UnifiedLogger.write(
                "AI_CORE",
                "ERROR",
                f"❌ Erreur lors de la récupération du token OAuth: {e}"
            )
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
        access_token = self._get_access_token()
        if not access_token:
            raise ValueError("Impossible d'obtenir un access token OAuth valide")
        
        url = self._get_method_url(method)
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        UnifiedLogger.write(
            "AI_CORE",
            "START",
            f"CodeAssist API: {method} (OAuth)"
        )
        
        # Log du payload complet pour diagnostic
        try:
            payload_str = json.dumps(payload, indent=2, ensure_ascii=False)
            UnifiedLogger.write(
                "AI_CORE",
                "DEBUG",
                f"Payload CodeAssist ({method}):\n{payload_str}"
            )
        except Exception as e:
            UnifiedLogger.write(
                "AI_CORE",
                "WARN",
                f"Impossible de logger le payload: {e}"
            )
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
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
        except requests.exceptions.RequestException as e:
            UnifiedLogger.write(
                "AI_CORE",
                "ERROR",
                f"❌ Erreur CodeAssist API {method}: {e}"
            )
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    UnifiedLogger.write(
                        "AI_CORE",
                        "DEBUG",
                        f"Détails erreur: {json.dumps(error_detail, indent=2)}"
                    )
                except:
                    pass
            raise
    
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
        access_token = self._get_access_token()
        if not access_token:
            raise ValueError("Impossible d'obtenir un access token OAuth valide")
        
        url = self._get_method_url(method)
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Ajouter le paramètre alt=sse pour le streaming
        params = {"alt": "sse"}
        
        UnifiedLogger.write(
            "AI_CORE",
            "START",
            f"CodeAssist API Streaming: {method} (OAuth)"
        )
        
        # Log du payload complet pour diagnostic
        try:
            payload_str = json.dumps(payload, indent=2, ensure_ascii=False)
            UnifiedLogger.write(
                "AI_CORE",
                "DEBUG",
                f"Payload CodeAssist Streaming ({method}):\n{payload_str}"
            )
        except Exception as e:
            UnifiedLogger.write(
                "AI_CORE",
                "WARN",
                f"Impossible de logger le payload: {e}"
            )
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                params=params,
                stream=True,
                timeout=300
            )
            response.raise_for_status()
            
            # Parser les chunks SSE
            buffer = ""
            for line in response.iter_lines():
                if line:
                    try:
                        line_text = line.decode('utf-8')
                        buffer += line_text + "\n"
                        
                        # Parser les chunks SSE de CodeAssist
                        # Format: "data: {...}\n\n"
                        while "\n\n" in buffer:
                            chunk_text, buffer = buffer.split("\n\n", 1)
                            
                            if chunk_text.startswith("data: "):
                                data_json = chunk_text[6:].strip()
                                if data_json:
                                    try:
                                        data = json.loads(data_json)
                                        yield data
                                    except json.JSONDecodeError as e:
                                        UnifiedLogger.write(
                                            "AI_CORE",
                                            "WARNING",
                                            f"Erreur parsing JSON chunk: {e}"
                                        )
                    except Exception as e:
                        UnifiedLogger.write(
                            "AI_CORE",
                            "WARNING",
                            f"Erreur traitement chunk streaming: {e}"
                        )
            
            UnifiedLogger.write(
                "AI_CORE",
                "SUCCESS",
                f"CodeAssist API Streaming: {method} terminé"
            )
        except requests.exceptions.RequestException as e:
            UnifiedLogger.write(
                "AI_CORE",
                "ERROR",
                f"❌ Erreur CodeAssist API Streaming {method}: {e}"
            )
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    UnifiedLogger.write(
                        "AI_CORE",
                        "DEBUG",
                        f"Détails erreur: {json.dumps(error_detail, indent=2)}"
                    )
                except:
                    pass
            raise
    
    def generate_content(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        system_instruction: Optional[str] = None,
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
        user_prompt_id = str(uuid.uuid4())
        
        # Log des outils si présents
        if tools:
            UnifiedLogger.write(
                "AI_CORE",
                "DEBUG",
                f"Outils passés à CodeAssist: {len(tools)} outils"
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
            user_prompt_id=user_prompt_id,
            project_id=self.project_id,
            session_id=self.session_id,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            system_instruction=system_instruction,
            **kwargs
        )
        
        # Vérification post-conversion
        request_data = ca_request.get("request", {})
        if tools:
            has_toolconfig = "toolConfig" in request_data
            UnifiedLogger.write(
                "AI_CORE",
                "DEBUG",
                f"Vérification post-conversion: toolConfig présent = {has_toolconfig}"
            )
            if has_toolconfig:
                toolconfig_str = json.dumps(request_data.get("toolConfig"), indent=2, ensure_ascii=False)
                UnifiedLogger.write(
                    "AI_CORE",
                    "DEBUG",
                    f"toolConfig généré:\n{toolconfig_str}"
                )
            else:
                UnifiedLogger.write(
                    "AI_CORE",
                    "ERROR",
                    "[CRITICAL] toolConfig MANQUANT après conversion!"
                )
        
        if stream:
            # Mode streaming
            method = "streamGenerateContent"
            chunks = self._request_streaming_post(method, ca_request)
            
            # Convertir les chunks au format LiteLLM
            def stream_generator():
                full_text = ""
                for chunk in chunks:
                    # Convertir chaque chunk
                    gemini_chunk = from_generate_content_response(chunk)
                    
                    # Extraire le texte du chunk
                    if "candidates" in gemini_chunk and len(gemini_chunk["candidates"]) > 0:
                        candidate = gemini_chunk["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            chunk_text = ""
                            for part in candidate["content"]["parts"]:
                                if "text" in part:
                                    chunk_text += part["text"]
                            
                            if chunk_text:
                                full_text += chunk_text
                                
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
                
                # Dernier chunk avec le texte complet
                if full_text:
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
                    
                    delta = DeltaObject(full_text)
                    choice = ChoiceObject(delta)
                    chunk_obj = ChunkObject(choice)
                    yield chunk_obj
            
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

