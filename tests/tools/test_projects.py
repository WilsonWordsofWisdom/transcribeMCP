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
