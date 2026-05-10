# Security Policy

CRD Notes is a local-first application, but it still handles sensitive data: recordings, transcripts, summaries, and provider API keys.

## Supported Versions

The project is currently pre-1.0. Security fixes are applied to the main development line.

## Reporting a Vulnerability

Please report security issues privately to the maintainers instead of opening a public issue. Include:

- Affected version or commit.
- Steps to reproduce.
- Impact and affected data.
- Any relevant logs with secrets removed.

If no private channel has been published yet, create a minimal public issue asking for a security contact without disclosing details.

## Local Data

By default, runtime data is stored in `data/`:

- Uploaded source media.
- Converted WAV files.
- `crd_notes.sqlite3`.
- `config.json`, which may contain API keys.
- Logs.

This directory is ignored by git. Do not upload it to issue trackers or paste it into public discussions.

## Network Exposure

The server binds to `127.0.0.1` by default. Binding to `0.0.0.0` exposes the application to your local network and should only be done behind trusted network controls.

## Provider Secrets

API keys are stored in the local configuration file when entered through the UI. Treat `data/config.json` as sensitive. Do not commit `.env`, `data/`, logs, database files, or screenshots that reveal keys.
