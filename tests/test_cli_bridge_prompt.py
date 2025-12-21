import unittest


from ai_core.prompt_builders import build_cli_prompt, sanitize_system_instruction_for_cli, build_cli_system_md


class TestCliBridgePrompt(unittest.TestCase):
    def test_sanitize_system_instruction_removes_tool_manual(self):
        raw = (
            "IDENTITÉ:\n"
            "Tu es AiModding.\n"
            "\n--- 🛠️ MANUEL DES OUTILS AUTORISÉS ---\n"
            "Utilise !native_tool pour appeler un outil.\n"
            "\n--- AUTRE ---\n"
            "Fin.\n"
        )
        cleaned = sanitize_system_instruction_for_cli(raw)
        self.assertIn("IDENTITÉ", cleaned)
        self.assertNotIn("MANUEL DES OUTILS", cleaned)
        self.assertNotIn("native_tool", cleaned.lower())

    def test_build_cli_system_md_has_guardrails(self):
        system_md = build_cli_system_md("IDENTITÉ:\nTu es AiModding.")
        self.assertIn("assistant conversationnel", system_md.lower())
        self.assertIn("Réponds en français".lower(), system_md.lower())

    def test_build_cli_prompt_structure_and_truncation(self):
        history = [
            {"role": "user", "content": "bonjour"},
            {"role": "assistant", "content": "salut"},
        ]
        comps = {
            "arch": "ARCH" * 3000,  # long
            "tree": "TREE" * 3000,  # long
            "ltm": "LTM" * 2000,
        }
        prompt, meta = build_cli_prompt(
            message="liste tes commandes",
            rag_context="RAG" * 5000,
            history=history,
            cache_components=comps,
            max_history_turns=1,
            limits={"total": 5000, "arch": 1000, "tree": 1000, "ltm": 500, "rag": 1200, "history": 300, "message": 500},
        )

        self.assertIn("=== CONTEXTE PROJET", prompt)
        self.assertIn("=== 📂 RAG CONTEXT", prompt)
        self.assertIn("=== HISTORIQUE", prompt)
        self.assertIn("=== MESSAGE ACTUEL", prompt)
        self.assertTrue(meta.total_chars <= 5000)
        # Au moins un bloc devrait être tronqué vu les limites
        self.assertTrue(any(meta.truncated.values()))


if __name__ == "__main__":
    unittest.main()


