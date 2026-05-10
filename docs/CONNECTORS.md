# Connectors and Custom Behavior

CRD Notes uses a small connector interface for AI summaries. A connector receives provider settings, a system prompt, and the transcript, then returns normalized summary content.

## Connector Contract

The protocol lives in `crd_notes/ai/connectors/base.py`:

```python
from crd_notes.ai.connectors.base import AiResult
from crd_notes.core.config import ProviderSettings


class MyConnector:
    name = "my_provider"

    async def summarize(
        self,
        *,
        settings: ProviderSettings,
        system_prompt: str,
        transcript: str,
    ) -> AiResult:
        ...
```

Return:

```python
AiResult(
    content="Markdown summary",
    provider="my_provider",
    model=settings.model,
)
```

Raise `AiConnectorError` for expected provider failures so the UI receives a readable message.

## Adding a Provider

1. Create `crd_notes/ai/connectors/my_provider.py`.
2. Implement `summarize()` using the connector contract.
3. Add the provider name to `ProviderName` in `crd_notes/core/config.py`.
4. Add default provider settings in `AppSettings.providers`.
5. Register the connector in `ConnectorFactory.create()` in `crd_notes/ai/factory.py`.
6. Add provider labels, key requirements, URL requirements, and help text in `crd_notes/web/static/app.js`.
7. Add model listing support in `crd_notes/api.py` if the provider can enumerate models.
8. Add or update tests for factory dispatch, settings validation, and error behavior.

## OpenAI-Compatible Providers

If a provider supports the OpenAI chat completions API, prefer `OpenAICompatibleConnector`:

```python
from crd_notes.ai.connectors.openai_compatible import OpenAICompatibleConnector

OpenAICompatibleConnector("my_provider", require_key=True)
```

Expected endpoints:

- `GET {base_url}/models`
- `POST {base_url}/chat/completions`

The connector sends a system message with the selected prompt template and a user message containing the transcript.

## Local Providers

Ollama and LM Studio are examples of local providers:

- Ollama uses `/api/chat` and `/api/tags`.
- LM Studio uses the OpenAI-compatible connector with `require_key=False`.

Local connectors should provide clear errors when the service is not reachable.

## GitHub Copilot Bridge

The Copilot connector uses `crd_notes/ai/copilot_bridge.mjs` and the `@github/copilot-sdk` package. The Python connector starts Node as a subprocess and exchanges JSON over stdin/stdout.

The bridge supports:

- `models`: returns authentication status and available model IDs.
- `summarize`: starts a Copilot session and sends the prompt plus transcript.

This connector is optional. Users who do not install Node dependencies can still use all Python-only providers.

## Prompt Templates

Prompt templates are Markdown files in `crd_notes/ai/prompt_templates/` with front matter:

```markdown
---
id: product_review
title: Product review
description: Summarizes product feedback and action items.
---

You are a senior product analyst...
```

Rules:

- `id` must be unique.
- `title` and `description` are shown in the UI.
- The Markdown body becomes the system prompt.
- Keep templates deterministic and explicit about output structure.

The prompt loader is in `crd_notes/ai/prompts.py`. Missing prompt IDs fall back to `sintesi_generale`.

## Custom Workflows

New behavior should usually be added in one of these places:

- New summary style: add a prompt template.
- New model provider: add an AI connector.
- New transcription behavior: extend `WhisperTranscriber` settings and expose them through `AppSettings`.
- New import/export format: add API routes in `crd_notes/api.py` and keep file generation outside the repository layer.

Keep provider-specific logic out of `AiService`; it should remain a dispatcher that validates settings, resolves prompts, and calls connectors.
