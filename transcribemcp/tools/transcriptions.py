import json


def register(mcp, client):
    @mcp.tool()
    def list_transcriptions(
        project_id: str | None = None,
        workspace_id: str | None = None,
        status: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[dict]:
        """List batch transcription jobs, optionally filtered.

        Args:
            project_id: Only list transcriptions for this project.
            workspace_id: Only list transcriptions in this workspace.
            status: Filter by status, e.g. "In Queue", "In Progress", "Success", "Fail".
            limit: Max transcriptions to return (1-50).
            offset: Pagination offset.
        """
        params = {"limit": limit, "offset": offset, "type": "batch"}
        if project_id is not None:
            params["project_id"] = project_id
        if workspace_id is not None:
            params["workspace_id"] = workspace_id
        if status is not None:
            params["status"] = status
        return client.get_json("/transcriptions", params=params)

    @mcp.tool()
    def get_transcription(transcription_id: str) -> dict:
        """Get a transcription job's current status and metadata.

        Args:
            transcription_id: The transcription's ID.
        """
        return client.get_json(f"/transcriptions/{transcription_id}")

    @mcp.tool()
    def create_transcription(
        project_id: str,
        engine_options: dict,
        has_diarization: bool = False,
    ) -> dict:
        """Start a batch transcription job for a project.

        Args:
            project_id: ID of the project to transcribe (its audio file is used).
            engine_options: One of the engine option objects returned by get_engines,
                e.g. {"engine": "google", "model": "latest_long", "language": "english", ...}.
            has_diarization: Whether to enable speaker diarization.
        """
        return client.post_form(
            "/transcriptions",
            data={
                "project_id": project_id,
                "engine": engine_options["engine"],
                "options": json.dumps(engine_options),
                "type": "batch",
                "has_diarization": str(has_diarization).lower(),
            },
        )

    @mcp.tool()
    def delete_transcription(transcription_id: str) -> dict:
        """Permanently delete a transcription job (its project is unaffected).

        Args:
            transcription_id: The transcription's ID.
        """
        client.delete(f"/transcriptions/{transcription_id}")
        return {"status": "deleted", "transcription_id": transcription_id}

    @mcp.tool()
    def download_transcript(transcription_id: str, variant: str = "latest") -> str:
        """Download a transcription's transcript text.

        Args:
            transcription_id: The transcription's ID.
            variant: Which transcript to download: "raw", "uf" (user-formatted), or
                "latest" (the most recently edited version).
        """
        if variant not in ("raw", "uf", "latest"):
            raise ValueError('variant must be one of "raw", "uf", "latest"')
        content = client.download(f"/transcriptions/{transcription_id}/{variant}_transcript/download")
        return content.decode("utf-8")

    return {
        "list_transcriptions": list_transcriptions,
        "get_transcription": get_transcription,
        "create_transcription": create_transcription,
        "delete_transcription": delete_transcription,
        "download_transcript": download_transcript,
    }
