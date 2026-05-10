from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from crd_notes.ai.connectors.base import AiResult
from crd_notes.core.config import ProviderSettings
from crd_notes.core.errors import AiConnectorError
from crd_notes.core.paths import ROOT_DIR


class CopilotConnector:
    name = "copilot"

    async def list_models(self) -> dict[str, object]:
        data = await self._run_bridge({"action": "models"})
        models = data.get("models", [])
        if not isinstance(models, list):
            raise AiConnectorError("Copilot ha restituito un elenco modelli non valido.")
        return data

    async def summarize(
        self,
        *,
        settings: ProviderSettings,
        system_prompt: str,
        transcript: str,
    ) -> AiResult:
        data = await self._run_bridge(
            {
                "action": "summarize",
                "model": settings.model,
                "systemPrompt": system_prompt,
                "transcript": transcript,
            },
        )

        content = str(data.get("content", "")).strip()
        if not content:
            raise AiConnectorError("Copilot non ha restituito testo.")

        return AiResult(content=content, provider=self.name, model=settings.model)

    async def _run_bridge(self, data: dict[str, object]) -> dict[str, object]:
        node = shutil.which("node")
        if not node:
            raise AiConnectorError("Node.js non e' installato: il connettore Copilot richiede Node 18 o superiore.")

        bridge = ROOT_DIR / "crd_notes" / "ai" / "copilot_bridge.mjs"
        payload = json.dumps(data, ensure_ascii=False)

        process = await asyncio.create_subprocess_exec(
            node,
            str(bridge),
            cwd=str(ROOT_DIR),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate(payload.encode("utf-8"))

        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise AiConnectorError(
                "Copilot non ha completato la richiesta. Verifica di essere loggato con GitHub Copilot sul dispositivo.",
                detail=self._readable_detail(detail),
            )

        try:
            parsed = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise AiConnectorError("Risposta non valida dal bridge Copilot.") from exc

        if not isinstance(parsed, dict):
            raise AiConnectorError("Risposta non valida dal bridge Copilot.")
        return parsed

    def _readable_detail(self, detail: str) -> str | None:
        if not detail:
            return None
        if "EPERM" in detail and ".copilot" in detail:
            return "Copilot non riesce a scrivere la configurazione locale nella cartella utente."
        if "not authenticated" in detail.lower() or "authentication" in detail.lower():
            return "Accesso Copilot non trovato o non valido."
        lines = [line.strip() for line in detail.splitlines() if line.strip()]
        return lines[-1] if lines else None
