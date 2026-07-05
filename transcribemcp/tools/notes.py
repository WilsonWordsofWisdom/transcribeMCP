def register(mcp, client):
    @mcp.tool()
    def get_notes(transcription_id: str) -> dict | None:
        """Get the free-text notes attached to a transcription.

        Args:
            transcription_id: The transcription's ID.

        Returns:
            None if no notes exist yet.
        """
        return client.get_json(f"/transcriptions/{transcription_id}/notes")

    @mcp.tool()
    def append_note(transcription_id: str, text: str) -> dict:
        """Append text to a transcription's notes.

        Args:
            transcription_id: The transcription's ID.
            text: Text to append.
        """
        return client.post_form(f"/transcriptions/{transcription_id}/append_text", data={"text": text})

    return {"get_notes": get_notes, "append_note": append_note}
