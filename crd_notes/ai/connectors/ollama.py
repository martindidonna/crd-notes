from __future__ import annotations

import httpx

from crd_notes.ai.connectors.base import AiResult
from crd_notes.core.config import ProviderSettings
from crd_notes.core.errors import AiConnectorError


class OllamaConnector:
    name = "ollama"

    async def summarize(
        self,
        *,
        settings: ProviderSettings,
        system_prompt: str,
        transcript: str,
    ) -> AiResult:
        base_url = settings.base_url.rstrip("/")
        if not base_url:
            raise AiConnectorError("URL base mancante per Ollama.")

        payload = {
            "model": settings.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript},
            ],
            "options": {"temperature": 0.2},
        }

        async with httpx.AsyncClient(timeout=180) as client:
            try:
                response = await client.post(f"{base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as exc:
                raise AiConnectorError(
                    "Ollama ha rifiutato la richiesta.",
                    detail=exc.response.text,
                ) from exc
            except httpx.HTTPError as exc:
                raise AiConnectorError(
                    "Ollama non e' raggiungibile. Verifica che il servizio sia avviato.",
                    detail=str(exc),
                ) from exc

        content = (data.get("message") or {}).get("content", "").strip()
        if not content:
            raise AiConnectorError("Ollama non ha restituito testo.")

        return AiResult(content=content, provider=self.name, model=settings.model)
