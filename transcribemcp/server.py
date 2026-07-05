import httpx
from mcp.server.fastmcp import FastMCP

from .auth import TokenManager
from .client import TranscribeClient
from .config import load_config
from .tools import chats, metadata, minutes, notes, projects, sections, summaries, transcriptions, workspaces

mcp = FastMCP("transcribe")

_config = load_config()
_http_client = httpx.Client(timeout=60.0)
_token_manager = TokenManager(_http_client, _config.base_url, _config.email, _config.api_key)
client = TranscribeClient(_config.base_url, _config.api_version, _token_manager, _http_client)

metadata.register(mcp, client)
workspaces.register(mcp, client)
projects.register(mcp, client)
transcriptions.register(mcp, client)
summaries.register(mcp, client)
sections.register(mcp, client)
minutes.register(mcp, client)
notes.register(mcp, client)
chats.register(mcp, client)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
