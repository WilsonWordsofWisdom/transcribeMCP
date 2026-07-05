# Transcribe MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python MCP server that exposes GovTech Transcribe's speech-to-text API (workspaces, projects, transcriptions, summaries, sections, minutes, notes, chats) as MCP tools, per `docs/superpowers/specs/2026-07-05-transcribe-mcp-server-design.md`.

**Architecture:** A `TranscribeClient` (httpx-based) handles all HTTP calls, a `TokenManager` transparently exchanges/renews JWTs from a long-lived API key, and nine `tools/*.py` modules each register a small, focused set of FastMCP tools that call `TranscribeClient`. `server.py` wires these together into one FastMCP app.

**Tech Stack:** Python 3.10+, `mcp` (FastMCP), `httpx`, `pytest`, `respx` (HTTP mocking for tests).

**Spec deviation found during planning:** the spec listed only `TRANSCRIBE_API_KEY` as required config. The actual `POST /auth/tokens` endpoint requires an `email` field alongside the API key (confirmed in the Postman collection's `tokens - create` request body: `{"email": ..., "otp": "", "apikey": ...}`). This plan adds a second required env var, `TRANSCRIBE_EMAIL`, to supply it. Flagging this now — if you'd rather avoid a second env var, the alternative is to have the server call `GET /auth/apikeys`-equivalent lookup first, but Transcribe has no such "whoami" endpoint, so `TRANSCRIBE_EMAIL` is the simplest correct option.

---

## File Structure

```
transcribemcp/
  __init__.py
  config.py              # env var loading (Task 2)
  auth.py                 # TokenManager: API key -> JWT exchange/renewal (Task 3)
  client.py                # TranscribeClient: HTTP calls, error wrapping (Task 4)
  server.py                # FastMCP app assembly (Task 15)
  tools/
    __init__.py
    metadata.py            # get_engines (Task 6)
    workspaces.py          # list/get/create (Task 7)
    projects.py            # list/get/create (audio upload)/delete (Task 8)
    transcriptions.py       # list/get/create/delete/download_transcript (Task 9)
    summaries.py            # generate/get/download (Task 10)
    sections.py              # get/update (Task 11)
    minutes.py                # generate/get/download (Task 12)
    notes.py                   # get/append (Task 13)
    chats.py                    # list/create/add_message/get/download/delete (Task 14)
tests/
  __init__.py
  fakes.py                 # FakeMCP + FakeTranscribeClient test doubles (Task 5)
  test_config.py
  test_auth.py
  test_client.py
  test_server.py
  tools/
    __init__.py
    test_metadata.py
    test_workspaces.py
    test_projects.py
    test_transcriptions.py
    test_summaries.py
    test_sections.py
    test_minutes.py
    test_notes.py
    test_chats.py
pyproject.toml
README.md                  # updated with setup + registration instructions (Task 16)
```

Every `tools/*.py` module exports a single `register(mcp, client) -> dict[str, Callable]` function: it defines each tool as a nested function decorated with `@mcp.tool()`, and returns them in a dict so tests can call them directly without booting a real MCP server. The official `mcp` SDK's `@FastMCP.tool()` decorator returns the original function unchanged, so this works both for real registration (`server.py`) and for tests (using a `FakeMCP` stub whose `.tool()` is also an identity decorator).

Tool-level tests use a `FakeTranscribeClient` test double (records calls, returns programmed responses) instead of mocking HTTP again for every tool — this keeps each tool test about "did I call the client correctly and return its response", while `client.py`'s own tests are the ones that mock HTTP (via `respx`) to verify headers, retries, multipart encoding, and error wrapping. This avoids duplicating HTTP-mocking boilerplate across ~29 tool tests.

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `transcribemcp/__init__.py`
- Create: `transcribemcp/tools/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/tools/__init__.py`

- [ ] **Step 1: Create the package directories and empty `__init__.py` files**

```bash
mkdir -p transcribemcp/tools tests/tools
touch transcribemcp/__init__.py transcribemcp/tools/__init__.py
touch tests/__init__.py tests/tools/__init__.py
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "transcribemcp"
version = "0.1.0"
description = "MCP server for GovTech's Transcribe speech-to-text service"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.2.0",
    "httpx>=0.27",
]

[project.scripts]
transcribemcp = "transcribemcp.server:main"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "respx>=0.21",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["transcribemcp"]
```

- [ ] **Step 3: Create a virtualenv and install the project in editable mode with dev dependencies**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Expected: install completes with no errors; `pip show transcribemcp` shows the package installed.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml transcribemcp tests
git commit -m "chore: scaffold transcribemcp package structure"
```

---

### Task 2: Config Module

**Files:**
- Create: `transcribemcp/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
import pytest

from transcribemcp.config import ConfigError, load_config


def test_load_config_reads_required_env_vars_and_applies_defaults(monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_API_KEY", "test-api-key")
    monkeypatch.setenv("TRANSCRIBE_EMAIL", "user@domain.gov.sg")
    monkeypatch.delenv("TRANSCRIBE_BASE_URL", raising=False)
    monkeypatch.delenv("TRANSCRIBE_API_VERSION", raising=False)

    config = load_config()

    assert config.api_key == "test-api-key"
    assert config.email == "user@domain.gov.sg"
    assert config.base_url == "https://core.transcribe.gov.sg"
    assert config.api_version == "3.0"


def test_load_config_honours_overridden_base_url_and_version(monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_API_KEY", "test-api-key")
    monkeypatch.setenv("TRANSCRIBE_EMAIL", "user@domain.gov.sg")
    monkeypatch.setenv("TRANSCRIBE_BASE_URL", "https://staging.transcribe.gov.sg")
    monkeypatch.setenv("TRANSCRIBE_API_VERSION", "2.1")

    config = load_config()

    assert config.base_url == "https://staging.transcribe.gov.sg"
    assert config.api_version == "2.1"


def test_load_config_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("TRANSCRIBE_API_KEY", raising=False)
    monkeypatch.setenv("TRANSCRIBE_EMAIL", "user@domain.gov.sg")

    with pytest.raises(ConfigError, match="TRANSCRIBE_API_KEY"):
        load_config()


def test_load_config_raises_when_email_missing(monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_API_KEY", "test-api-key")
    monkeypatch.delenv("TRANSCRIBE_EMAIL", raising=False)

    with pytest.raises(ConfigError, match="TRANSCRIBE_EMAIL"):
        load_config()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'transcribemcp.config'`

- [ ] **Step 3: Implement `transcribemcp/config.py`**

```python
import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://core.transcribe.gov.sg"
DEFAULT_API_VERSION = "3.0"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    api_key: str
    email: str
    base_url: str
    api_version: str


def load_config() -> Config:
    api_key = os.environ.get("TRANSCRIBE_API_KEY")
    if not api_key:
        raise ConfigError("TRANSCRIBE_API_KEY environment variable is required")

    email = os.environ.get("TRANSCRIBE_EMAIL")
    if not email:
        raise ConfigError("TRANSCRIBE_EMAIL environment variable is required")

    base_url = os.environ.get("TRANSCRIBE_BASE_URL", DEFAULT_BASE_URL)
    api_version = os.environ.get("TRANSCRIBE_API_VERSION", DEFAULT_API_VERSION)

    return Config(api_key=api_key, email=email, base_url=base_url, api_version=api_version)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add transcribemcp/config.py tests/test_config.py
git commit -m "feat: add env-var config loading"
```

---

### Task 3: Auth Module (TokenManager)

**Files:**
- Create: `transcribemcp/auth.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_auth.py
import httpx
import pytest
import respx

from transcribemcp.auth import AuthError, TokenManager

BASE_URL = "https://core.transcribe.gov.sg"


@respx.mock
def test_get_token_exchanges_api_key_on_first_call():
    route = respx.post(f"{BASE_URL}/auth/tokens").mock(
        return_value=httpx.Response(200, json={"token": "jwt-1"})
    )
    manager = TokenManager(httpx.Client(), BASE_URL, "user@domain.gov.sg", "api-key-1")

    token = manager.get_token()

    assert token == "jwt-1"
    assert route.called
    sent_body = route.calls.last.request.content
    assert b"api-key-1" in sent_body
    assert b"user@domain.gov.sg" in sent_body


@respx.mock
def test_get_token_reuses_cached_token_before_expiry():
    route = respx.post(f"{BASE_URL}/auth/tokens").mock(
        return_value=httpx.Response(200, json={"token": "jwt-1"})
    )
    manager = TokenManager(httpx.Client(), BASE_URL, "user@domain.gov.sg", "api-key-1")

    first = manager.get_token()
    second = manager.get_token()

    assert first == second == "jwt-1"
    assert route.call_count == 1


@respx.mock
def test_get_token_renews_when_close_to_expiry():
    respx.post(f"{BASE_URL}/auth/tokens").mock(
        return_value=httpx.Response(200, json={"token": "jwt-1"})
    )
    renew_route = respx.post(f"{BASE_URL}/auth/tokens/renew").mock(
        return_value=httpx.Response(200, json={"token": "jwt-2"})
    )
    manager = TokenManager(httpx.Client(), BASE_URL, "user@domain.gov.sg", "api-key-1")
    manager.get_token()
    manager._expires_at = 0.0  # simulate a token about to expire

    token = manager.get_token()

    assert token == "jwt-2"
    assert renew_route.called


@respx.mock
def test_get_token_falls_back_to_exchange_when_renew_fails():
    exchange_route = respx.post(f"{BASE_URL}/auth/tokens").mock(
        return_value=httpx.Response(200, json={"token": "jwt-1"})
    )
    respx.post(f"{BASE_URL}/auth/tokens/renew").mock(
        return_value=httpx.Response(400, json={"message": "expired"})
    )
    manager = TokenManager(httpx.Client(), BASE_URL, "user@domain.gov.sg", "api-key-1")
    manager.get_token()
    manager._expires_at = 0.0

    token = manager.get_token()

    assert token == "jwt-1"
    assert exchange_route.call_count == 2


@respx.mock
def test_invalidate_forces_new_exchange_on_next_call():
    route = respx.post(f"{BASE_URL}/auth/tokens").mock(
        side_effect=[
            httpx.Response(200, json={"token": "jwt-1"}),
            httpx.Response(200, json={"token": "jwt-2"}),
        ]
    )
    manager = TokenManager(httpx.Client(), BASE_URL, "user@domain.gov.sg", "api-key-1")
    manager.get_token()

    manager.invalidate()
    token = manager.get_token()

    assert token == "jwt-2"
    assert route.call_count == 2


@respx.mock
def test_exchange_raises_auth_error_on_failure():
    respx.post(f"{BASE_URL}/auth/tokens").mock(
        return_value=httpx.Response(400, json={"message": "Invalid API key."})
    )
    manager = TokenManager(httpx.Client(), BASE_URL, "user@domain.gov.sg", "bad-key")

    with pytest.raises(AuthError, match="Invalid API key"):
        manager.get_token()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'transcribemcp.auth'`

- [ ] **Step 3: Implement `transcribemcp/auth.py`**

```python
import time

import httpx


class AuthError(Exception):
    pass


class TokenManager:
    """Exchanges a Transcribe API key for a JWT bearer token and keeps it fresh."""

    RENEW_MARGIN_SECONDS = 300
    TOKEN_TTL_SECONDS = 43200  # 12 hours, matches Transcribe's JWT lifetime

    def __init__(self, http_client: httpx.Client, base_url: str, email: str, api_key: str):
        self._http = http_client
        self._base_url = base_url
        self._email = email
        self._api_key = api_key
        self._token: str | None = None
        self._expires_at: float = 0.0

    def get_token(self) -> str:
        if self._token is None:
            self._exchange()
        elif time.monotonic() >= self._expires_at - self.RENEW_MARGIN_SECONDS:
            self._renew()
        return self._token

    def invalidate(self) -> None:
        """Force the next get_token() call to fetch a brand new token."""
        self._token = None

    def _exchange(self) -> None:
        response = self._http.post(
            f"{self._base_url}/auth/tokens",
            params={"service": self._base_url, "expiry": self.TOKEN_TTL_SECONDS},
            json={"email": self._email, "otp": "", "apikey": self._api_key},
        )
        if response.status_code != 200:
            raise AuthError(f"Failed to obtain auth token ({response.status_code}): {response.text}")
        self._token = response.json()["token"]
        self._expires_at = time.monotonic() + self.TOKEN_TTL_SECONDS

    def _renew(self) -> None:
        response = self._http.post(
            f"{self._base_url}/auth/tokens/renew",
            json={"token": self._token},
        )
        if response.status_code != 200:
            self._exchange()
            return
        self._token = response.json()["token"]
        self._expires_at = time.monotonic() + self.TOKEN_TTL_SECONDS
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_auth.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add transcribemcp/auth.py tests/test_auth.py
git commit -m "feat: add TokenManager for API-key-to-JWT auth with renewal"
```

---

### Task 4: API Client

**Files:**
- Create: `transcribemcp/client.py`
- Test: `tests/test_client.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_client.py
import httpx
import pytest
import respx

from transcribemcp.client import TranscribeAPIError, TranscribeClient

BASE_URL = "https://core.transcribe.gov.sg"


class FakeTokenManager:
    def __init__(self, tokens):
        self._tokens = iter(tokens)
        self.invalidate_calls = 0

    def get_token(self):
        return next(self._tokens)

    def invalidate(self):
        self.invalidate_calls += 1


@respx.mock
def test_get_json_sends_version_header_and_bearer_token():
    route = respx.get(f"{BASE_URL}/workspaces").mock(
        return_value=httpx.Response(200, json=[{"id": "w1"}])
    )
    client = TranscribeClient(BASE_URL, "3.0", FakeTokenManager(["jwt-1"]), httpx.Client())

    result = client.get_json("/workspaces")

    assert result == [{"id": "w1"}]
    sent_headers = route.calls.last.request.headers
    assert sent_headers["Accept"] == "version=3.0"
    assert sent_headers["Authorization"] == "Bearer jwt-1"


@respx.mock
def test_get_json_returns_none_on_204():
    respx.get(f"{BASE_URL}/transcriptions/t1/summary").mock(return_value=httpx.Response(204))
    client = TranscribeClient(BASE_URL, "3.0", FakeTokenManager(["jwt-1"]), httpx.Client())

    assert client.get_json("/transcriptions/t1/summary") is None


@respx.mock
def test_request_retries_once_on_401_with_fresh_token():
    route = respx.get(f"{BASE_URL}/workspaces").mock(
        side_effect=[
            httpx.Response(401, json={"message": "expired"}),
            httpx.Response(200, json=[{"id": "w1"}]),
        ]
    )
    tokens = FakeTokenManager(["stale-jwt", "fresh-jwt"])
    client = TranscribeClient(BASE_URL, "3.0", tokens, httpx.Client())

    result = client.get_json("/workspaces")

    assert result == [{"id": "w1"}]
    assert route.call_count == 2
    assert tokens.invalidate_calls == 1
    assert route.calls[0].request.headers["Authorization"] == "Bearer stale-jwt"
    assert route.calls[1].request.headers["Authorization"] == "Bearer fresh-jwt"


@respx.mock
def test_error_response_raises_transcribe_api_error_with_message():
    respx.get(f"{BASE_URL}/workspaces/bad-id").mock(
        return_value=httpx.Response(403, json={"message": "Insufficient permissions"})
    )
    client = TranscribeClient(BASE_URL, "3.0", FakeTokenManager(["jwt-1"]), httpx.Client())

    with pytest.raises(TranscribeAPIError) as exc_info:
        client.get_json("/workspaces/bad-id")

    assert exc_info.value.status_code == 403
    assert "Insufficient permissions" in exc_info.value.message


@respx.mock
def test_post_form_sends_multipart_file_upload():
    route = respx.post(f"{BASE_URL}/projects").mock(return_value=httpx.Response(201, json={"id": "p1"}))
    client = TranscribeClient(BASE_URL, "3.0", FakeTokenManager(["jwt-1"]), httpx.Client())

    result = client.post_form(
        "/projects",
        data={"name": "demo", "workspace_id": "w1"},
        files={"audio": ("demo.wav", b"RIFF....", "application/octet-stream")},
    )

    assert result == {"id": "p1"}
    request_body = route.calls.last.request.content
    assert b'name="audio"; filename="demo.wav"' in request_body
    assert b'name="name"' in request_body


@respx.mock
def test_put_json_sends_json_body():
    route = respx.put(f"{BASE_URL}/transcriptions/t1/sections").mock(
        return_value=httpx.Response(200, json={"sections": []})
    )
    client = TranscribeClient(BASE_URL, "3.0", FakeTokenManager(["jwt-1"]), httpx.Client())

    result = client.put_json("/transcriptions/t1/sections", json_body={"sections": []})

    assert result == {"sections": []}
    assert route.calls.last.request.headers["content-type"] == "application/json"


@respx.mock
def test_download_returns_raw_bytes():
    respx.get(f"{BASE_URL}/transcriptions/t1/latest_transcript/download").mock(
        return_value=httpx.Response(200, content=b"transcript text")
    )
    client = TranscribeClient(BASE_URL, "3.0", FakeTokenManager(["jwt-1"]), httpx.Client())

    result = client.download("/transcriptions/t1/latest_transcript/download")

    assert result == b"transcript text"


@respx.mock
def test_delete_raises_nothing_on_204():
    respx.delete(f"{BASE_URL}/projects/p1").mock(return_value=httpx.Response(204))
    client = TranscribeClient(BASE_URL, "3.0", FakeTokenManager(["jwt-1"]), httpx.Client())

    client.delete("/projects/p1")  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'transcribemcp.client'`

- [ ] **Step 3: Implement `transcribemcp/client.py`**

```python
from typing import Any

import httpx

from .auth import TokenManager


class TranscribeAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Transcribe API error {status_code}: {message}")


class TranscribeClient:
    def __init__(
        self,
        base_url: str,
        api_version: str,
        token_manager: TokenManager,
        http_client: httpx.Client,
    ):
        self._base_url = base_url
        self._api_version = api_version
        self._tokens = token_manager
        self._http = http_client

    def _headers(self) -> dict:
        return {
            "Accept": f"version={self._api_version}",
            "Authorization": f"Bearer {self._tokens.get_token()}",
        }

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self._base_url}{path}"
        response = self._http.request(method, url, headers=self._headers(), **kwargs)
        if response.status_code == 401:
            self._tokens.invalidate()
            response = self._http.request(method, url, headers=self._headers(), **kwargs)
        if response.status_code >= 400:
            raise TranscribeAPIError(response.status_code, _error_message(response))
        return response

    def get_json(self, path: str, params: dict | None = None) -> Any:
        response = self.request("GET", path, params=params)
        return _parse_json(response)

    def post_form(self, path: str, data: dict | None = None, files: dict | None = None) -> Any:
        response = self.request("POST", path, data=data, files=files)
        return _parse_json(response)

    def put_json(self, path: str, json_body: dict | None = None) -> Any:
        response = self.request("PUT", path, json=json_body)
        return _parse_json(response)

    def delete(self, path: str) -> None:
        self.request("DELETE", path)

    def download(self, path: str, params: dict | None = None) -> bytes:
        response = self.request("GET", path, params=params)
        return response.content


def _parse_json(response: httpx.Response) -> Any:
    if response.status_code == 204 or not response.content:
        return None
    return response.json()


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
        return body.get("message", response.text)
    except ValueError:
        return response.text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_client.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add transcribemcp/client.py tests/test_client.py
git commit -m "feat: add TranscribeClient HTTP wrapper with 401 retry and error wrapping"
```

---

### Task 5: Test Doubles for Tool Tests

**Files:**
- Create: `tests/fakes.py`

- [ ] **Step 1: Create `tests/fakes.py`**

```python
class FakeMCP:
    """Stub for FastMCP: `.tool()` returns the function unchanged, mirroring the
    real `mcp.server.fastmcp.FastMCP.tool()` decorator's identity behavior."""

    def __init__(self):
        self.registered = {}

    def tool(self):
        def decorator(fn):
            self.registered[fn.__name__] = fn
            return fn

        return decorator


class FakeTranscribeClient:
    """Records every call made against it and returns pre-programmed responses,
    standing in for TranscribeClient in tool-level unit tests."""

    def __init__(self):
        self.calls: list[tuple] = []
        self._responses: dict[tuple, object] = {}

    def set_response(self, method: str, path: str, response: object) -> None:
        self._responses[(method, path)] = response

    def _record_and_respond(self, method: str, path: str, **kwargs):
        self.calls.append((method, path, kwargs))
        return self._responses.get((method, path))

    def get_json(self, path, params=None):
        return self._record_and_respond("get_json", path, params=params)

    def post_form(self, path, data=None, files=None):
        return self._record_and_respond("post_form", path, data=data, files=files)

    def put_json(self, path, json_body=None):
        return self._record_and_respond("put_json", path, json_body=json_body)

    def delete(self, path):
        return self._record_and_respond("delete", path)

    def download(self, path, params=None):
        return self._record_and_respond("download", path, params=params)
```

- [ ] **Step 2: Commit**

```bash
git add tests/fakes.py
git commit -m "test: add FakeMCP and FakeTranscribeClient test doubles"
```

(No red/green cycle here — this is test infrastructure, not behavior under test. It gets exercised for the first time in Task 6.)

---

### Task 6: Metadata Tools (`get_engines`)

**Files:**
- Create: `transcribemcp/tools/metadata.py`
- Test: `tests/tools/test_metadata.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/test_metadata.py
from tests.fakes import FakeMCP, FakeTranscribeClient
from transcribemcp.tools import metadata


def test_get_engines_calls_engines_endpoint_with_type():
    mcp = FakeMCP()
    client = FakeTranscribeClient()
    client.set_response("get_json", "/engines", {"english": [{"engine": "google"}]})
    tools = metadata.register(mcp, client)

    result = tools["get_engines"](type="batch")

    assert result == {"english": [{"engine": "google"}]}
    assert client.calls == [("get_json", "/engines", {"params": {"type": "batch"}})]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_metadata.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'transcribemcp.tools.metadata'`

- [ ] **Step 3: Implement `transcribemcp/tools/metadata.py`**

```python
def register(mcp, client):
    @mcp.tool()
    def get_engines(type: str) -> dict:
        """List transcription engines and options available for a job type.

        Args:
            type: Either "batch" or "live".
        """
        return client.get_json("/engines", params={"type": type})

    return {"get_engines": get_engines}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/tools/test_metadata.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add transcribemcp/tools/metadata.py tests/tools/test_metadata.py
git commit -m "feat: add get_engines tool"
```

---

### Task 7: Workspaces Tools

**Files:**
- Create: `transcribemcp/tools/workspaces.py`
- Test: `tests/tools/test_workspaces.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/tools/test_workspaces.py
from tests.fakes import FakeMCP, FakeTranscribeClient
from transcribemcp.tools import workspaces


def _tools():
    mcp = FakeMCP()
    client = FakeTranscribeClient()
    return client, workspaces.register(mcp, client)


def test_list_workspaces_defaults_to_limit_and_offset():
    client, tools = _tools()
    client.set_response("get_json", "/workspaces", [{"id": "w1"}])

    result = tools["list_workspaces"]()

    assert result == [{"id": "w1"}]
    assert client.calls == [("get_json", "/workspaces", {"params": {"limit": 10, "offset": 0}})]


def test_list_workspaces_includes_optional_filters():
    client, tools = _tools()
    client.set_response("get_json", "/workspaces", [])

    tools["list_workspaces"](name="demo", owner="a@b.gov.sg", workspace_type="shared", limit=5, offset=2)

    assert client.calls == [
        (
            "get_json",
            "/workspaces",
            {"params": {"limit": 5, "offset": 2, "name": "demo", "owner": "a@b.gov.sg", "type": "shared"}},
        )
    ]


def test_get_workspace_fetches_by_id():
    client, tools = _tools()
    client.set_response("get_json", "/workspaces/w1", {"id": "w1"})

    result = tools["get_workspace"]("w1")

    assert result == {"id": "w1"}
    assert client.calls == [("get_json", "/workspaces/w1", {"params": None})]


def test_create_workspace_posts_name():
    client, tools = _tools()
    client.set_response("post_form", "/workspaces", {"id": "w1", "name": "demo"})

    result = tools["create_workspace"]("demo")

    assert result == {"id": "w1", "name": "demo"}
    assert client.calls == [("post_form", "/workspaces", {"data": {"name": "demo"}, "files": None})]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_workspaces.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'transcribemcp.tools.workspaces'`

- [ ] **Step 3: Implement `transcribemcp/tools/workspaces.py`**

```python
def register(mcp, client):
    @mcp.tool()
    def list_workspaces(
        name: str | None = None,
        owner: str | None = None,
        workspace_type: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[dict]:
        """List workspaces you are a member of, optionally filtered.

        Args:
            name: Filter by workspace name.
            owner: Filter by owner email.
            workspace_type: Filter by "personal" or "shared".
            limit: Max workspaces to return (1-50).
            offset: Pagination offset.
        """
        params = {"limit": limit, "offset": offset}
        if name is not None:
            params["name"] = name
        if owner is not None:
            params["owner"] = owner
        if workspace_type is not None:
            params["type"] = workspace_type
        return client.get_json("/workspaces", params=params)

    @mcp.tool()
    def get_workspace(workspace_id: str) -> dict:
        """Get a single workspace by ID.

        Args:
            workspace_id: The workspace's ID.
        """
        return client.get_json(f"/workspaces/{workspace_id}")

    @mcp.tool()
    def create_workspace(name: str) -> dict:
        """Create a new shared workspace. You become its owner.

        Args:
            name: Name for the new workspace.
        """
        return client.post_form("/workspaces", data={"name": name})

    return {
        "list_workspaces": list_workspaces,
        "get_workspace": get_workspace,
        "create_workspace": create_workspace,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_workspaces.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add transcribemcp/tools/workspaces.py tests/tools/test_workspaces.py
git commit -m "feat: add workspace tools (list/get/create)"
```

---

### Task 8: Projects Tools

**Files:**
- Create: `transcribemcp/tools/projects.py`
- Test: `tests/tools/test_projects.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/tools/test_projects.py
from tests.fakes import FakeMCP, FakeTranscribeClient
from transcribemcp.tools import projects


def _tools():
    mcp = FakeMCP()
    client = FakeTranscribeClient()
    return client, projects.register(mcp, client)


def test_list_projects_defaults_to_limit_and_offset():
    client, tools = _tools()
    client.set_response("get_json", "/projects", [{"id": "p1"}])

    result = tools["list_projects"]()

    assert result == [{"id": "p1"}]
    assert client.calls == [("get_json", "/projects", {"params": {"limit": 10, "offset": 0}})]


def test_list_projects_includes_optional_filters():
    client, tools = _tools()
    client.set_response("get_json", "/projects", [])

    tools["list_projects"](workspace_id="w1", name="demo", owner="a@b.gov.sg", tag="est", limit=5, offset=1)

    assert client.calls == [
        (
            "get_json",
            "/projects",
            {
                "params": {
                    "limit": 5,
                    "offset": 1,
                    "workspace_id": "w1",
                    "name": "demo",
                    "owner": "a@b.gov.sg",
                    "tag": "est",
                }
            },
        )
    ]


def test_get_project_fetches_by_id():
    client, tools = _tools()
    client.set_response("get_json", "/projects/p1", {"id": "p1"})

    result = tools["get_project"]("p1")

    assert result == {"id": "p1"}
    assert client.calls == [("get_json", "/projects/p1", {"params": None})]


def test_create_project_uploads_audio_file_with_metadata(tmp_path):
    client, tools = _tools()
    client.set_response("post_form", "/projects", {"id": "p1", "name": "demo"})
    audio_path = tmp_path / "demo.wav"
    audio_path.write_bytes(b"RIFF....")

    result = tools["create_project"](
        name="demo",
        workspace_id="w1",
        audio_path=str(audio_path),
        sensitivity="Non-Sensitive",
        classification="Official Open",
        languages=["en_us"],
        tags=["demo"],
    )

    assert result == {"id": "p1", "name": "demo"}
    assert len(client.calls) == 1
    method, path, kwargs = client.calls[0]
    assert (method, path) == ("post_form", "/projects")
    assert kwargs["data"] == {
        "name": "demo",
        "workspace_id": "w1",
        "sensitivity": "Non-Sensitive",
        "classification": "Official Open",
        "languages": ["en_us"],
        "tags": ["demo"],
    }
    filename, file_obj, content_type = kwargs["files"]["audio"]
    assert filename == "demo.wav"
    assert file_obj.read() == b"RIFF...."
    assert content_type == "application/octet-stream"


def test_create_project_omits_optional_metadata_when_not_given(tmp_path):
    client, tools = _tools()
    client.set_response("post_form", "/projects", {"id": "p1"})
    audio_path = tmp_path / "demo.wav"
    audio_path.write_bytes(b"RIFF....")

    tools["create_project"](
        name="demo",
        workspace_id="w1",
        audio_path=str(audio_path),
        sensitivity="Non-Sensitive",
        classification="Official Open",
    )

    kwargs = client.calls[0][2]
    assert "languages" not in kwargs["data"]
    assert "tags" not in kwargs["data"]


def test_delete_project_calls_delete_and_confirms():
    client, tools = _tools()

    result = tools["delete_project"]("p1")

    assert result == {"status": "deleted", "project_id": "p1"}
    assert client.calls == [("delete", "/projects/p1", {})]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_projects.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'transcribemcp.tools.projects'`

- [ ] **Step 3: Implement `transcribemcp/tools/projects.py`**

```python
from pathlib import Path


def register(mcp, client):
    @mcp.tool()
    def list_projects(
        workspace_id: str | None = None,
        name: str | None = None,
        owner: str | None = None,
        tag: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[dict]:
        """List transcription projects, optionally filtered.

        Args:
            workspace_id: Only list projects in this workspace.
            name: Filter by project name.
            owner: Filter by owner email.
            tag: Filter by project tag.
            limit: Max projects to return (1-50).
            offset: Pagination offset.
        """
        params = {"limit": limit, "offset": offset}
        if workspace_id is not None:
            params["workspace_id"] = workspace_id
        if name is not None:
            params["name"] = name
        if owner is not None:
            params["owner"] = owner
        if tag is not None:
            params["tag"] = tag
        return client.get_json("/projects", params=params)

    @mcp.tool()
    def get_project(project_id: str) -> dict:
        """Get a single transcription project by ID.

        Args:
            project_id: The project's ID.
        """
        return client.get_json(f"/projects/{project_id}")

    @mcp.tool()
    def create_project(
        name: str,
        workspace_id: str,
        audio_path: str,
        sensitivity: str,
        classification: str,
        languages: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Create a transcription project by uploading a local audio file.

        Args:
            name: Name of the project.
            workspace_id: ID of the workspace to create the project under.
            audio_path: Local filesystem path to the audio file to upload.
            sensitivity: One of "Non-Sensitive", "Sensitive Normal", "Sensitive High".
            classification: One of "Official Open", "Official Closed", "Restricted".
            languages: Optional list of language tags for project metadata.
            tags: Optional list of free-text tags for project metadata.
        """
        path = Path(audio_path)
        data = {
            "name": name,
            "workspace_id": workspace_id,
            "sensitivity": sensitivity,
            "classification": classification,
        }
        if languages:
            data["languages"] = languages
        if tags:
            data["tags"] = tags
        with path.open("rb") as audio_file:
            return client.post_form(
                "/projects",
                data=data,
                files={"audio": (path.name, audio_file, "application/octet-stream")},
            )

    @mcp.tool()
    def delete_project(project_id: str) -> dict:
        """Permanently delete a transcription project and all its transcriptions.

        Args:
            project_id: The project's ID.
        """
        client.delete(f"/projects/{project_id}")
        return {"status": "deleted", "project_id": project_id}

    return {
        "list_projects": list_projects,
        "get_project": get_project,
        "create_project": create_project,
        "delete_project": delete_project,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_projects.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add transcribemcp/tools/projects.py tests/tools/test_projects.py
git commit -m "feat: add project tools (list/get/create with audio upload/delete)"
```

---

### Task 9: Transcriptions Tools

**Files:**
- Create: `transcribemcp/tools/transcriptions.py`
- Test: `tests/tools/test_transcriptions.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/tools/test_transcriptions.py
import json

import pytest

from tests.fakes import FakeMCP, FakeTranscribeClient
from transcribemcp.tools import transcriptions


def _tools():
    mcp = FakeMCP()
    client = FakeTranscribeClient()
    return client, transcriptions.register(mcp, client)


def test_list_transcriptions_defaults_to_batch_type():
    client, tools = _tools()
    client.set_response("get_json", "/transcriptions", [{"id": "t1"}])

    result = tools["list_transcriptions"]()

    assert result == [{"id": "t1"}]
    assert client.calls == [
        ("get_json", "/transcriptions", {"params": {"limit": 10, "offset": 0, "type": "batch"}})
    ]


def test_list_transcriptions_includes_optional_filters():
    client, tools = _tools()
    client.set_response("get_json", "/transcriptions", [])

    tools["list_transcriptions"](project_id="p1", workspace_id="w1", status="Success", limit=5, offset=1)

    assert client.calls == [
        (
            "get_json",
            "/transcriptions",
            {
                "params": {
                    "limit": 5,
                    "offset": 1,
                    "type": "batch",
                    "project_id": "p1",
                    "workspace_id": "w1",
                    "status": "Success",
                }
            },
        )
    ]


def test_get_transcription_fetches_by_id():
    client, tools = _tools()
    client.set_response("get_json", "/transcriptions/t1", {"id": "t1", "status": "In Queue"})

    result = tools["get_transcription"]("t1")

    assert result == {"id": "t1", "status": "In Queue"}
    assert client.calls == [("get_json", "/transcriptions/t1", {"params": None})]


def test_create_transcription_sends_engine_and_json_encoded_options():
    client, tools = _tools()
    client.set_response("post_form", "/transcriptions", {"id": "t1", "status": "In Queue"})
    engine_options = {"engine": "google", "model": "latest_long", "language": "english"}

    result = tools["create_transcription"]("p1", engine_options)

    assert result == {"id": "t1", "status": "In Queue"}
    assert client.calls == [
        (
            "post_form",
            "/transcriptions",
            {
                "data": {
                    "project_id": "p1",
                    "engine": "google",
                    "options": json.dumps(engine_options),
                    "type": "batch",
                    "has_diarization": "false",
                },
                "files": None,
            },
        )
    ]


def test_create_transcription_with_diarization_enabled():
    client, tools = _tools()
    client.set_response("post_form", "/transcriptions", {"id": "t1"})
    engine_options = {"engine": "google", "model": "latest_long"}

    tools["create_transcription"]("p1", engine_options, has_diarization=True)

    sent_data = client.calls[0][2]["data"]
    assert sent_data["has_diarization"] == "true"


def test_delete_transcription_calls_delete_and_confirms():
    client, tools = _tools()

    result = tools["delete_transcription"]("t1")

    assert result == {"status": "deleted", "transcription_id": "t1"}
    assert client.calls == [("delete", "/transcriptions/t1", {})]


def test_download_transcript_defaults_to_latest_variant():
    client, tools = _tools()
    client.set_response("download", "/transcriptions/t1/latest_transcript/download", b"hello transcript")

    result = tools["download_transcript"]("t1")

    assert result == "hello transcript"
    assert client.calls == [("download", "/transcriptions/t1/latest_transcript/download", {"params": None})]


def test_download_transcript_supports_raw_variant():
    client, tools = _tools()
    client.set_response("download", "/transcriptions/t1/raw_transcript/download", b"raw text")

    result = tools["download_transcript"]("t1", variant="raw")

    assert result == "raw text"


def test_download_transcript_rejects_invalid_variant():
    client, tools = _tools()

    with pytest.raises(ValueError, match="variant"):
        tools["download_transcript"]("t1", variant="bogus")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_transcriptions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'transcribemcp.tools.transcriptions'`

- [ ] **Step 3: Implement `transcribemcp/tools/transcriptions.py`**

```python
import json


def register(mcp, client):
    @mcp.tool()
    def list_transcriptions(
        project_id: str | None = None,
        workspace_id: str | None = None,
        status: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[dict]:
        """List batch transcription jobs, optionally filtered.

        Args:
            project_id: Only list transcriptions for this project.
            workspace_id: Only list transcriptions in this workspace.
            status: Filter by status, e.g. "In Queue", "In Progress", "Success", "Fail".
            limit: Max transcriptions to return (1-50).
            offset: Pagination offset.
        """
        params = {"limit": limit, "offset": offset, "type": "batch"}
        if project_id is not None:
            params["project_id"] = project_id
        if workspace_id is not None:
            params["workspace_id"] = workspace_id
        if status is not None:
            params["status"] = status
        return client.get_json("/transcriptions", params=params)

    @mcp.tool()
    def get_transcription(transcription_id: str) -> dict:
        """Get a transcription job's current status and metadata.

        Args:
            transcription_id: The transcription's ID.
        """
        return client.get_json(f"/transcriptions/{transcription_id}")

    @mcp.tool()
    def create_transcription(
        project_id: str,
        engine_options: dict,
        has_diarization: bool = False,
    ) -> dict:
        """Start a batch transcription job for a project.

        Args:
            project_id: ID of the project to transcribe (its audio file is used).
            engine_options: One of the engine option objects returned by get_engines,
                e.g. {"engine": "google", "model": "latest_long", "language": "english", ...}.
            has_diarization: Whether to enable speaker diarization.
        """
        return client.post_form(
            "/transcriptions",
            data={
                "project_id": project_id,
                "engine": engine_options["engine"],
                "options": json.dumps(engine_options),
                "type": "batch",
                "has_diarization": str(has_diarization).lower(),
            },
        )

    @mcp.tool()
    def delete_transcription(transcription_id: str) -> dict:
        """Permanently delete a transcription job (its project is unaffected).

        Args:
            transcription_id: The transcription's ID.
        """
        client.delete(f"/transcriptions/{transcription_id}")
        return {"status": "deleted", "transcription_id": transcription_id}

    @mcp.tool()
    def download_transcript(transcription_id: str, variant: str = "latest") -> str:
        """Download a transcription's transcript text.

        Args:
            transcription_id: The transcription's ID.
            variant: Which transcript to download: "raw", "uf" (user-formatted), or
                "latest" (the most recently edited version).
        """
        if variant not in ("raw", "uf", "latest"):
            raise ValueError('variant must be one of "raw", "uf", "latest"')
        content = client.download(f"/transcriptions/{transcription_id}/{variant}_transcript/download")
        return content.decode("utf-8")

    return {
        "list_transcriptions": list_transcriptions,
        "get_transcription": get_transcription,
        "create_transcription": create_transcription,
        "delete_transcription": delete_transcription,
        "download_transcript": download_transcript,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_transcriptions.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add transcribemcp/tools/transcriptions.py tests/tools/test_transcriptions.py
git commit -m "feat: add transcription tools (list/get/create/delete/download_transcript)"
```

---

### Task 10: Summaries Tools

**Files:**
- Create: `transcribemcp/tools/summaries.py`
- Test: `tests/tools/test_summaries.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/tools/test_summaries.py
from tests.fakes import FakeMCP, FakeTranscribeClient
from transcribemcp.tools import summaries


def _tools():
    mcp = FakeMCP()
    client = FakeTranscribeClient()
    return client, summaries.register(mcp, client)


def test_generate_summary_posts_prompt():
    client, tools = _tools()
    client.set_response(
        "post_form", "/transcriptions/t1/summary", {"transcription_id": "t1", "summary": None}
    )

    result = tools["generate_summary"]("t1", "How many speakers are there?")

    assert result == {"transcription_id": "t1", "summary": None}
    assert client.calls == [
        (
            "post_form",
            "/transcriptions/t1/summary",
            {"data": {"prompt": "How many speakers are there?"}, "files": None},
        )
    ]


def test_get_summary_fetches_metadata():
    client, tools = _tools()
    client.set_response("get_json", "/transcriptions/t1/summary", {"summary": {"name": "t1"}})

    result = tools["get_summary"]("t1")

    assert result == {"summary": {"name": "t1"}}
    assert client.calls == [("get_json", "/transcriptions/t1/summary", {"params": None})]


def test_get_summary_returns_none_when_not_generated():
    client, tools = _tools()
    client.set_response("get_json", "/transcriptions/t1/summary", None)

    assert tools["get_summary"]("t1") is None


def test_download_summary_decodes_text():
    client, tools = _tools()
    client.set_response("download", "/transcriptions/t1/summary/download", b"Two speakers.")

    result = tools["download_summary"]("t1")

    assert result == "Two speakers."
    assert client.calls == [("download", "/transcriptions/t1/summary/download", {"params": None})]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_summaries.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'transcribemcp.tools.summaries'`

- [ ] **Step 3: Implement `transcribemcp/tools/summaries.py`**

```python
def register(mcp, client):
    @mcp.tool()
    def generate_summary(transcription_id: str, prompt: str) -> dict:
        """Start an LLM-generated summary job for a completed transcription.

        Args:
            transcription_id: The transcription's ID.
            prompt: Instructions for how the LLM should summarize the transcript.
        """
        return client.post_form(f"/transcriptions/{transcription_id}/summary", data={"prompt": prompt})

    @mcp.tool()
    def get_summary(transcription_id: str) -> dict | None:
        """Get summary generation status/metadata for a transcription.

        Args:
            transcription_id: The transcription's ID.

        Returns:
            None if no summary has been generated yet.
        """
        return client.get_json(f"/transcriptions/{transcription_id}/summary")

    @mcp.tool()
    def download_summary(transcription_id: str) -> str:
        """Download the generated summary text for a transcription.

        Args:
            transcription_id: The transcription's ID.
        """
        content = client.download(f"/transcriptions/{transcription_id}/summary/download")
        return content.decode("utf-8")

    return {
        "generate_summary": generate_summary,
        "get_summary": get_summary,
        "download_summary": download_summary,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_summaries.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add transcribemcp/tools/summaries.py tests/tools/test_summaries.py
git commit -m "feat: add summary tools (generate/get/download)"
```

---

### Task 11: Sections Tools

**Files:**
- Create: `transcribemcp/tools/sections.py`
- Test: `tests/tools/test_sections.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/tools/test_sections.py
from tests.fakes import FakeMCP, FakeTranscribeClient
from transcribemcp.tools import sections


def _tools():
    mcp = FakeMCP()
    client = FakeTranscribeClient()
    return client, sections.register(mcp, client)


def test_get_sections_fetches_by_transcription_id():
    client, tools = _tools()
    client.set_response(
        "get_json", "/transcriptions/t1/sections", {"transcription_id": "t1", "sections": []}
    )

    result = tools["get_sections"]("t1")

    assert result == {"transcription_id": "t1", "sections": []}
    assert client.calls == [("get_json", "/transcriptions/t1/sections", {"params": None})]


def test_update_sections_sends_json_body():
    client, tools = _tools()
    new_sections = [{"name": "Introduction", "time": 0.0}, {"name": "Conclusion", "time": 120.5}]
    client.set_response(
        "put_json", "/transcriptions/t1/sections", {"transcription_id": "t1", "sections": new_sections}
    )

    result = tools["update_sections"]("t1", new_sections)

    assert result == {"transcription_id": "t1", "sections": new_sections}
    assert client.calls == [
        ("put_json", "/transcriptions/t1/sections", {"json_body": {"sections": new_sections}})
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_sections.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'transcribemcp.tools.sections'`

- [ ] **Step 3: Implement `transcribemcp/tools/sections.py`**

```python
def register(mcp, client):
    @mcp.tool()
    def get_sections(transcription_id: str) -> dict:
        """Get the section markers (chapter-like timestamps) for a transcription.

        Args:
            transcription_id: The transcription's ID.
        """
        return client.get_json(f"/transcriptions/{transcription_id}/sections")

    @mcp.tool()
    def update_sections(transcription_id: str, sections: list[dict]) -> dict:
        """Replace the section markers for a transcription.

        Args:
            transcription_id: The transcription's ID.
            sections: List of {"name": str, "time": float} objects, fully replacing
                the existing section list.
        """
        return client.put_json(f"/transcriptions/{transcription_id}/sections", json_body={"sections": sections})

    return {"get_sections": get_sections, "update_sections": update_sections}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_sections.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add transcribemcp/tools/sections.py tests/tools/test_sections.py
git commit -m "feat: add section tools (get/update)"
```

---

### Task 12: Minutes Tools

**Files:**
- Create: `transcribemcp/tools/minutes.py`
- Test: `tests/tools/test_minutes.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/tools/test_minutes.py
from tests.fakes import FakeMCP, FakeTranscribeClient
from transcribemcp.tools import minutes


def _tools():
    mcp = FakeMCP()
    client = FakeTranscribeClient()
    return client, minutes.register(mcp, client)


def test_generate_minutes_posts_format():
    client, tools = _tools()
    client.set_response(
        "post_form", "/transcriptions/t1/minutes", {"transcription_id": "t1", "minutes": None}
    )

    result = tools["generate_minutes"]("t1")

    assert result == {"transcription_id": "t1", "minutes": None}
    assert client.calls == [
        ("post_form", "/transcriptions/t1/minutes", {"data": {"format": "text_minutes"}, "files": None})
    ]


def test_get_minutes_fetches_with_format_param():
    client, tools = _tools()
    client.set_response(
        "get_json", "/transcriptions/t1/minutes", {"transcription_id": "t1", "minutes": {"name": "t1"}}
    )

    result = tools["get_minutes"]("t1")

    assert result == {"transcription_id": "t1", "minutes": {"name": "t1"}}
    assert client.calls == [
        ("get_json", "/transcriptions/t1/minutes", {"params": {"format": "text_minutes"}})
    ]


def test_download_minutes_decodes_text_with_custom_format():
    client, tools = _tools()
    client.set_response("download", "/transcriptions/t1/minutes/download", b"Meeting Minutes: ...")

    result = tools["download_minutes"]("t1", format="text_minutes")

    assert result == "Meeting Minutes: ..."
    assert client.calls == [
        ("download", "/transcriptions/t1/minutes/download", {"params": {"format": "text_minutes"}})
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_minutes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'transcribemcp.tools.minutes'`

- [ ] **Step 3: Implement `transcribemcp/tools/minutes.py`**

```python
def register(mcp, client):
    @mcp.tool()
    def generate_minutes(transcription_id: str, format: str = "text_minutes") -> dict:
        """Start a meeting-minutes generation job for a completed transcription.

        Args:
            transcription_id: The transcription's ID.
            format: Minutes format, e.g. "text_minutes".
        """
        return client.post_form(f"/transcriptions/{transcription_id}/minutes", data={"format": format})

    @mcp.tool()
    def get_minutes(transcription_id: str, format: str = "text_minutes") -> dict | None:
        """Get minutes generation status/metadata for a transcription.

        Args:
            transcription_id: The transcription's ID.
            format: Minutes format to check, e.g. "text_minutes".

        Returns:
            None if no minutes have been generated yet for that format.
        """
        return client.get_json(f"/transcriptions/{transcription_id}/minutes", params={"format": format})

    @mcp.tool()
    def download_minutes(transcription_id: str, format: str = "text_minutes") -> str:
        """Download the generated minutes text for a transcription.

        Args:
            transcription_id: The transcription's ID.
            format: Minutes format to download, e.g. "text_minutes".
        """
        content = client.download(
            f"/transcriptions/{transcription_id}/minutes/download", params={"format": format}
        )
        return content.decode("utf-8")

    return {
        "generate_minutes": generate_minutes,
        "get_minutes": get_minutes,
        "download_minutes": download_minutes,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_minutes.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add transcribemcp/tools/minutes.py tests/tools/test_minutes.py
git commit -m "feat: add minutes tools (generate/get/download)"
```

---

### Task 13: Notes Tools

**Files:**
- Create: `transcribemcp/tools/notes.py`
- Test: `tests/tools/test_notes.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/tools/test_notes.py
from tests.fakes import FakeMCP, FakeTranscribeClient
from transcribemcp.tools import notes


def _tools():
    mcp = FakeMCP()
    client = FakeTranscribeClient()
    return client, notes.register(mcp, client)


def test_get_notes_fetches_by_transcription_id():
    client, tools = _tools()
    client.set_response("get_json", "/transcriptions/t1/notes", {"notes": "hello\n"})

    result = tools["get_notes"]("t1")

    assert result == {"notes": "hello\n"}
    assert client.calls == [("get_json", "/transcriptions/t1/notes", {"params": None})]


def test_append_note_posts_text():
    client, tools = _tools()
    client.set_response("post_form", "/transcriptions/t1/append_text", {"notes": "hello\nworld\n"})

    result = tools["append_note"]("t1", "world\n")

    assert result == {"notes": "hello\nworld\n"}
    assert client.calls == [
        ("post_form", "/transcriptions/t1/append_text", {"data": {"text": "world\n"}, "files": None})
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_notes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'transcribemcp.tools.notes'`

- [ ] **Step 3: Implement `transcribemcp/tools/notes.py`**

```python
def register(mcp, client):
    @mcp.tool()
    def get_notes(transcription_id: str) -> dict | None:
        """Get the free-text notes attached to a transcription.

        Args:
            transcription_id: The transcription's ID.

        Returns:
            None if no notes exist yet.
        """
        return client.get_json(f"/transcriptions/{transcription_id}/notes")

    @mcp.tool()
    def append_note(transcription_id: str, text: str) -> dict:
        """Append text to a transcription's notes.

        Args:
            transcription_id: The transcription's ID.
            text: Text to append.
        """
        return client.post_form(f"/transcriptions/{transcription_id}/append_text", data={"text": text})

    return {"get_notes": get_notes, "append_note": append_note}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_notes.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add transcribemcp/tools/notes.py tests/tools/test_notes.py
git commit -m "feat: add notes tools (get/append)"
```

---

### Task 14: Chats Tools

**Files:**
- Create: `transcribemcp/tools/chats.py`
- Test: `tests/tools/test_chats.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/tools/test_chats.py
from tests.fakes import FakeMCP, FakeTranscribeClient
from transcribemcp.tools import chats


def _tools():
    mcp = FakeMCP()
    client = FakeTranscribeClient()
    return client, chats.register(mcp, client)


def test_list_chats_queries_by_scope():
    client, tools = _tools()
    client.set_response("get_json", "/chats", [{"id": "c1"}])

    result = tools["list_chats"]("transcription", "t1")

    assert result == [{"id": "c1"}]
    assert client.calls == [("get_json", "/chats", {"params": {"scope": "transcription", "scope_id": "t1"}})]


def test_create_chat_posts_scope_and_prompt():
    client, tools = _tools()
    client.set_response("post_form", "/chats", {"id": "c1", "title": "test"})

    result = tools["create_chat"]("transcription", "t1", "hello")

    assert result == {"id": "c1", "title": "test"}
    assert client.calls == [
        (
            "post_form",
            "/chats",
            {"data": {"scope": "transcription", "scope_id": "t1", "prompt": "hello"}, "files": None},
        )
    ]


def test_add_chat_message_posts_prompt():
    client, tools = _tools()
    client.set_response("post_form", "/chats/c1/message", {"id": "c1"})

    result = tools["add_chat_message"]("c1", "follow-up question")

    assert result == {"id": "c1"}
    assert client.calls == [
        ("post_form", "/chats/c1/message", {"data": {"prompt": "follow-up question"}, "files": None})
    ]


def test_get_chat_fetches_metadata():
    client, tools = _tools()
    client.set_response("get_json", "/chats/c1", {"id": "c1"})

    result = tools["get_chat"]("c1")

    assert result == {"id": "c1"}
    assert client.calls == [("get_json", "/chats/c1", {"params": None})]


def test_download_chat_fetches_message_history():
    client, tools = _tools()
    client.set_response("get_json", "/chats/c1/download", [{"user_message": "hi"}])

    result = tools["download_chat"]("c1")

    assert result == [{"user_message": "hi"}]
    assert client.calls == [("get_json", "/chats/c1/download", {"params": None})]


def test_delete_chat_calls_delete_and_confirms():
    client, tools = _tools()

    result = tools["delete_chat"]("c1")

    assert result == {"status": "deleted", "chat_id": "c1"}
    assert client.calls == [("delete", "/chats/c1", {})]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_chats.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'transcribemcp.tools.chats'`

- [ ] **Step 3: Implement `transcribemcp/tools/chats.py`**

```python
def register(mcp, client):
    @mcp.tool()
    def list_chats(scope: str, scope_id: str) -> list[dict]:
        """List chats scoped to a workspace or transcription.

        Args:
            scope: Either "workspace" or "transcription".
            scope_id: ID of the workspace or transcription.
        """
        return client.get_json("/chats", params={"scope": scope, "scope_id": scope_id})

    @mcp.tool()
    def create_chat(scope: str, scope_id: str, prompt: str) -> dict:
        """Create a new chat for Q&A over a workspace's or transcription's content.

        Args:
            scope: Either "workspace" or "transcription".
            scope_id: ID of the workspace or transcription.
            prompt: The first user message to start the chat with.
        """
        return client.post_form("/chats", data={"scope": scope, "scope_id": scope_id, "prompt": prompt})

    @mcp.tool()
    def add_chat_message(chat_id: str, prompt: str) -> dict:
        """Add a user message to an existing chat and trigger a new response.

        Args:
            chat_id: The chat's ID.
            prompt: User message to add.
        """
        return client.post_form(f"/chats/{chat_id}/message", data={"prompt": prompt})

    @mcp.tool()
    def get_chat(chat_id: str) -> dict:
        """Get metadata for a chat (not its message history).

        Args:
            chat_id: The chat's ID.
        """
        return client.get_json(f"/chats/{chat_id}")

    @mcp.tool()
    def download_chat(chat_id: str) -> list[dict]:
        """Download the full message history for a chat.

        Args:
            chat_id: The chat's ID.
        """
        return client.get_json(f"/chats/{chat_id}/download")

    @mcp.tool()
    def delete_chat(chat_id: str) -> dict:
        """Delete a chat.

        Args:
            chat_id: The chat's ID.
        """
        client.delete(f"/chats/{chat_id}")
        return {"status": "deleted", "chat_id": chat_id}

    return {
        "list_chats": list_chats,
        "create_chat": create_chat,
        "add_chat_message": add_chat_message,
        "get_chat": get_chat,
        "download_chat": download_chat,
        "delete_chat": delete_chat,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_chats.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add transcribemcp/tools/chats.py tests/tools/test_chats.py
git commit -m "feat: add chat tools (list/create/add_message/get/download/delete)"
```

---

### Task 15: Server Wiring

**Files:**
- Create: `transcribemcp/server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server.py
def test_server_module_imports_and_wires_client(monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_API_KEY", "test-key")
    monkeypatch.setenv("TRANSCRIBE_EMAIL", "user@domain.gov.sg")

    from transcribemcp import server

    assert server.mcp.name == "transcribe"
    assert server.client is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'transcribemcp.server'`

- [ ] **Step 3: Implement `transcribemcp/server.py`**

```python
import httpx
from mcp.server.fastmcp import FastMCP

from .auth import TokenManager
from .client import TranscribeClient
from .config import load_config
from .tools import chats, metadata, minutes, notes, projects, sections, summaries, transcriptions, workspaces

mcp = FastMCP("transcribe")

_config = load_config()
_http_client = httpx.Client(timeout=60.0)
_token_manager = TokenManager(_http_client, _config.base_url, _config.email, _config.api_key)
client = TranscribeClient(_config.base_url, _config.api_version, _token_manager, _http_client)

metadata.register(mcp, client)
workspaces.register(mcp, client)
projects.register(mcp, client)
transcriptions.register(mcp, client)
summaries.register(mcp, client)
sections.register(mcp, client)
minutes.register(mcp, client)
notes.register(mcp, client)
chats.register(mcp, client)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_server.py -v`
Expected: 1 passed

- [ ] **Step 5: Run the full test suite to confirm nothing regressed**

Run: `pytest -v`
Expected: all tests pass (46 total across Tasks 2-15: 4 config + 6 auth + 8 client + 1 metadata + 4 workspaces + 6 projects + 9 transcriptions + 4 summaries + 2 sections + 3 minutes + 2 notes + 6 chats + 1 server)

- [ ] **Step 6: Commit**

```bash
git add transcribemcp/server.py tests/test_server.py
git commit -m "feat: wire FastMCP server with all tool modules"
```

---

### Task 16: Packaging & Registration Docs

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read the current README**

Run: `cat README.md` (currently just the repo name and one-line description)

- [ ] **Step 2: Replace README.md contents**

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add setup and MCP registration instructions"
```

---

### Task 17: Manual End-to-End Verification (checklist, not automated)

This requires a real Transcribe API key and email — there's no test/sandbox credential available in this environment, so this task is a manual checklist for whoever has access to a whitelisted Transcribe account. It is not part of the automated test suite.

- [ ] **Step 1: Register the server locally**

```bash
export TRANSCRIBE_API_KEY=<real key>
export TRANSCRIBE_EMAIL=<real email>
claude mcp add transcribe -- transcribemcp
```

- [ ] **Step 2: Inspect the server with the MCP inspector**

```bash
npx @modelcontextprotocol/inspector transcribemcp
```

Confirm all 29 tools listed in the design spec appear (`get_engines`, workspace/project/transcription CRUD, summaries, sections, minutes, notes, chats).

- [ ] **Step 3: Walk the golden path manually**

1. `create_workspace(name="smoke-test")` → note the returned `id`
2. `create_project(name="smoke-test", workspace_id=<id>, audio_path="<a real short wav file>", sensitivity="Non-Sensitive", classification="Official Open")` → note the returned `id`
3. `get_engines(type="batch")` → pick an English engine option
4. `create_transcription(project_id=<id>, engine_options=<chosen option>)` → note the returned `id`
5. Poll `get_transcription(transcription_id=<id>)` until `status` is `"Success"`
6. `download_transcript(transcription_id=<id>, variant="latest")` → confirm transcript text is returned
7. `generate_summary(transcription_id=<id>, prompt="Summarize this in one sentence")`, then poll `get_summary` until `summary` is non-null, then `download_summary`

- [ ] **Step 4: Confirm cleanup tools work**

`delete_transcription`, then `delete_project` — confirm both return `{"status": "deleted", ...}` and no longer appear in `list_transcriptions` / `list_projects`.

- [ ] **Step 5: Record results**

Note any deviations from expected behavior (e.g., actual field names differing from the Postman collection's captured examples, since those examples may be stale) as follow-up issues rather than silently patching around them.

---

## Self-Review Notes

- **Spec coverage:** every in-scope item from the design spec's "Tool list" section has a corresponding task (Tasks 6-14). Auth, client, config, and server wiring match the spec's "Architecture" section (Tasks 2-4, 15). Testing approach matches the spec's "Testing" section (respx-mocked HTTP at the client layer; FakeTranscribeClient at the tool layer, which is a refinement of "mock the Transcribe API" scoped to avoid redundant HTTP mocking in 29 near-identical tool tests). Packaging matches the spec's "Packaging" section (Task 16).
- **Spec gap found and resolved:** the spec didn't account for `POST /auth/tokens` requiring an `email` field. Resolved by adding `TRANSCRIBE_EMAIL` as a second required env var — called out explicitly at the top of this plan and in Task 2/16.
- **Type consistency:** `engine_options: dict` (Task 9) matches the shape returned by `get_engines` (Task 6) — both are the raw per-engine dict from `GET /engines`, e.g. `{"engine": "google", "model": "latest_long", ...}`. `sections: list[dict]` (Task 11) matches `{"name": str, "time": float}` shape used consistently in both `get_sections` and `update_sections`. All `download_*` tools return decoded `str`; all `delete_*` tools return `{"status": "deleted", "<id-field>": <id>}` consistently across projects/transcriptions/chats.
