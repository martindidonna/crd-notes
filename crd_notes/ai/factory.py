from __future__ import annotations

from crd_notes.ai.connectors.base import AiConnector
from crd_notes.ai.connectors.copilot import CopilotConnector
from crd_notes.ai.connectors.ollama import OllamaConnector
from crd_notes.ai.connectors.openai_compatible import OpenAICompatibleConnector
from crd_notes.core.config import ProviderName


class ConnectorFactory:
    def create(self, provider: ProviderName) -> AiConnector:
        if provider == "openai":
            return OpenAICompatibleConnector("openai")
        if provider == "openrouter":
            return OpenAICompatibleConnector("openrouter")
        if provider == "lmstudio":
            return OpenAICompatibleConnector("lmstudio", require_key=False)
        if provider == "ollama":
            return OllamaConnector()
        if provider == "copilot":
            return CopilotConnector()
        raise ValueError(f"Provider non supportato: {provider}")
