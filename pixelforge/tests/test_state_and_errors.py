import logging

import pytest

from pixelforge.services.demo import demo_project, demo_screenshot_png
from pixelforge.state import SOURCE_AI, SOURCE_DEMO, Workspace
from pixelforge.utils.errors import ImageValidationError, PixelForgeError, redact_secrets
from pixelforge.utils.logging_config import get_logger, setup_logging


def test_workspace_lifecycle(make_image, settings):
    ws = Workspace()
    ws.set_image(make_image(), "a.png", settings)
    assert ws.image and ws.image_info.width == 400 and ws.project is None
    ws.set_project(demo_project(), SOURCE_AI, "m")
    revision = ws.revision
    ws.set_image(make_image(size=(500, 500)), "b.png", settings)
    assert ws.project is None  # a new image invalidates the old result
    ws.session_api_key = "sk-keep-me-12345"
    ws.set_project(demo_project(), SOURCE_AI)
    ws.error = "boom"
    ws.reset()
    assert ws.image is None and ws.project is None and ws.error is None
    assert ws.session_api_key == "sk-keep-me-12345" and ws.revision > revision and ws.uploader_nonce == 1


def test_invalid_image_does_not_replace_current(make_image, settings):
    ws = Workspace()
    ws.set_image(make_image(), "a.png", settings)
    with pytest.raises(ImageValidationError):
        ws.set_image(b"junk", "b.png", settings)
    assert ws.image_name == "a.png"


def test_demo_loads_without_api(settings):
    ws = Workspace()
    ws.load_demo(settings)
    assert ws.project_source == SOURCE_DEMO and "index.html" in ws.project.files and ws.image
    assert demo_screenshot_png()[:8] == b"\x89PNG\r\n\x1a\n"
    assert demo_project().warnings == []  # demo passes the production sanitiser untouched


def test_repeated_set_project_bumps_revision(settings):
    ws = Workspace()
    ws.set_project(demo_project(), SOURCE_AI)
    first = ws.revision
    ws.set_project(demo_project(), SOURCE_AI)
    assert ws.revision == first + 1


def test_redaction():
    text = "key sk-proj-ABCDEFGH12345 and Bearer abcdefghijkl1234 and mysecret"
    out = redact_secrets(text, ["mysecret"])
    assert "ABCDEFGH" not in out and "abcdefghijkl" not in out and "mysecret" not in out


def test_user_message_joins_hint():
    assert PixelForgeError("A.", hint="B.").user_message == "A. B."


def test_logging_filter_redacts_message_and_traceback():
    from pixelforge.utils.logging_config import RedactingFilter

    record = logging.LogRecord("pixelforge.t", logging.WARNING, __file__, 1, "token %s leaked", ("sk-live-ABCDEFGHIJKL",), None)
    assert RedactingFilter().filter(record)
    assert "ABCDEFGHIJKL" not in record.getMessage() and "[REDACTED]" in record.getMessage()
    try:
        raise ValueError("inner sk-live-ZZZZZZZZZZZZ")
    except ValueError:
        import sys

        exc_record = logging.LogRecord("pixelforge.t", logging.ERROR, __file__, 1, "failed", None, sys.exc_info())
    RedactingFilter().filter(exc_record)
    assert "ZZZZZZZZZZZZ" not in exc_record.exc_text


def test_setup_logging_is_idempotent():
    from pixelforge.utils.logging_config import RedactingFilter

    logger = setup_logging("INFO")
    setup_logging("DEBUG")
    ours = [h for h in logger.handlers if any(isinstance(f, RedactingFilter) for f in h.filters)]
    assert len(ours) == 1
    assert get_logger("x").name == "pixelforge.x"
