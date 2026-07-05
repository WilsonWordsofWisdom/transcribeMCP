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
