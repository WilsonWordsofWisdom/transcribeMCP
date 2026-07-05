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
