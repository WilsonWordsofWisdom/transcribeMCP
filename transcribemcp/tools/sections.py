def register(mcp, client):
    @mcp.tool()
    def get_sections(transcription_id: str) -> dict:
        """Get the section markers (chapter-like timestamps) for a transcription.

        Args:
            transcription_id: The transcription's ID.
        """
        return client.get_json(f"/transcriptions/{transcription_id}/sections")

    @mcp.tool()
    def update_sections(transcription_id: str, sections: list[dict]) -> dict:
        """Replace the section markers for a transcription.

        Args:
            transcription_id: The transcription's ID.
            sections: List of {"name": str, "time": float} objects, fully replacing
                the existing section list.
        """
        return client.put_json(f"/transcriptions/{transcription_id}/sections", json_body={"sections": sections})

    return {"get_sections": get_sections, "update_sections": update_sections}
