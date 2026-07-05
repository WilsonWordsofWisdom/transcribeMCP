def register(mcp, client):
    @mcp.tool()
    def generate_minutes(transcription_id: str, format: str = "text_minutes") -> dict:
        """Start a meeting-minutes generation job for a completed transcription.

        Args:
            transcription_id: The transcription's ID.
            format: Minutes format, e.g. "text_minutes".
        """
        return client.post_form(f"/transcriptions/{transcription_id}/minutes", data={"format": format})

    @mcp.tool()
    def get_minutes(transcription_id: str, format: str = "text_minutes") -> dict | None:
        """Get minutes generation status/metadata for a transcription.

        Args:
            transcription_id: The transcription's ID.
            format: Minutes format to check, e.g. "text_minutes".

        Returns:
            None if no minutes have been generated yet for that format.
        """
        return client.get_json(f"/transcriptions/{transcription_id}/minutes", params={"format": format})

    @mcp.tool()
    def download_minutes(transcription_id: str, format: str = "text_minutes") -> str:
        """Download the generated minutes text for a transcription.

        Args:
            transcription_id: The transcription's ID.
            format: Minutes format to download, e.g. "text_minutes".
        """
        content = client.download(
            f"/transcriptions/{transcription_id}/minutes/download", params={"format": format}
        )
        return content.decode("utf-8")

    return {
        "generate_minutes": generate_minutes,
        "get_minutes": get_minutes,
        "download_minutes": download_minutes,
    }
