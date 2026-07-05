def register(mcp, client):
    @mcp.tool()
    def list_workspaces(
        name: str | None = None,
        owner: str | None = None,
        workspace_type: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[dict]:
        """List workspaces you are a member of, optionally filtered.

        Args:
            name: Filter by workspace name.
            owner: Filter by owner email.
            workspace_type: Filter by "personal" or "shared".
            limit: Max workspaces to return (1-50).
            offset: Pagination offset.
        """
        params = {"limit": limit, "offset": offset}
        if name is not None:
            params["name"] = name
        if owner is not None:
            params["owner"] = owner
        if workspace_type is not None:
            params["type"] = workspace_type
        return client.get_json("/workspaces", params=params)

    @mcp.tool()
    def get_workspace(workspace_id: str) -> dict:
        """Get a single workspace by ID.

        Args:
            workspace_id: The workspace's ID.
        """
        return client.get_json(f"/workspaces/{workspace_id}")

    @mcp.tool()
    def create_workspace(name: str) -> dict:
        """Create a new shared workspace. You become its owner.

        Args:
            name: Name for the new workspace.
        """
        return client.post_form("/workspaces", data={"name": name})

    return {
        "list_workspaces": list_workspaces,
        "get_workspace": get_workspace,
        "create_workspace": create_workspace,
    }
