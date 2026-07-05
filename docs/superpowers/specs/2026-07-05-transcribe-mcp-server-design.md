# Transcribe MCP Server — Design

## Purpose

Build an MCP (Model Context Protocol) server that lets an LLM agent drive GovTech's
Transcribe service (https://www.transcribe.gov.sg/) — uploading audio, running
speech-to-text transcriptions, and working with the resulting transcripts
(summaries, minutes, sections, notes, chat-based Q&A) — without the user
hand-operating the web portal or Postman collection.

Source material reviewed: `GvtReferences/Transcribe API Documentation.pdf` and
`GvtReferences/stt-core-user.postman_collection.json`.

## API Summary

- REST API over HTTPS only. Versioned via an `Accept: version=X.X` request header
  (default `3.0`).
- Auth: obtain a JWT bearer token (12h expiry) via either an OTP (10 min,
  one-time, requires org email domain whitelisting) or an API key (90 days,
  reusable). The JWT is renewable via `POST /auth/tokens/renew` before expiry.
- Resource hierarchy: **Workspace** (access-control container) → **Project**
  (exactly one audio file + sensitivity/classification metadata) →
  **Transcription** (a job run against an engine, e.g. Google STT, with optional
  speaker diarization).
- Typical flow: create workspace → create project (upload audio) → fetch engine
  options → create transcription → poll status (`In Queue` → `In Progress` →
  `Success`/`Fail`, auto-retried up to 3x server-side) → download transcript.
- Additional features present in the API: Summarization (GPT-4, async
  generate/poll/download), Minutes, Sections, Notes, Chat (RAG-style Q&A over a
  transcript), Suggested Queries, Live Transcription (WebRTC signaling, contact
  required), Usage/billing.

## Scope

**In scope (v1):**
- Metadata: engine options lookup
- Workspaces: list, get, create
- Projects: list, get, create (with local audio file upload), delete
- Transcriptions: list, get, create, delete, transcript download (raw/uf/latest)
- Summaries: generate, get, download
- Sections: get, update
- Minutes: generate, get, download
- Notes: get, append
- Chats: list, create, add message, get, download, delete

**Explicitly out of scope (v1):**
- Live Transcription (requires real-time WebRTC audio streaming — doesn't fit a
  synchronous MCP tool-call model)
- Workspace user/role management (add/remove/update users)
- Bulk project operations (duplicate, move, bulk delete)
- Audio download variants (normalised/compressed) — only transcript downloads
  are needed
- Suggested Queries
- Usage/billing endpoints

## Architecture

Python MCP server built with FastMCP.

```
transcribemcp/
  server.py          # FastMCP server entrypoint, tool registration
  auth.py            # API key -> JWT exchange, auto-renewal
  client.py          # httpx-based API client (base URL, version header, error handling)
  config.py          # env var loading
  tools/
    metadata.py
    workspaces.py
    projects.py
    transcriptions.py
    summaries.py
    sections.py
    minutes.py
    notes.py
    chats.py
tests/
  ...
pyproject.toml
```

### Auth

`TRANSCRIBE_API_KEY` (a 90-day API key, obtained by the user out-of-band via the
Transcribe web portal or OTP flow) is required at startup via env var. The
server is not responsible for the OTP/API-key acquisition flow — no auth tools
are exposed to the LLM.

On first API call, `auth.py` exchanges the API key for a JWT via
`POST /auth/tokens`, caches it in memory, and transparently renews it via
`POST /auth/tokens/renew` before the 12h expiry. If renewal fails (e.g. server
was idle past expiry), it re-exchanges using the API key. This is invisible to
the calling agent.

### Config (env vars)

- `TRANSCRIBE_API_KEY` (required)
- `TRANSCRIBE_BASE_URL` (default `https://core.transcribe.gov.sg`)
- `TRANSCRIBE_API_VERSION` (default `3.0`)

### Audio input

`create_project` takes a local filesystem path (`audio_path`) and reads +
uploads the file as multipart/form-data. Base64 encoding was considered and
rejected — it would bloat tool-call payloads for anything beyond a few MB,
which is a normal size for transcription audio.

### Polling model

Transcription/summary/minutes generation is asynchronous on Transcribe's side.
Rather than having tools block internally with long polling loops (risking
tool-call timeouts), each `get_*` tool (`get_transcription`, `get_summary`,
`get_minutes`) simply returns the current status. The calling agent re-invokes
the tool to poll — no internal wait/retry loop.

### Error handling

The API client wraps HTTP errors into tool-facing errors that surface
Transcribe's own error body (e.g. `403: Insufficient permissions`, `422:
Invalid filter fields`) rather than a raw stack trace. A 401 triggers exactly
one automatic re-auth-and-retry (covers the case where the cached JWT expired
earlier than expected); all other 4xx/5xx responses are surfaced as-is with no
speculative retry logic.

### Tool list

**Metadata**
- `get_engines(type: "batch" | "live")`

**Workspaces**
- `list_workspaces(...)`
- `get_workspace(workspace_id)`
- `create_workspace(name)`

**Projects**
- `list_projects(...)`
- `get_project(project_id)`
- `create_project(name, workspace_id, audio_path, sensitivity, classification, languages?, tags?)`
- `delete_project(project_id)`

**Transcriptions**
- `list_transcriptions(...)`
- `get_transcription(transcription_id)`
- `create_transcription(project_id, engine_options, has_diarization=False)`
- `delete_transcription(transcription_id)`
- `download_transcript(transcription_id, variant: "raw" | "uf" | "latest")`

**Summaries**
- `generate_summary(transcription_id, prompt)`
- `get_summary(transcription_id)`
- `download_summary(transcription_id)`

**Sections**
- `get_sections(transcription_id)`
- `update_sections(transcription_id, sections)`

**Minutes**
- `generate_minutes(transcription_id)`
- `get_minutes(transcription_id, format)`
- `download_minutes(transcription_id, format)`

**Notes**
- `get_notes(transcription_id)`
- `append_note(transcription_id, text)`

**Chats**
- `list_chats(scope, scope_id)`
- `create_chat(...)`
- `add_chat_message(chat_id, message)`
- `get_chat(chat_id)`
- `download_chat(chat_id)`
- `delete_chat(chat_id)`

## Testing

Unit tests mock the Transcribe API (`httpx` mock transport / `respx`), covering
each tool's request shaping and response parsing, plus the auth renewal logic
(expiring token triggers re-exchange, failed renewal falls back to API-key
re-exchange). No live integration tests against the real Transcribe service are
planned for v1 — that would require a real whitelisted account/API key.
Implementation will follow TDD as tools are built.

## Packaging

`pyproject.toml` with a console-script entry point. Documentation will include
instructions for registering the server with Claude Code (`.mcp.json` /
`claude mcp add`) and Claude Desktop's config file.
