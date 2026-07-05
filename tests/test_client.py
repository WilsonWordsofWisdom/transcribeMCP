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
