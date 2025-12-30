#!/usr/bin/env python3
"""
Script de test automatisé pour la boucle agentique CodeAssist.

Ce script teste :
1. La détection des FunctionCallObject
2. L'exécution des tool calls
3. L'injection dans le Shadow History
4. La continuation du stream avec le même session_id
5. Le Circuit Breaker

Usage:
    python scripts/test_boucle_agentique.py
"""

import sys
import os
import time
import json
import queue
import threading
from pathlib import Path

# Ajouter le répertoire racine au path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from worker.core import Worker, AgentState, CircuitBreakerException
from ai_core.code_assist_client import FunctionCallObject
from config.logs import get_logger

log = get_logger("test.boucle_agentique")


class TestResult:
    """Résultat d'un test."""
    def __init__(self, name, passed, message=""):
        self.name = name
        self.passed = passed
        self.message = message
        self.timestamp = time.time()


class BoucleAgentiqueTester:
    """Testeur automatisé pour la boucle agentique."""
    
    def __init__(self):
        self.task_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.results = []
        self.logs = []
    
    def setup(self):
        """Initialise le worker pour les tests."""
        log.info("🔧 Initialisation du worker...")
        self.worker = Worker(self.task_queue, self.response_queue, self.stop_event)
        self.worker.start()
        time.sleep(2)  # Attendre que le worker soit prêt
        log.info("✅ Worker initialisé")
    
    def teardown(self):
        """Nettoie après les tests."""
        log.info("🧹 Nettoyage...")
        if self.worker:
            self.stop_event.set()
            self.worker.join(timeout=5)
        log.info("✅ Nettoyage terminé")
    
    def log_message(self, message):
        """Enregistre un message de log."""
        self.logs.append(f"[{time.strftime('%H:%M:%S')}] {message}")
        log.info(message)
    
    def assert_test(self, name, condition, message=""):
        """Assertion pour un test."""
        result = TestResult(name, condition, message)
        self.results.append(result)
        status = "✅ PASS" if condition else "❌ FAIL"
        self.log_message(f"{status}: {name} - {message}")
        return condition
    
    def test_1_detection_function_call(self):
        """Test 1: Détection d'un FunctionCallObject."""
        self.log_message("\n" + "="*60)
        self.log_message("TEST 1: Détection FunctionCallObject")
        self.log_message("="*60)
        
        # Créer un FunctionCallObject de test
        test_call = FunctionCallObject(
            name="lire_fichier",
            args={"chemin": "worker/core.py"},
            call_id="test-123",
            thought_signature="test-signature"
        )
        
        # Vérifier que l'objet est bien créé
        passed = self.assert_test(
            "FunctionCallObject créé",
            isinstance(test_call, FunctionCallObject),
            f"Type: {type(test_call)}"
        )
        
        # Vérifier les attributs
        passed = passed and self.assert_test(
            "Attribut 'name' présent",
            hasattr(test_call, 'name') and test_call.name == "lire_fichier",
            f"name={test_call.name}"
        )
        
        passed = passed and self.assert_test(
            "Attribut 'args' présent",
            hasattr(test_call, 'args') and test_call.args == {"chemin": "worker/core.py"},
            f"args={test_call.args}"
        )
        
        passed = passed and self.assert_test(
            "Attribut 'id' présent",
            hasattr(test_call, 'id') and test_call.id == "test-123",
            f"id={test_call.id}"
        )
        
        return passed
    
    def test_2_circuit_breaker(self):
        """Test 2: Circuit Breaker."""
        self.log_message("\n" + "="*60)
        self.log_message("TEST 2: Circuit Breaker")
        self.log_message("="*60)
        
        if not self.worker:
            self.log_message("⚠️ Worker non initialisé, skip du test")
            return False
        
        # Réinitialiser le compteur
        self.worker._tool_call_count = 0
        self.worker._recent_tool_calls = []
        
        # Test 1: Vérifier que le Circuit Breaker permet les appels normaux
        try:
            self.worker._check_circuit_breaker("lire_fichier")
            passed1 = self.assert_test(
                "Circuit Breaker permet appels normaux",
                True,
                "Pas d'exception levée"
            )
        except CircuitBreakerException:
            passed1 = self.assert_test(
                "Circuit Breaker permet appels normaux",
                False,
                "Exception levée incorrectement"
            )
        
        # Test 2: Vérifier la limite d'itérations
        self.worker._tool_call_count = 14  # Juste en dessous de la limite
        try:
            self.worker._check_circuit_breaker("lire_fichier")
            passed2 = self.assert_test(
                "Circuit Breaker à la limite",
                True,
                "Pas d'exception à 14 appels"
            )
        except CircuitBreakerException:
            passed2 = self.assert_test(
                "Circuit Breaker à la limite",
                False,
                "Exception levée trop tôt"
            )
        
        # Test 3: Vérifier que la limite est atteinte
        self.worker._tool_call_count = 15  # À la limite
        try:
            self.worker._check_circuit_breaker("lire_fichier")
            passed3 = self.assert_test(
                "Circuit Breaker bloque à la limite",
                False,
                "Exception non levée à 15 appels"
            )
        except CircuitBreakerException:
            passed3 = self.assert_test(
                "Circuit Breaker bloque à la limite",
                True,
                "Exception levée correctement"
            )
        
        # Test 4: Vérifier la détection de répétitions
        self.worker._tool_call_count = 0
        self.worker._recent_tool_calls = ["lire_fichier", "lire_fichier"]
        try:
            self.worker._check_circuit_breaker("lire_fichier")  # 3ème fois
            passed4 = self.assert_test(
                "Circuit Breaker détecte répétitions",
                False,
                "Exception non levée pour 3 répétitions"
            )
        except CircuitBreakerException:
            passed4 = self.assert_test(
                "Circuit Breaker détecte répétitions",
                True,
                "Exception levée correctement pour 3 répétitions"
            )
        
        return passed1 and passed2 and passed3 and passed4
    
    def test_3_shadow_history_initialization(self):
        """Test 3: Initialisation du Shadow History."""
        self.log_message("\n" + "="*60)
        self.log_message("TEST 3: Initialisation Shadow History")
        self.log_message("="*60)
        
        if not self.worker:
            self.log_message("⚠️ Worker non initialisé, skip du test")
            return False
        
        # Réinitialiser
        self.worker._shadow_history = []
        self.worker._current_session_id = None
        
        # Simuler un nouveau message
        payload = {"message": "Test message"}
        self.worker._handle_chat_stream(payload)
        
        # Attendre un peu pour que le traitement se fasse
        time.sleep(1)
        
        # Vérifier que le Shadow History contient le message utilisateur
        passed = self.assert_test(
            "Shadow History initialisé avec message user",
            len(self.worker._shadow_history) > 0,
            f"Shadow History length: {len(self.worker._shadow_history)}"
        )
        
        if passed and len(self.worker._shadow_history) > 0:
            first_msg = self.worker._shadow_history[0]
            passed = passed and self.assert_test(
                "Premier message est 'user'",
                first_msg.get("role") == "user",
                f"Role: {first_msg.get('role')}"
            )
        
        return passed
    
    def test_4_inject_function_response(self):
        """Test 4: Injection dans le Shadow History."""
        self.log_message("\n" + "="*60)
        self.log_message("TEST 4: Injection Function Response")
        self.log_message("="*60)
        
        if not self.worker:
            self.log_message("⚠️ Worker non initialisé, skip du test")
            return False
        
        # Réinitialiser
        self.worker._shadow_history = []
        
        # Créer un FunctionCallObject de test
        test_call = FunctionCallObject(
            name="lire_fichier",
            args={"chemin": "worker/core.py"},
            call_id="test-456",
            thought_signature="test-sig"
        )
        
        # Créer un function_response de test
        test_response = {
            "name": "lire_fichier",
            "response": {"result": "Contenu du fichier"},
            "id": "test-456"
        }
        
        # Injecter
        initial_length = len(self.worker._shadow_history)
        self.worker._inject_function_response(test_call, test_response)
        
        # Vérifier que 2 messages ont été ajoutés (functionCall + functionResponse)
        passed = self.assert_test(
            "2 messages ajoutés au Shadow History",
            len(self.worker._shadow_history) == initial_length + 2,
            f"Length: {len(self.worker._shadow_history)} (attendu: {initial_length + 2})"
        )
        
        if passed and len(self.worker._shadow_history) >= 2:
            # Vérifier le format du functionCall
            function_call_msg = self.worker._shadow_history[-2]
            passed = passed and self.assert_test(
                "FunctionCall a role='model'",
                function_call_msg.get("role") == "model",
                f"Role: {function_call_msg.get('role')}"
            )
            
            # Vérifier le format du functionResponse
            function_response_msg = self.worker._shadow_history[-1]
            passed = passed and self.assert_test(
                "FunctionResponse a role='function'",
                function_response_msg.get("role") == "function",
                f"Role: {function_response_msg.get('role')}"
            )
        
        return passed
    
    def test_5_session_id_stability(self):
        """Test 5: Stabilité du session_id."""
        self.log_message("\n" + "="*60)
        self.log_message("TEST 5: Stabilité Session ID")
        self.log_message("="*60)
        
        if not self.worker:
            self.log_message("⚠️ Worker non initialisé, skip du test")
            return False
        
        # Réinitialiser
        self.worker._current_session_id = None
        
        # Simuler un premier message
        payload1 = {"message": "Premier message"}
        self.worker._handle_chat_stream(payload1)
        time.sleep(0.5)
        
        session_id_1 = self.worker._current_session_id
        
        # Vérifier qu'un session_id a été généré
        passed = self.assert_test(
            "Session ID généré",
            session_id_1 is not None,
            f"Session ID: {session_id_1}"
        )
        
        # Simuler un deuxième message (continuation)
        payload2 = {"message": "Deuxième message", "is_continuation": True}
        self.worker._handle_chat_stream(payload2)
        time.sleep(0.5)
        
        session_id_2 = self.worker._current_session_id
        
        # Vérifier que le session_id est stable
        passed = passed and self.assert_test(
            "Session ID stable entre messages",
            session_id_1 == session_id_2,
            f"ID1: {session_id_1}, ID2: {session_id_2}"
        )
        
        return passed
    
    def test_6_agent_state_transitions(self):
        """Test 6: Transitions d'état de l'agent."""
        self.log_message("\n" + "="*60)
        self.log_message("TEST 6: Transitions d'État Agent")
        self.log_message("="*60)
        
        if not self.worker:
            self.log_message("⚠️ Worker non initialisé, skip du test")
            return False
        
        # Test initial: IDLE
        self.worker.agent_state = AgentState.IDLE
        passed = self.assert_test(
            "État initial IDLE",
            self.worker.agent_state == AgentState.IDLE,
            f"État: {self.worker.agent_state}"
        )
        
        # Simuler le début d'un stream
        payload = {"message": "Test"}
        self.worker._handle_chat_stream(payload)
        time.sleep(0.5)
        
        # Vérifier que l'état est passé à GENERATING
        passed = passed and self.assert_test(
            "État passe à GENERATING",
            self.worker.agent_state == AgentState.GENERATING,
            f"État: {self.worker.agent_state}"
        )
        
        return passed
    
    def run_all_tests(self):
        """Exécute tous les tests."""
        self.log_message("\n" + "="*60)
        self.log_message("🚀 DÉMARRAGE DES TESTS - BOUCLE AGENTIQUE")
        self.log_message("="*60)
        
        try:
            self.setup()
            
            # Exécuter les tests
            tests = [
                ("Détection FunctionCall", self.test_1_detection_function_call),
                ("Circuit Breaker", self.test_2_circuit_breaker),
                ("Initialisation Shadow History", self.test_3_shadow_history_initialization),
                ("Injection Function Response", self.test_4_inject_function_response),
                ("Stabilité Session ID", self.test_5_session_id_stability),
                ("Transitions d'État", self.test_6_agent_state_transitions),
            ]
            
            results_summary = []
            for test_name, test_func in tests:
                try:
                    result = test_func()
                    results_summary.append((test_name, result))
                except Exception as e:
                    self.log_message(f"❌ ERREUR dans {test_name}: {e}")
                    results_summary.append((test_name, False))
            
            # Afficher le résumé
            self.log_message("\n" + "="*60)
            self.log_message("📊 RÉSUMÉ DES TESTS")
            self.log_message("="*60)
            
            passed_count = sum(1 for _, result in results_summary if result)
            total_count = len(results_summary)
            
            for test_name, result in results_summary:
                status = "✅ PASS" if result else "❌ FAIL"
                self.log_message(f"{status}: {test_name}")
            
            self.log_message(f"\nTotal: {passed_count}/{total_count} tests réussis")
            
            if passed_count == total_count:
                self.log_message("🎉 TOUS LES TESTS SONT PASSÉS !")
                return True
            else:
                self.log_message(f"⚠️ {total_count - passed_count} test(s) ont échoué")
                return False
                
        except Exception as e:
            self.log_message(f"❌ ERREUR CRITIQUE: {e}")
            import traceback
            self.log_message(traceback.format_exc())
            return False
        finally:
            self.teardown()
    
    def save_report(self, filename="test_boucle_agentique_report.json"):
        """Sauvegarde un rapport des tests."""
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_tests": len(self.results),
            "passed": sum(1 for r in self.results if r.passed),
            "failed": sum(1 for r in self.results if not r.passed),
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "message": r.message,
                    "timestamp": r.timestamp
                }
                for r in self.results
            ],
            "logs": self.logs
        }
        
        report_path = root_dir / filename
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        self.log_message(f"📄 Rapport sauvegardé: {report_path}")


if __name__ == "__main__":
    tester = BoucleAgentiqueTester()
    success = tester.run_all_tests()
    tester.save_report()
    
    sys.exit(0 if success else 1)
