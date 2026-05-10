from __future__ import annotations

import unittest
from unittest.mock import patch

from crd_notes.ai.prompts import PromptTemplate, get_prompt, get_prompts
from crd_notes.api import list_prompts
from crd_notes.chat.prompts import get_chat_prompt, get_chat_prompts, get_chat_system_prompt


class PromptsTests(unittest.TestCase):
    def test_get_prompts_loads_markdown_templates(self) -> None:
        prompts = get_prompts()

        self.assertEqual(
            set(prompts),
            {
                "riunione_tecnica",
                "requisiti",
                "dungeon_dragons",
                "sintesi_generale",
            },
        )
        self.assertEqual(prompts["riunione_tecnica"].title, "Call tecnica")
        self.assertIn("assistente senior", prompts["riunione_tecnica"].system_prompt)

    def test_get_prompt_fallbacks_to_default(self) -> None:
        prompt = get_prompt("inesistente")

        self.assertEqual(prompt.id, "sintesi_generale")
        self.assertIn("riassunto", prompt.system_prompt.lower())

    def test_list_prompts_reads_items_from_loader(self) -> None:
        fake_prompt = PromptTemplate(
            id="custom",
            title="Custom",
            description="Descrizione custom",
            system_prompt="Prompt custom",
        )

        with patch("crd_notes.api.get_prompts", return_value={"custom": fake_prompt}):
            result = list_prompts()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "custom")
        self.assertEqual(result[0].title, "Custom")
        self.assertEqual(result[0].description, "Descrizione custom")

    def test_get_chat_prompts_loads_system_prompt_template(self) -> None:
        prompts = get_chat_prompts()

        self.assertIn("chat_system", prompts)
        self.assertEqual(prompts["chat_system"].title, "Chat workspace")
        self.assertIn("risposta naturale", prompts["chat_system"].system_prompt)

    def test_get_chat_system_prompt_returns_external_template(self) -> None:
        prompt = get_chat_system_prompt()

        self.assertIn("Sei Cardinal", prompt)
        self.assertIn("le fonti sono mostrate dall'interfaccia separatamente", prompt.lower())
        self.assertEqual(get_chat_prompt("inesistente").id, "chat_system")


if __name__ == "__main__":
    unittest.main()
