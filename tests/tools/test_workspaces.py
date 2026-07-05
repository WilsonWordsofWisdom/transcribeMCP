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
