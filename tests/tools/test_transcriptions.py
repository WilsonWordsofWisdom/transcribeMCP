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
