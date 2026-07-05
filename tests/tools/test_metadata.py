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
