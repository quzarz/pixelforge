"""Exception hierarchy and secret redaction helpers.

Every error that is safe to show to the user derives from ``PixelForgeError``.
Its ``user_message`` never contains secrets.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_KEY_PATTERN = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9._\-]{8,})")
_REDACTED = "[REDACTED]"


class PixelForgeError(Exception):
    """Base class for errors that can be displayed to the user."""

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return self.user_message

    @property
    def user_message(self) -> str:
        """Message plus an actionable hint, ready for display."""
        return f"{self.message} {self.hint}".strip()


class ConfigError(PixelForgeError):
    """Invalid or missing configuration."""


class MissingApiKeyError(ConfigError):
    """No API key is configured."""


class ImageValidationError(PixelForgeError):
    """The uploaded image is unsupported, malformed or too large."""


class GenerationError(PixelForgeError):
    """The model call failed (network, quota, timeout, ...)."""


class InvalidModelResponseError(GenerationError):
    """The model answered, but not with usable structured output."""


class CodeValidationError(PixelForgeError):
    """Generated files failed validation (unsafe path, too large, ...)."""


class ExportError(PixelForgeError):
    """Building the ZIP export failed."""


def redact_secrets(text: str, secrets: Iterable[str | None] = ()) -> str:
    """Replace known secrets and key-like tokens in ``text``."""
    for secret in secrets:
        if secret and len(secret) >= 4:
            text = text.replace(secret, _REDACTED)
    return _KEY_PATTERN.sub(_REDACTED, text)
