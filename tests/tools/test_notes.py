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
