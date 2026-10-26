"""Centralised configuration, read from environment variables / ``.env``."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from urllib.parse import urlparse

from dotenv import load_dotenv

from pixelforge.utils.errors import ConfigError

DEFAULT_MODEL = "gpt-4o"
DEFAULT_TOKEN_PARAM = "max_completion_tokens"
_MB = 1024 * 1024


@dataclass(frozen=True)
class Settings:
    """Runtime settings. ``api_key`` is excluded from ``repr`` on purpose."""

    api_key: str | None = field(default=None, repr=False)
    base_url: str | None = None
    model: str = DEFAULT_MODEL
    timeout_seconds: int = 120
    max_output_tokens: int = 16000
    max_upload_bytes: int = 10 * _MB
    max_pixels: int = 40_000_000
    max_dimension: int = 8000
    min_dimension: int = 64
    max_send_side: int = 2000
    max_format_retries: int = 1
    token_param: str = DEFAULT_TOKEN_PARAM
    log_level: str = "INFO"

    @property
    def has_api_key(self) -> bool:
        """True when a non-empty API key is available."""
        return bool(self.api_key and self.api_key.strip())

    @property
    def provider_host(self) -> str:
        """Host that receives screenshots (shown in the privacy notice)."""
        if self.base_url:
            return urlparse(self.base_url).netloc or self.base_url
        return "api.openai.com"

    def with_api_key(self, api_key: str | None) -> Settings:
        """Return a copy using ``api_key`` when it is non-empty."""
        key = (api_key or "").strip()
        return replace(self, api_key=key) if key else self


def _int_env(env: Mapping[str, str], name: str, default: int, lo: int, hi: int) -> int:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be an integer, got {raw!r}.") from None
    if not lo <= value <= hi:
        raise ConfigError(f"{name} must be between {lo} and {hi}, got {value}.")
    return value


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build ``Settings`` from ``env`` (defaults to ``os.environ`` after loading ``.env``)."""
    if env is None:
        load_dotenv(override=False)
        env = os.environ
    api_key = env.get("OPENAI_API_KEY", "").strip() or None
    if api_key and api_key.lower().startswith(("your_", "your-", "sk-your")):
        api_key = None  # untouched placeholder copied from .env.example
    return Settings(
        api_key=api_key,
        base_url=env.get("PIXELFORGE_BASE_URL", "").strip() or None,
        model=env.get("PIXELFORGE_MODEL", "").strip() or DEFAULT_MODEL,
        timeout_seconds=_int_env(env, "PIXELFORGE_TIMEOUT_SECONDS", 120, 5, 900),
        max_output_tokens=_int_env(env, "PIXELFORGE_MAX_OUTPUT_TOKENS", 16000, 1000, 128000),
        max_upload_bytes=_int_env(env, "PIXELFORGE_MAX_UPLOAD_MB", 10, 1, 50) * _MB,
        max_pixels=_int_env(env, "PIXELFORGE_MAX_PIXELS", 40_000_000, 10_000, 178_000_000),
        max_dimension=_int_env(env, "PIXELFORGE_MAX_DIMENSION", 8000, 256, 20000),
        min_dimension=_int_env(env, "PIXELFORGE_MIN_DIMENSION", 64, 1, 1000),
        max_send_side=_int_env(env, "PIXELFORGE_MAX_SEND_SIDE", 2000, 256, 8000),
        max_format_retries=_int_env(env, "PIXELFORGE_MAX_FORMAT_RETRIES", 1, 0, 3),
        token_param=env.get("PIXELFORGE_TOKEN_PARAM", "").strip() or DEFAULT_TOKEN_PARAM,
        log_level=env.get("PIXELFORGE_LOG_LEVEL", "INFO").strip().upper() or "INFO",
    )
