"""
Module Shadow Workspace : validation du code généré avant présentation.
Alternative légère au LSP complet.
"""

import os
import logging
import ast
import subprocess
from typing import Tuple, List, Optional
from config import get_logger
from features.Decorators import trace_action

log = get_logger("features.context.shadow_workspace")


class ShadowWorkspace:
    """
    Workspace fantôme pour validation du code généré.
    
    Valide syntaxiquement et sémantiquement le code avant présentation.
    """
    
    def __init__(self, use_linter: bool = True):
        """
        Args:
            use_linter: Si True, utilise un linter externe (ruff/flake8)
        """
        self.use_linter = use_linter
        self.linter_available = self._check_linter_available()
    
    def _check_linter_available(self) -> bool:
        """Vérifie si un linter est disponible."""
        if not self.use_linter:
            return False
        
        # Vérifier ruff (préféré)
        try:
            result = subprocess.run(['ruff', '--version'], 
                                  capture_output=True, 
                                  timeout=2)
            if result.returncode == 0:
                log.info("✅ Ruff disponible pour validation")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Vérifier flake8 (fallback)
        try:
            result = subprocess.run(['flake8', '--version'], 
                                  capture_output=True, 
                                  timeout=2)
            if result.returncode == 0:
                log.info("✅ Flake8 disponible pour validation")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        log.warning("Aucun linter disponible (ruff/flake8). Validation basique uniquement.")
        return False
    
    @trace_action(source="shadow_workspace")
    def validate_syntax(self, code: str, filename: str = "temp.py") -> Tuple[bool, List[str]]:
        """
        Valide la syntaxe Python du code.
        
        Args:
            code: Code à valider
            filename: Nom du fichier (pour messages d'erreur)
        
        Returns:
            Tuple (is_valid, errors)
        """
        errors = []
        
        # Validation AST
        try:
            ast.parse(code, filename=filename)
        except SyntaxError as e:
            errors.append(f"SyntaxError ligne {e.lineno}: {e.msg}")
            return False, errors
        except Exception as e:
            errors.append(f"Erreur parsing: {e}")
            return False, errors
        
        # Validation linter si disponible
        if self.linter_available:
            linter_errors = self._run_linter(code, filename)
            errors.extend(linter_errors)
        
        return len(errors) == 0, errors
    
    def _run_linter(self, code: str, filename: str) -> List[str]:
        """Exécute le linter sur le code."""
        errors = []
        
        # Écrire le code dans un fichier temporaire
        temp_file = None
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # Essayer ruff d'abord
            try:
                result = subprocess.run(
                    ['ruff', 'check', temp_file],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode != 0:
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            errors.append(f"Ruff: {line}")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                # Essayer flake8
                try:
                    result = subprocess.run(
                        ['flake8', temp_file],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode != 0:
                        for line in result.stdout.split('\n'):
                            if line.strip():
                                errors.append(f"Flake8: {line}")
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
        
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass
        
        return errors
    
    @trace_action(source="shadow_workspace")
    def validate_and_correct(self, code: str, filename: str = "temp.py", 
                            max_iterations: int = 3) -> Tuple[str, List[str]]:
        """
        Valide le code et retourne les erreurs pour auto-correction.
        
        Args:
            code: Code à valider
            filename: Nom du fichier
            max_iterations: Nombre maximum d'itérations de correction
        
        Returns:
            Tuple (code, errors) - Le code peut être modifié si auto-correction activée
        """
        is_valid, errors = self.validate_syntax(code, filename)
        
        if is_valid:
            return code, []
        
        return code, errors
    
    @trace_action(source="shadow_workspace")
    def create_correction_prompt(self, code: str, errors: List[str]) -> str:
        """
        Crée un prompt pour corriger le code basé sur les erreurs.
        
        Args:
            code: Code avec erreurs
            errors: Liste des erreurs détectées
        
        Returns:
            Prompt pour l'IA
        """
        errors_text = "\n".join([f"- {e}" for e in errors])
        
        prompt = f"""Le code suivant contient des erreurs. Corrige-les.

Code:
```python
{code}
```

Erreurs détectées:
{errors_text}

Corrige le code en conservant la logique originale."""
        
        return prompt


# Instance globale
_shadow_workspace_instance: Optional[ShadowWorkspace] = None

def get_shadow_workspace(use_linter: bool = True) -> ShadowWorkspace:
    """Retourne l'instance singleton du Shadow Workspace."""
    global _shadow_workspace_instance
    if _shadow_workspace_instance is None:
        _shadow_workspace_instance = ShadowWorkspace(use_linter)
    return _shadow_workspace_instance

