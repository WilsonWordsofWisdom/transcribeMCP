# Transcribe HTTP (Streamable) MCP Server — Design

## Purpose

Build a second, self-contained MCP server that exposes the same Transcribe
functionality as the existing stdio server, but over the **Streamable HTTP**
transport so it can be **hosted remotely** and used by external agents. Unlike
the stdio server (one Transcribe account, credentials baked in via env vars),
this server is **multi-tenant**: each caller supplies their own Transcribe
credentials per request.

This is a sibling to the existing stdio server, which was reorganized into a
`stdio/` folder. The new server lives in its own `http/` folder and is
independently installable and deployable.

## Context: current repo state

The user reorganized the repo before this work:
- The original `transcribemcp/` package and `tests/` were moved into a folder
  named `stido/` (a typo for `stdio/`).
- An empty `sse/` folder was created for the new server.
- `pyproject.toml` remains at the repo root, still pointing at the old
  `transcribemcp` path — now orphaned.

This reorganization is uncommitted at design time and will be finalized as part
of implementation (see "Repo housekeeping").

## Transport decision

The user initially said "SSE". SSE (HTTP+SSE, MCP protocol 2024-11-05) is
**deprecated** in the MCP spec, replaced by **Streamable HTTP** (2025-03-26+).
For a new server meant to be hosted for external agents, Streamable HTTP is the
correct, modern, better-supported choice. **We build Streamable HTTP**, not SSE.

Verified against the installed SDK (`mcp` 1.28.1): `FastMCP` exposes
`streamable_http_app()` (a Starlette ASGI app we can wrap with middleware),
`run(transport="streamable-http")` / `run_streamable_http_async()`, settings for
`host`/`port`/`stateless_http`/`streamable_http_path`, and `custom_route` for a
health endpoint.

## Key decisions (from brainstorming)

- **Transport:** Streamable HTTP.
- **Credential model:** Per-caller (multi-tenant). The server holds NO Transcribe
  key. Each caller sends `X-Transcribe-Api-Key` and `X-Transcribe-Email` headers.
- **Inbound auth:** None beyond the Transcribe credentials (v1). The endpoint is
  reachable but useless without a valid Transcribe key. HTTPS mandatory; keep URL
  private; a gateway bearer token can be added later as pure middleware.
- **Code structure:** Self-contained copy in `http/` (its own tool modules,
  config, auth/client, tests, Dockerfile). Does not touch the shipped stdio
  version. Tradeoff accepted: tool request-logic is duplicated across folders.
- **Hosting:** Docker (Dockerfile + docker-compose.yml + deploy notes).
- **Concurrency:** Synchronous tools run in FastMCP's threadpool (reusing stdio
  logic almost verbatim), with a `threading.Lock` added to `TokenManager` for
  safe concurrent JWT exchange/renewal. Async (httpx.AsyncClient) is a documented
  future optimization, out of scope for v1.

## Repo housekeeping (part of this work)

- Rename `stido/` → `stdio/`.
- Rename `sse/` → `http/`.
- Give `stdio/` its own `pyproject.toml` (package `transcribemcp`, console script
  `transcribemcp`), so the stdio server still installs from within `stdio/`.
- Remove the orphaned root `pyproject.toml`.

Result: two independent projects, `stdio/` and `http/`, each installable on its
own.

## Architecture: `http/` package

```
http/
  transcribe_http_mcp/
    __init__.py
    config.py         # server config from env (NO transcribe key/email)
    credentials.py    # contextvar + ASGI middleware for per-request creds
    auth.py           # TokenManager (ported) + threading.Lock
    client.py         # TranscribeClient (ported verbatim)
    registry.py       # bounded per-caller cache: (api_key,email) -> TranscribeClient
    tools/
      __init__.py
      metadata.py workspaces.py projects.py transcriptions.py summaries.py
      sections.py minutes.py notes.py chats.py
    app.py            # build FastMCP, register tools, wrap ASGI app, /health, expose `app`
    server.py         # main(): uvicorn serves `app`
  tests/
    __init__.py
    fakes.py
    test_config.py test_auth.py test_client.py test_credentials.py
    test_registry.py test_app.py
    tools/
      test_*.py       # ported tool tests, adapted to the request-scoped client provider
  pyproject.toml
  Dockerfile
  docker-compose.yml
  .dockerignore
  README.md
```

### config.py

Loads server config from env vars (all optional with defaults):

- `TRANSCRIBE_BASE_URL` (default `https://core.transcribe.gov.sg`) — upstream API.
- `TRANSCRIBE_API_VERSION` (default `3.0`).
- `MCP_HOST` (default `0.0.0.0`) — bind all interfaces (container-friendly).
- `MCP_PORT` (default `8000`).
- `MCP_PATH` (default `/mcp`) — Streamable HTTP endpoint path.
- `LOG_LEVEL` (default `info`).
- `CLIENT_CACHE_MAX` (default `256`) — max cached per-caller clients.

Crucially, this config does NOT include a Transcribe API key or email; those are
per-caller and never server-wide.

### credentials.py

- A `contextvars.ContextVar` holding the current request's Transcribe credentials
  (`(api_key, email)` or `None`).
- An ASGI middleware that, for each HTTP request, reads `X-Transcribe-Api-Key` and
  `X-Transcribe-Email` headers and sets the contextvar (to `None` when absent).
  It does NOT reject credential-less requests — MCP discovery calls (initialize,
  list_tools) must work without credentials so clients can enumerate tools.
