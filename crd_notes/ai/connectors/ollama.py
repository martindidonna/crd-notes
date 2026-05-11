from __future__ import annotations

import json
from collections.abc import AsyncIterator

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

        timeout = httpx.Timeout(settings.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(f"{base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
            except httpx.TimeoutException as exc:
                raise AiConnectorError(
                    "Ollama ha superato il tempo massimo per generare il riassunto.",
                    detail=(
                        f"Timeout dopo {settings.timeout_seconds} secondi. "
                        "Prova un modello piu' piccolo, aumenta il timeout del provider "
                        "o riduci la trascrizione da riassumere."
                    ),
                ) from exc
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

    async def stream_summarize(
        self,
        *,
        settings: ProviderSettings,
        system_prompt: str,
        transcript: str,
    ) -> AsyncIterator[str]:
        base_url = settings.base_url.rstrip("/")
        if not base_url:
            raise AiConnectorError("URL base mancante per Ollama.")

        payload = {
            "model": settings.model,
            "stream": True,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript},
            ],
            "options": {"temperature": 0.2},
        }

        timeout = httpx.Timeout(settings.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream("POST", f"{base_url}/api/chat", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        content = (data.get("message") or {}).get("content", "")
                        if content:
                            yield content
            except httpx.TimeoutException as exc:
                raise AiConnectorError(
                    "Ollama ha superato il tempo massimo per generare il riassunto.",
                    detail=(
                        f"Timeout dopo {settings.timeout_seconds} secondi. "
                        "Prova un modello piu' piccolo, aumenta il timeout del provider "
                        "o riduci la trascrizione da riassumere."
                    ),
                ) from exc
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
            except json.JSONDecodeError as exc:
                raise AiConnectorError("Ollama ha restituito uno stream non valido.") from exc
