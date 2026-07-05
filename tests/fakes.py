import io


class FakeMCP:
    """Stub for FastMCP: `.tool()` returns the function unchanged, mirroring the
    real `mcp.server.fastmcp.FastMCP.tool()` decorator's identity behavior."""

    def __init__(self):
        self.registered = {}

    def tool(self):
        def decorator(fn):
            self.registered[fn.__name__] = fn
            return fn

        return decorator


class FakeTranscribeClient:
    """Records every call made against it and returns pre-programmed responses,
    standing in for TranscribeClient in tool-level unit tests."""

    def __init__(self):
        self.calls: list[tuple] = []
        self._responses: dict[tuple, object] = {}

    def set_response(self, method: str, path: str, response: object) -> None:
        self._responses[(method, path)] = response

    def _record_and_respond(self, method: str, path: str, **kwargs):
        self.calls.append((method, path, kwargs))
        return self._responses.get((method, path))

    def get_json(self, path, params=None):
        return self._record_and_respond("get_json", path, params=params)

    def post_form(self, path, data=None, files=None):
        if files is not None:
            snapshot = {}
            for key, value in files.items():
                filename, file_obj, content_type = value
                content = file_obj.read() if hasattr(file_obj, "read") else file_obj
                snapshot[key] = (filename, io.BytesIO(content), content_type)
            files = snapshot
        return self._record_and_respond("post_form", path, data=data, files=files)

    def put_json(self, path, json_body=None):
        return self._record_and_respond("put_json", path, json_body=json_body)

    def delete(self, path):
        return self._record_and_respond("delete", path)

    def download(self, path, params=None):
        return self._record_and_respond("download", path, params=params)
