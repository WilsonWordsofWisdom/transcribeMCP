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
