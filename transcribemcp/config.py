import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://core.transcribe.gov.sg"
DEFAULT_API_VERSION = "3.0"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    api_key: str
    email: str
    base_url: str
    api_version: str


def load_config() -> Config:
    api_key = os.environ.get("TRANSCRIBE_API_KEY")
    if not api_key:
        raise ConfigError("TRANSCRIBE_API_KEY environment variable is required")

    email = os.environ.get("TRANSCRIBE_EMAIL")
    if not email:
        raise ConfigError("TRANSCRIBE_EMAIL environment variable is required")

    base_url = os.environ.get("TRANSCRIBE_BASE_URL", DEFAULT_BASE_URL)
    api_version = os.environ.get("TRANSCRIBE_API_VERSION", DEFAULT_API_VERSION)

    return Config(api_key=api_key, email=email, base_url=base_url, api_version=api_version)
