import time

import httpx


class AuthError(Exception):
    pass


class TokenManager:
    """Exchanges a Transcribe API key for a JWT bearer token and keeps it fresh."""

    RENEW_MARGIN_SECONDS = 300
    TOKEN_TTL_SECONDS = 43200  # 12 hours, matches Transcribe's JWT lifetime

    def __init__(self, http_client: httpx.Client, base_url: str, email: str, api_key: str):
        self._http = http_client
        self._base_url = base_url
        self._email = email
        self._api_key = api_key
        self._token: str | None = None
        self._expires_at: float = 0.0

    def get_token(self) -> str:
        if self._token is None:
            self._exchange()
        elif time.monotonic() >= self._expires_at - self.RENEW_MARGIN_SECONDS:
            self._renew()
        return self._token

    def invalidate(self) -> None:
        """Force the next get_token() call to fetch a brand new token."""
        self._token = None

    def _exchange(self) -> None:
        response = self._http.post(
            f"{self._base_url}/auth/tokens",
            params={"service": self._base_url, "expiry": self.TOKEN_TTL_SECONDS},
            json={"email": self._email, "otp": "", "apikey": self._api_key},
        )
        if response.status_code != 200:
            raise AuthError(f"Failed to obtain auth token ({response.status_code}): {response.text}")
        self._token = response.json()["token"]
        self._expires_at = time.monotonic() + self.TOKEN_TTL_SECONDS

    def _renew(self) -> None:
        response = self._http.post(
            f"{self._base_url}/auth/tokens/renew",
            json={"token": self._token},
        )
        if response.status_code != 200:
            self._exchange()
            return
        self._token = response.json()["token"]
        self._expires_at = time.monotonic() + self.TOKEN_TTL_SECONDS
