from pathlib import Path


def register(mcp, client):
    @mcp.tool()
    def list_projects(
        workspace_id: str | None = None,
        name: str | None = None,
        owner: str | None = None,
        tag: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[dict]:
        """List transcription projects, optionally filtered.

        Args:
            workspace_id: Only list projects in this workspace.
            name: Filter by project name.
            owner: Filter by owner email.
            tag: Filter by project tag.
            limit: Max projects to return (1-50).
            offset: Pagination offset.
        """
        params = {"limit": limit, "offset": offset}
        if workspace_id is not None:
            params["workspace_id"] = workspace_id
        if name is not None:
            params["name"] = name
        if owner is not None:
            params["owner"] = owner
        if tag is not None:
            params["tag"] = tag
        return client.get_json("/projects", params=params)

    @mcp.tool()
    def get_project(project_id: str) -> dict:
        """Get a single transcription project by ID.

        Args:
            project_id: The project's ID.
        """
        return client.get_json(f"/projects/{project_id}")

    @mcp.tool()
    def create_project(
        name: str,
        workspace_id: str,
        audio_path: str,
        sensitivity: str,
        classification: str,
        languages: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Create a transcription project by uploading a local audio file.

        Args:
            name: Name of the project.
            workspace_id: ID of the workspace to create the project under.
            audio_path: Local filesystem path to the audio file to upload.
            sensitivity: One of "Non-Sensitive", "Sensitive Normal", "Sensitive High".
            classification: One of "Official Open", "Official Closed", "Restricted".
            languages: Optional list of language tags for project metadata.
            tags: Optional list of free-text tags for project metadata.
        """
        path = Path(audio_path)
        data = {
            "name": name,
            "workspace_id": workspace_id,
            "sensitivity": sensitivity,
            "classification": classification,
        }
        if languages:
            data["languages"] = languages
        if tags:
            data["tags"] = tags
        with path.open("rb") as audio_file:
            return client.post_form(
                "/projects",
                data=data,
                files={"audio": (path.name, audio_file, "application/octet-stream")},
            )

    @mcp.tool()
    def delete_project(project_id: str) -> dict:
        """Permanently delete a transcription project and all its transcriptions.

        Args:
            project_id: The project's ID.
        """
        client.delete(f"/projects/{project_id}")
        return {"status": "deleted", "project_id": project_id}

    return {
        "list_projects": list_projects,
        "get_project": get_project,
        "create_project": create_project,
        "delete_project": delete_project,
    }
