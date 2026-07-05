import httpx
import pytest
import respx

from transcribemcp.auth import AuthError, TokenManager

BASE_URL = "https://core.transcribe.gov.sg"


@respx.mock
def test_get_token_exchanges_api_key_on_first_call():
    route = respx.post(f"{BASE_URL}/auth/tokens").mock(
        return_value=httpx.Response(200, json={"token": "jwt-1"})
    )
    manager = TokenManager(httpx.Client(), BASE_URL, "user@domain.gov.sg", "api-key-1")

    token = manager.get_token()

    assert token == "jwt-1"
    assert route.called
    sent_body = route.calls.last.request.content
    assert b"api-key-1" in sent_body
    assert b"user@domain.gov.sg" in sent_body


@respx.mock
def test_get_token_reuses_cached_token_before_expiry():
    route = respx.post(f"{BASE_URL}/auth/tokens").mock(
        return_value=httpx.Response(200, json={"token": "jwt-1"})
    )
    manager = TokenManager(httpx.Client(), BASE_URL, "user@domain.gov.sg", "api-key-1")

    first = manager.get_token()
    second = manager.get_token()

    assert first == second == "jwt-1"
    assert route.call_count == 1


@respx.mock
def test_get_token_renews_when_close_to_expiry():
    respx.post(f"{BASE_URL}/auth/tokens").mock(
        return_value=httpx.Response(200, json={"token": "jwt-1"})
    )
    renew_route = respx.post(f"{BASE_URL}/auth/tokens/renew").mock(
        return_value=httpx.Response(200, json={"token": "jwt-2"})
    )
    manager = TokenManager(httpx.Client(), BASE_URL, "user@domain.gov.sg", "api-key-1")
    manager.get_token()
    manager._expires_at = 0.0  # simulate a token about to expire

    token = manager.get_token()

    assert token == "jwt-2"
    assert renew_route.called


@respx.mock
def test_get_token_falls_back_to_exchange_when_renew_fails():
    exchange_route = respx.post(f"{BASE_URL}/auth/tokens").mock(
        return_value=httpx.Response(200, json={"token": "jwt-1"})
    )
    respx.post(f"{BASE_URL}/auth/tokens/renew").mock(
        return_value=httpx.Response(400, json={"message": "expired"})
    )
    manager = TokenManager(httpx.Client(), BASE_URL, "user@domain.gov.sg", "api-key-1")
    manager.get_token()
    manager._expires_at = 0.0

    token = manager.get_token()

    assert token == "jwt-1"
    assert exchange_route.call_count == 2


@respx.mock
def test_invalidate_forces_new_exchange_on_next_call():
    route = respx.post(f"{BASE_URL}/auth/tokens").mock(
        side_effect=[
            httpx.Response(200, json={"token": "jwt-1"}),
            httpx.Response(200, json={"token": "jwt-2"}),
        ]
    )
    manager = TokenManager(httpx.Client(), BASE_URL, "user@domain.gov.sg", "api-key-1")
    manager.get_token()

    manager.invalidate()
    token = manager.get_token()

    assert token == "jwt-2"
    assert route.call_count == 2


@respx.mock
def test_exchange_raises_auth_error_on_failure():
    respx.post(f"{BASE_URL}/auth/tokens").mock(
        return_value=httpx.Response(400, json={"message": "Invalid API key."})
    )
    manager = TokenManager(httpx.Client(), BASE_URL, "user@domain.gov.sg", "bad-key")

    with pytest.raises(AuthError, match="Invalid API key"):
        manager.get_token()
