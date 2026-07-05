from typing import Any

import httpx

from .auth import TokenManager


class TranscribeAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Transcribe API error {status_code}: {message}")


class TranscribeClient:
    def __init__(
        self,
        base_url: str,
        api_version: str,
        token_manager: TokenManager,
        http_client: httpx.Client,
    ):
        self._base_url = base_url
        self._api_version = api_version
        self._tokens = token_manager
        self._http = http_client

    def _headers(self) -> dict:
        return {
            "Accept": f"version={self._api_version}",
            "Authorization": f"Bearer {self._tokens.get_token()}",
        }

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self._base_url}{path}"
        response = self._http.request(method, url, headers=self._headers(), **kwargs)
        if response.status_code == 401:
            self._tokens.invalidate()
            response = self._http.request(method, url, headers=self._headers(), **kwargs)
        if response.status_code >= 400:
            raise TranscribeAPIError(response.status_code, _error_message(response))
        return response

    def get_json(self, path: str, params: dict | None = None) -> Any:
        response = self.request("GET", path, params=params)
        return _parse_json(response)

    def post_form(self, path: str, data: dict | None = None, files: dict | None = None) -> Any:
        response = self.request("POST", path, data=data, files=files)
        return _parse_json(response)

    def put_json(self, path: str, json_body: dict | None = None) -> Any:
        response = self.request("PUT", path, json=json_body)
        return _parse_json(response)

    def delete(self, path: str) -> None:
        self.request("DELETE", path)

    def download(self, path: str, params: dict | None = None) -> bytes:
        response = self.request("GET", path, params=params)
        return response.content


def _parse_json(response: httpx.Response) -> Any:
    if response.status_code == 204 or not response.content:
        return None
    return response.json()


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
        return body.get("message", response.text)
    except ValueError:
        return response.text
