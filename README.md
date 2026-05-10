# CRD Notes

![Open Source](https://img.shields.io/badge/Open%20Source-Yes-brightgreen)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)
![Made with PyCharm](https://img.shields.io/badge/Made%20with-PyCharm-21D789?logo=pycharm&logoColor=white)

CRD Notes is a local-first web application for turning audio or video recordings into searchable transcripts and AI-generated summaries. It runs a FastAPI server on your machine, stores data in a local SQLite database, converts media with ffmpeg, transcribes audio with faster-whisper, and can summarize transcripts through pluggable AI connectors.

The default UI is currently Italian because the original workflow targets Italian meeting notes. Project documentation and contributor-facing files are written in English.

## Features

- Upload audio or video files from the browser.
- Convert media to 16 kHz mono WAV for transcription.
- Transcribe locally with faster-whisper.
- Store transcripts, metadata, participants, and summaries in SQLite.
- Create and select workspaces so transcripts, summaries, and operational items stay grouped by context.
- Enrich generated summaries with tags, keywords, people, topics, and extended context for better retrieval.
- Review workspace intelligence with local clustering, recurring themes, people, risks, questions, and optional AI briefs.
- Download transcripts and summaries as Markdown.
- Use built-in prompt templates for meeting notes, requirements, general summaries, and custom workflows.
- Summarize with Ollama, OpenAI-compatible APIs, LM Studio, OpenRouter, or the optional GitHub Copilot bridge.

## Requirements

- Python 3.10 or newer.
- Node.js 18 or newer, only if you want to use the GitHub Copilot connector.
- ffmpeg. If a system ffmpeg is not available, `imageio-ffmpeg` is used as a fallback.
- On Windows recording, prefer a full `ffmpeg` build with `WASAPI loopback` (for example `winget install --id Gyan.FFmpeg --exact`).
- Enough local CPU/RAM for the selected Whisper model.

## Quick Start

On Windows, use the bundled starter:

```powershell
.\scripts\crd-notes-starter.ps1
```

On Linux or macOS:

```bash
chmod +x scripts/crd-notes-starter.sh
./scripts/crd-notes-starter.sh
```

The app starts at `http://127.0.0.1:8184` by default.

Manual setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
python main.py
```

On Windows PowerShell, activate the virtual environment with:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Configuration

Runtime data is stored in `data/` under the current working directory by default. That folder contains uploaded media, converted audio, logs, local configuration, API keys saved through the UI, and the SQLite database. It is intentionally ignored by git.

Environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `CRD_NOTES_HOST` | `127.0.0.1` | Bind host for the FastAPI server. |
| `CRD_NOTES_PORT` | `8184` | Bind port for the FastAPI server. |
| `CRD_NOTES_RELOAD` | `false` | Enable Uvicorn reload when set to `true`, `1`, or `yes`. |
| `CRD_NOTES_DATA_DIR` | `data` under the current working directory | Directory for local runtime data. |
| `CRD_NOTES_FFMPEG` | unset | Absolute path to `ffmpeg.exe` to force a specific binary (recommended on Windows if multiple ffmpeg builds are installed). |
| `CRD_NOTES_INSTALL_FFMPEG` | unset | Starter script on Windows tries `winget install --id Gyan.FFmpeg --exact` when `ffmpeg` is missing. |
| `CRD_NOTES_SKIP_DEPS` | unset | Starter scripts skip Python dependency refresh when set to `true`, `1`, or `yes`. |
| `CRD_NOTES_SKIP_FRONTEND` | unset | Starter scripts skip Node dependency install and frontend build when set to `true`, `1`, or `yes`. |

Copy `.env.example` if you want a local reference, but the application does not automatically load `.env` files.

## AI Providers

Provider settings are managed from the UI under `Setup > AI summary`.

| Connector | Type | Default/Typical endpoint | API key |
| --- | --- | --- | --- |
| `Ollama` | Local | `http://127.0.0.1:11434` | No |
| `LM Studio` | Local (OpenAI-compatible) | `http://127.0.0.1:1234/v1` | No |
| `OpenAI` | Hosted (OpenAI-compatible) | Provider endpoint | Yes |
| `OpenRouter` | Hosted (OpenAI-compatible) | `https://openrouter.ai/api/v1` | Yes |
| `GitHub Copilot` | Optional local Node bridge | Local bridge endpoint | Uses local Copilot login |

Connector implementation details are documented in [docs/CONNECTORS.md](docs/CONNECTORS.md).

## Project Layout

```text
crd_notes/
  ai/              AI service, prompt loader, and connectors
  conversion/      ffmpeg discovery and media conversion
  core/            settings, paths, errors, and logging
  library/         SQLite repository and library domain service
  transcription/   faster-whisper adapter
  web/             static browser UI
tests/             unit tests
scripts/           local startup helpers
docs/              architecture and extension documentation
```

## Development

Install the package in editable mode with development dependencies:

```bash
pip install -e ".[dev]"
npm install
```

Run tests:

```bash
python -m pytest
```

Run the app with reload enabled:

```bash
CRD_NOTES_RELOAD=true python main.py
```

On PowerShell:

```powershell
$env:CRD_NOTES_RELOAD = "true"
python main.py
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Frontend architecture options](docs/FRONTEND-ARCHITECTURE.md)
- [Connectors and prompt templates](docs/CONNECTORS.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

## License

CRD Notes is released under the MIT License. See [LICENSE](LICENSE).