- A `get_current_credentials()` accessor returning the contextvar value.

### auth.py

Ported `TokenManager` from the stdio server, with one addition: a
`threading.Lock` guarding `_exchange`/`_renew`/token-state mutation so concurrent
requests from the same caller (running in FastMCP's threadpool) cannot race on
JWT exchange/renewal. Same public interface (`get_token()`, `invalidate()`).

### client.py

`TranscribeClient` ported verbatim from the stdio server (same
`get_json`/`post_form`/`put_json`/`delete`/`download`, 401-retry, error wrapping).

### registry.py

A bounded cache mapping `(api_key, email)` → a fully-wired `TranscribeClient`
(each with its own `TokenManager` and a shared module-level `httpx.Client`).
Caching lets a caller's JWT be reused across their requests instead of
re-exchanging every call. Bounded by `CLIENT_CACHE_MAX` (LRU eviction) to prevent
unbounded memory growth from many distinct callers. Provides:

- `get_client(credentials)` — returns/creates the cached client for those creds.
- A `get_client_for_request()` provider used by tools: reads the contextvar via
  `get_current_credentials()`; if `None`, raises a clear error
  ("Missing X-Transcribe-Api-Key / X-Transcribe-Email headers"); otherwise returns
  the cached client.

### tools/

The same 9 modules and 29 tools as the stdio server. The ONLY structural change:
instead of `register(mcp, client)` closing over a single client, registration is
`register(mcp)`, and each tool calls `get_client_for_request()` (imported from
`registry`) at call time to obtain the request-scoped client. Every tool's
upstream request logic (paths, params, encodings) is identical to the stdio
version.

### app.py

- Builds `FastMCP("transcribe")` with `stateless_http=True`.
- Registers all 9 tool modules.
- Obtains the Streamable HTTP ASGI app via `mcp.streamable_http_app()` and wraps
  it with the credentials middleware.
- Adds a `GET /health` route returning `200 {"status": "ok"}`.
- Exposes the resulting ASGI app as `app` for uvicorn.

### server.py

`main()` runs uvicorn against `app`, binding `MCP_HOST:MCP_PORT` at `LOG_LEVEL`.
Console entry point: `transcribe-http-mcp = transcribe_http_mcp.server:main`.

## Data flow

1. External agent opens a Streamable HTTP session to `https://host/mcp` with
   `X-Transcribe-Api-Key` and `X-Transcribe-Email` headers.
2. Credentials middleware stashes creds into the contextvar.
3. Agent calls a tool. The tool calls `get_client_for_request()`:
   - missing creds → clear tool error;
   - present → cached/newly-built `TranscribeClient` for those creds.
4. The client exchanges the API key for a JWT (per-caller `TokenManager`, renewed
   as needed), injects `Accept: version=` and `Authorization: Bearer` headers, and
   calls Transcribe.
5. Upstream 4xx/5xx surface as `TranscribeAPIError`, same as stdio.

## Security posture (v1)

- No separate server auth; Transcribe credentials are the only gate.
- HTTPS only — callers transmit their API key; TLS terminates at a reverse
  proxy / platform in front of the container.
- Credentials are never persisted or logged; they live only in memory in the
  bounded cache.
- Keep the endpoint URL private; optionally firewall/IP-restrict at the host.
- A gateway bearer token (single shared or allowlist) can be added later as
  middleware with zero changes to tools.

## Testing

- Unit tests mock at the same seam as the stdio server: tool tests set the
  request-scoped client to a `FakeTranscribeClient` and assert on recorded calls.
- New tests specific to this server:
  - `credentials.py`: middleware extracts headers into the contextvar; absent
    headers yield `None`.
  - `registry.py`: `get_client_for_request()` raises a clear error when creds are
    missing; returns the SAME client instance for identical creds and DISTINCT
    clients for different creds; respects the cache bound.
  - `auth.py`: `TokenManager` still behaves correctly with the lock; a basic
    concurrency test that concurrent `get_token()` calls trigger exactly one
    exchange.
  - `app.py`: `GET /health` returns 200; the app builds and registers 29 tools.
- `client.py` and `config.py` tests port over (config asserts defaults + no
  required Transcribe key/email).
- No live integration tests against the real Transcribe service (requires real
  whitelisted accounts).

## Docker & deployment

- **Dockerfile:** slim Python base (e.g. `python:3.12-slim`), install the `http/`
  package, create/run as a non-root user, `EXPOSE 8000`, `CMD` runs
  `transcribe-http-mcp` (uvicorn serving `app` on `0.0.0.0:8000`).
- **docker-compose.yml:** builds the image, maps the port, sets
  `TRANSCRIBE_BASE_URL`/`TRANSCRIBE_API_VERSION`/`LOG_LEVEL`, for local testing.
- **.dockerignore:** excludes tests, venvs, caches, git.
- **README.md:** how to build/run locally, how a client connects (the two
  required headers), and deploy notes emphasizing HTTPS termination at a reverse
  proxy / platform (Cloud Run, Render, Railway, Fly, ECS, or nginx/caddy on a VM).

## Out of scope (v1)

- SSE transport (deprecated).
- Separate inbound auth (gateway token / OAuth) — designed to be addable later.
- Async (httpx.AsyncClient) rewrite.
- Live integration tests.
- Any change to the stdio server's behavior (only its packaging/location moves).
