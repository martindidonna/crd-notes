from __future__ import annotations

from crd_notes.ai.factory import ConnectorFactory
from crd_notes.ai.prompts import get_prompt
from crd_notes.core.config import AppSettings, ProviderName
from crd_notes.core.errors import AiConnectorError


class AiService:
    def __init__(self, connector_factory: ConnectorFactory) -> None:
        self.connector_factory = connector_factory

    async def summarize(
        self,
        *,
        transcript: str,
        prompt_id: str,
        settings: AppSettings,
        provider: ProviderName | None = None,
        model: str | None = None,
    ):
        selected_provider = provider or settings.active_provider
        provider_settings = settings.providers[selected_provider]
        if not provider_settings.enabled:
            raise AiConnectorError(f"Provider {selected_provider} disabilitato.")
        if model:
            provider_settings = provider_settings.model_copy(update={"model": model})
        if not provider_settings.model:
            raise AiConnectorError(f"Modello non configurato per {selected_provider}.")

        prompt = get_prompt(prompt_id)
        connector = self.connector_factory.create(selected_provider)
        return await connector.summarize(
            settings=provider_settings,
            system_prompt=prompt.system_prompt,
            transcript=transcript,
        )

    async def complete_with_prompt(
        self,
        *,
        input_text: str,
        system_prompt: str,
        settings: AppSettings,
        provider: ProviderName | None = None,
        model: str | None = None,
    ):
        selected_provider = provider or settings.active_provider
        provider_settings = settings.providers[selected_provider]
        if not provider_settings.enabled:
            raise AiConnectorError(f"Provider {selected_provider} disabilitato.")
        if model:
            provider_settings = provider_settings.model_copy(update={"model": model})
        if not provider_settings.model:
            raise AiConnectorError(f"Modello non configurato per {selected_provider}.")

        connector = self.connector_factory.create(selected_provider)
        return await connector.summarize(
            settings=provider_settings,
            system_prompt=system_prompt,
            transcript=input_text,
        )
