from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from crd_notes.core.config import ProviderSettings


@dataclass(frozen=True)
class AiResult:
    content: str
    provider: str
    model: str


class AiConnector(Protocol):
    name: str

    async def summarize(
        self,
        *,
        settings: ProviderSettings,
        system_prompt: str,
        transcript: str,
    ) -> AiResult:
        ...
