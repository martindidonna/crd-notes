# Contributing

Thanks for taking the time to improve CRD Notes. This project is designed to stay small, local-first, and easy to run from source.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
npm install
python main.py
```

On Windows PowerShell:

```powershell
.\scripts\crd-notes-starter.ps1
```

## Before Opening a Pull Request

Run:

```bash
python -m pytest
```

For changes that touch the Copilot connector, also run:

```bash
npm install
```

Then test the affected workflow manually in the browser.

## Code Guidelines

- Keep the application local-first. Do not add external services to the critical path unless they are optional connectors.
- Keep provider-specific logic inside connector modules.
- Use `CrdNotesError` subclasses for expected user-facing failures.
- Store runtime data under the configured data directory, not in the repository tree outside `data/`.
- Add focused tests for repository migrations, settings behavior, prompt loading, and connector dispatch.
- Avoid committing generated data, uploaded media, local logs, `.venv`, or `node_modules`.

## Documentation Guidelines

Update documentation when changing:

- Supported providers or connector behavior.
- Runtime environment variables.
- SQLite schema or data storage behavior.
- Startup commands or required dependencies.
- Prompt template format.

## Commit Style

Use concise, imperative commit messages:

```text
Add OpenAI-compatible provider model discovery
Fix upload validation for extension-only media files
Document prompt template front matter
```
