from __future__ import annotations

import httpx

from crd_notes.ai.connectors.base import AiResult
from crd_notes.core.config import ProviderSettings
from crd_notes.core.errors import AiConnectorError


class OpenAICompatibleConnector:
    def __init__(self, name: str, *, require_key: bool = True, app_title: str = "crd-notes") -> None:
        self.name = name
        self.require_key = require_key
        self.app_title = app_title

    async def summarize(
        self,
        *,
        settings: ProviderSettings,
        system_prompt: str,
        transcript: str,
    ) -> AiResult:
        if self.require_key and not settings.api_key:
            raise AiConnectorError(f"Chiave API mancante per {self.name}.")

        base_url = settings.base_url.rstrip("/")
        if not base_url:
            raise AiConnectorError(f"URL base mancante per {self.name}.")

        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": "http://127.0.0.1",
            "X-Title": self.app_title,
        }
        if settings.api_key:
            headers["Authorization"] = f"Bearer {settings.api_key}"

        payload = {
            "model": settings.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Trascrizione da riassumere. Mantieni la risposta in italiano.\n\n"
                        f"{transcript}"
                    ),
                },
            ],
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.timeout_seconds)) as client:
            try:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as exc:
                raise AiConnectorError(
                    f"{self.name} ha rifiutato la richiesta.",
                    detail=exc.response.text,
                ) from exc
            except httpx.HTTPError as exc:
                raise AiConnectorError(
                    f"{self.name} non e' raggiungibile.",
                    detail=str(exc),
                ) from exc

        try:
            content = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise AiConnectorError(
                f"Risposta non valida da {self.name}.",
                detail=str(data),
            ) from exc

        return AiResult(content=content, provider=self.name, model=settings.model)
