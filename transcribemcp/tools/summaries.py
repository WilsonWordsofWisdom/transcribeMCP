def register(mcp, client):
    @mcp.tool()
    def generate_summary(transcription_id: str, prompt: str) -> dict:
        """Start an LLM-generated summary job for a completed transcription.

        Args:
            transcription_id: The transcription's ID.
            prompt: Instructions for how the LLM should summarize the transcript.
        """
        return client.post_form(f"/transcriptions/{transcription_id}/summary", data={"prompt": prompt})

    @mcp.tool()
    def get_summary(transcription_id: str) -> dict | None:
        """Get summary generation status/metadata for a transcription.

        Args:
            transcription_id: The transcription's ID.

        Returns:
            None if no summary has been generated yet.
        """
        return client.get_json(f"/transcriptions/{transcription_id}/summary")

    @mcp.tool()
    def download_summary(transcription_id: str) -> str:
        """Download the generated summary text for a transcription.

        Args:
            transcription_id: The transcription's ID.
        """
        content = client.download(f"/transcriptions/{transcription_id}/summary/download")
        return content.decode("utf-8")

    return {
        "generate_summary": generate_summary,
        "get_summary": get_summary,
        "download_summary": download_summary,
    }
