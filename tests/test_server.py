def test_server_module_imports_and_wires_client(monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_API_KEY", "test-key")
    monkeypatch.setenv("TRANSCRIBE_EMAIL", "user@domain.gov.sg")

    from transcribemcp import server

    assert server.mcp.name == "transcribe"
    assert server.client is not None
