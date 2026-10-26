"""Shared fixtures: settings, image factories and a fake model client."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from pixelforge.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(api_key="sk-test-0123456789abcdef", model="test-model", max_format_retries=1)


@pytest.fixture
def make_image():
    def _make(fmt: str = "PNG", size: tuple[int, int] = (400, 300), mode: str = "RGB", color="white", **save_kwargs) -> bytes:
        buf = io.BytesIO()
        Image.new(mode, size, color).save(buf, format=fmt, **save_kwargs)
        return buf.getvalue()

    return _make


def good_payload(**overrides) -> dict:
    payload = {
        "title": "Test page",
        "files": [
            {"path": "index.html", "content": '<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="styles.css"></head><body><h1>Hi</h1><script src="script.js"></script></body></html>'},
            {"path": "styles.css", "content": "h1{color:red}"},
            {"path": "script.js", "content": "console.log('hi')"},
        ],
        "notes": "approximation",
    }
    payload.update(overrides)
    return payload


def completion(content: str | None, finish_reason: str = "stop", refusal: str | None = None):
    message = SimpleNamespace(content=content, refusal=refusal)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish_reason)])


class FakeClient:
    """Mimics ``client.chat.completions.create`` with scripted replies or exceptions."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, BaseException):
            raise reply
        return reply if not isinstance(reply, (str, dict)) else completion(reply if isinstance(reply, str) else json.dumps(reply))
