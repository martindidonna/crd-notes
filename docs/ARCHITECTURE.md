# Architecture

CRD Notes is intentionally small: a local FastAPI backend serves a static browser UI and coordinates media conversion, transcription, local persistence, and optional AI summaries.

## Runtime Flow

1. The browser uploads an audio or video file to `POST /api/jobs`.
2. The API validates the media type or extension and writes the original file into `data/inbox/`.
3. `JobRunner` stores a queued job in SQLite and processes jobs from an in-process thread queue.
4. `MediaConverter` uses ffmpeg to create a 16 kHz mono WAV file in `data/audio/`.
5. `WhisperTranscriber` loads a faster-whisper model and creates the transcript.
6. `LibraryService` stores the transcript and metadata as a library entry.
7. If summary generation is requested, `AiService` selects the configured connector and stores the generated summary.
8. Summary metadata extraction adds tags, keywords, people, topics, and extended context for archive retrieval.
9. Workspace intelligence aggregates local metadata, operations, decisions, risks, and TF-IDF clusters for the selected workspace.
10. The browser polls `GET /api/jobs/{job_id}` and refreshes the library when processing completes.

Uploads include the currently selected workspace. Existing or unassigned entries belong to the default `Generico` workspace so every transcript always has a context.

## Main Components

| Component | Location | Responsibility |
| --- | --- | --- |
| FastAPI app | `crd_notes/app.py` | Application factory, static UI, startup lifecycle, error handling. |
| API routes | `crd_notes/api.py` | HTTP endpoints, upload validation, provider model discovery. |
| Job runner | `crd_notes/jobs.py` | Background processing and progress updates. |
| Repository | `crd_notes/library/repository.py` | SQLite schema, migrations, persistence. |
| Library service | `crd_notes/library/service.py` | Domain-level creation of entries and summaries. |
| Workspace intelligence | `crd_notes/library/workspace_intelligence.py` | Local workspace aggregation, theme scoring, lightweight clustering, and AI brief input. |
| Conversion | `crd_notes/conversion/` | ffmpeg lookup and WAV conversion. |
| Transcription | `crd_notes/transcription/` | faster-whisper integration. |
| AI service | `crd_notes/ai/service.py` | Prompt selection and connector dispatch. |
| Connectors | `crd_notes/ai/connectors/` | Provider-specific summary implementations. |
| Web UI | `crd_notes/web/` | Static HTML, CSS, and JavaScript client. |

## Data Model

SQLite is stored at `data/crd_notes.sqlite3` by default.

Tables:

- `workspaces`: local contexts used to group related transcripts and future shared knowledge.
- `entries`: transcript metadata and transcript text.
- `summaries`: AI summary outputs linked to entries.
- `summary_metadata`: AI-generated tags, keywords, people, topics, and context linked to summaries.
- `operation_items`: actions, decisions, risks, and questions extracted from summaries.
- `jobs`: queued, running, completed, and failed processing jobs.

The repository applies lightweight migrations at startup. New schema changes should be backward compatible and covered by tests using temporary SQLite files.

## Configuration

`SettingsStore` reads and writes `data/config.json` under the current working directory by default. It stores Whisper options, the active prompt, the active provider, and provider-specific settings. Treat this file as local state because it may contain API keys.

The data directory can be moved with `CRD_NOTES_DATA_DIR`. Host, port, and reload behavior can be configured with `CRD_NOTES_HOST`, `CRD_NOTES_PORT`, and `CRD_NOTES_RELOAD`.

## Error Handling

Domain errors inherit from `CrdNotesError`. The FastAPI exception handler returns them as user-facing JSON with HTTP 400:

```json
{
  "message": "Human-readable error",
  "detail": "Optional technical detail"
}
```

Unexpected job errors are caught in `JobRunner`, logged, and persisted on the job record so the UI can surface them.

## Extension Points

- Add prompt templates in `crd_notes/ai/prompt_templates/`.
- Add AI connectors in `crd_notes/ai/connectors/`.
- Add provider settings in `crd_notes/core/config.py`.
- Add frontend provider metadata in `crd_notes/web/static/app.js`.

For connector details, see [CONNECTORS.md](CONNECTORS.md).
