def register(mcp, client):
    @mcp.tool()
    def get_engines(type: str) -> dict:
        """List transcription engines and options available for a job type.

        Args:
            type: Either "batch" or "live".
        """
        return client.get_json("/engines", params={"type": type})

    return {"get_engines": get_engines}
