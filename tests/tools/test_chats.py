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
