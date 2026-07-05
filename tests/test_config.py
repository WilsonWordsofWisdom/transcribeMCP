import pytest

from transcribemcp.config import ConfigError, load_config


def test_load_config_reads_required_env_vars_and_applies_defaults(monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_API_KEY", "test-api-key")
    monkeypatch.setenv("TRANSCRIBE_EMAIL", "user@domain.gov.sg")
    monkeypatch.delenv("TRANSCRIBE_BASE_URL", raising=False)
    monkeypatch.delenv("TRANSCRIBE_API_VERSION", raising=False)

    config = load_config()

    assert config.api_key == "test-api-key"
    assert config.email == "user@domain.gov.sg"
    assert config.base_url == "https://core.transcribe.gov.sg"
    assert config.api_version == "3.0"


def test_load_config_honours_overridden_base_url_and_version(monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_API_KEY", "test-api-key")
    monkeypatch.setenv("TRANSCRIBE_EMAIL", "user@domain.gov.sg")
    monkeypatch.setenv("TRANSCRIBE_BASE_URL", "https://staging.transcribe.gov.sg")
    monkeypatch.setenv("TRANSCRIBE_API_VERSION", "2.1")

    config = load_config()

    assert config.base_url == "https://staging.transcribe.gov.sg"
    assert config.api_version == "2.1"


def test_load_config_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("TRANSCRIBE_API_KEY", raising=False)
    monkeypatch.setenv("TRANSCRIBE_EMAIL", "user@domain.gov.sg")

    with pytest.raises(ConfigError, match="TRANSCRIBE_API_KEY"):
        load_config()


def test_load_config_raises_when_email_missing(monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_API_KEY", "test-api-key")
    monkeypatch.delenv("TRANSCRIBE_EMAIL", raising=False)

    with pytest.raises(ConfigError, match="TRANSCRIBE_EMAIL"):
        load_config()
