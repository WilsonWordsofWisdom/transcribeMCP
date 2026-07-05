def register(mcp, client):
    @mcp.tool()
    def list_chats(scope: str, scope_id: str) -> list[dict]:
        """List chats scoped to a workspace or transcription.

        Args:
            scope: Either "workspace" or "transcription".
            scope_id: ID of the workspace or transcription.
        """
        return client.get_json("/chats", params={"scope": scope, "scope_id": scope_id})

    @mcp.tool()
    def create_chat(scope: str, scope_id: str, prompt: str) -> dict:
        """Create a new chat for Q&A over a workspace's or transcription's content.

        Args:
            scope: Either "workspace" or "transcription".
            scope_id: ID of the workspace or transcription.
            prompt: The first user message to start the chat with.
        """
        return client.post_form("/chats", data={"scope": scope, "scope_id": scope_id, "prompt": prompt})

    @mcp.tool()
    def add_chat_message(chat_id: str, prompt: str) -> dict:
        """Add a user message to an existing chat and trigger a new response.

        Args:
            chat_id: The chat's ID.
            prompt: User message to add.
        """
        return client.post_form(f"/chats/{chat_id}/message", data={"prompt": prompt})

    @mcp.tool()
    def get_chat(chat_id: str) -> dict:
        """Get metadata for a chat (not its message history).

        Args:
            chat_id: The chat's ID.
        """
        return client.get_json(f"/chats/{chat_id}")

    @mcp.tool()
    def download_chat(chat_id: str) -> list[dict]:
        """Download the full message history for a chat.

        Args:
            chat_id: The chat's ID.
        """
        return client.get_json(f"/chats/{chat_id}/download")

    @mcp.tool()
    def delete_chat(chat_id: str) -> dict:
        """Delete a chat.

        Args:
            chat_id: The chat's ID.
        """
        client.delete(f"/chats/{chat_id}")
        return {"status": "deleted", "chat_id": chat_id}

    return {
        "list_chats": list_chats,
        "create_chat": create_chat,
        "add_chat_message": add_chat_message,
        "get_chat": get_chat,
        "download_chat": download_chat,
        "delete_chat": delete_chat,
    }
