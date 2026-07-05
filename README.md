# transcribeMCP

MCP server for GovTech's [Transcribe](https://www.transcribe.gov.sg/) speech-to-text service. Lets an MCP client (Claude Code, Claude Desktop, etc.) upload audio, run batch transcriptions, and work with the results — summaries, minutes, sections, notes, and transcript Q&A chats.

## Setup

1. Get a Transcribe API key: log into https://www.transcribe.gov.sg/ and visit https://www.transcribe.gov.sg/dev_api_key (or use the `POST /auth/otps` + `POST /auth/tokens` + `POST /auth/apikeys` flow if your org isn't on WOG-AD). API keys are valid for 90 days.
2. Install the package:
   ```bash
   pip install -e .
   ```
3. Set the required environment variables:
   - `TRANSCRIBE_API_KEY` — your 90-day API key
   - `TRANSCRIBE_EMAIL` — the email address the API key was issued to
   - `TRANSCRIBE_BASE_URL` — optional, defaults to `https://core.transcribe.gov.sg`
   - `TRANSCRIBE_API_VERSION` — optional, defaults to `3.0`

## Registering with Claude Code

```bash
claude mcp add transcribe \
  --env TRANSCRIBE_API_KEY=your-api-key \
  --env TRANSCRIBE_EMAIL=you@domain.gov.sg \
  -- transcribemcp
```

Or add directly to `.mcp.json`:

```json
{
  "mcpServers": {
    "transcribe": {
      "command": "transcribemcp",
      "env": {
        "TRANSCRIBE_API_KEY": "your-api-key",
        "TRANSCRIBE_EMAIL": "you@domain.gov.sg"
      }
    }
  }
}
```

## Registering with Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "transcribe": {
      "command": "transcribemcp",
      "env": {
        "TRANSCRIBE_API_KEY": "your-api-key",
        "TRANSCRIBE_EMAIL": "you@domain.gov.sg"
      }
    }
  }
}
```

## Scope

Covers batch transcription (workspaces, projects, transcriptions), summaries, minutes, sections, notes, and chat-based Q&A over a transcript. Live Transcription is not supported — it requires real-time WebRTC audio streaming, which doesn't fit an MCP tool-call model. See `docs/superpowers/specs/2026-07-05-transcribe-mcp-server-design.md` for the full design rationale.

## Development

```bash
pip install -e ".[dev]"
pytest
```
