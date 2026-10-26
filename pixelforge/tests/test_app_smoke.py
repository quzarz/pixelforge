"""End-to-end UI tests using Streamlit's AppTest harness (model API mocked)."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from pixelforge.config import Settings
from pixelforge.services import ai_generator
from pixelforge.state import SOURCE_AI, SOURCE_DEMO, Workspace
from tests.conftest import FakeClient, good_payload


def run(at: AppTest) -> AppTest:
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def button(at: AppTest, fragment: str):
    return next(b for b in at.button if fragment in b.label)


@pytest.fixture
def no_key_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(APP_PATH.parent)


@pytest.fixture
def key_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-0123456789abcdef")
    monkeypatch.chdir(APP_PATH.parent)


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def app() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=30)


def test_launches_without_key_and_explains_configuration(no_key_env, make_image):
    at = run(app())
    assert button(at, "Generate").disabled
    assert any("No API key" in w.value for w in at.sidebar.warning)
    assert not any("st.success" in str(m.value) for m in at.sidebar.markdown)  # no magic-rendered source code
    ws = Workspace()
    ws.set_image(make_image(), "x.png", Settings())
    at.session_state["workspace"] = ws
    run(at)
    assert any("OPENAI_API_KEY" in w.value for w in at.warning)


def test_demo_mode_then_edit_and_reset(no_key_env):
    at = run(app())
    button(at, "offline demo").click()
    run(at)
    ws = at.session_state["workspace"]
    assert ws.project_source == SOURCE_DEMO and ws.project.files["index.html"]
    assert any("not* produced by an AI" in i.value or "not produced" in i.value.replace("*", "") for i in at.info)
    assert len(at.tabs) == 5 and at.text_area  # editable panels present
    first = at.text_area[0]
    first.set_value("<!DOCTYPE html><p>EDITMARKER42</p>")
    run(at)
    # Regression: the preview must reflect an edit in the SAME rerun (editors render before the preview).
    srcdoc = at.get("iframe")[0].proto.srcdoc
    assert "EDITMARKER42" in srcdoc and 'sandbox="allow-scripts"' in srcdoc and "Content-Security-Policy" in srcdoc
    assert at.session_state["workspace"].project.files["index.html"].startswith("<!DOCTYPE html><p>EDITMARKER42")
    button(at, "Clear workspace").click()
    run(at)
    ws = at.session_state["workspace"]
    assert ws.project is None and ws.image is None


def test_generation_success_regeneration_and_reset(key_env, make_image, monkeypatch):
    client = FakeClient(good_payload(title="First"))
    monkeypatch.setattr(ai_generator, "create_client", lambda settings: client)
    at = run(app())
    ws = Workspace()
    ws.set_image(make_image(), "x.png", Settings())
    at.session_state["workspace"] = ws
    run(at)
    button(at, "Generate").click()
    run(at)
    ws = at.session_state["workspace"]
    assert ws.project_source == SOURCE_AI and ws.project.title == "First"
    assert ws.model_used and len(client.calls) == 1
    client.replies = [json.dumps(good_payload(title="Second"))]
    button(at, "Regenerate").click()
    run(at)
    assert at.session_state["workspace"].project.title == "Second" and len(client.calls) == 2


def test_api_failure_shows_error_without_crash_or_secret(key_env, make_image, monkeypatch):
    class Boom:
        def __init__(self):
            self.chat = type("C", (), {"completions": type("X", (), {"create": staticmethod(lambda **k: (_ for _ in ()).throw(RuntimeError("sk-test-0123456789abcdef exploded")))})()})()

    monkeypatch.setattr(ai_generator, "create_client", lambda settings: Boom())
    at = run(app())
    ws = Workspace()
    ws.set_image(make_image(), "x.png", Settings())
    at.session_state["workspace"] = ws
    run(at)
    button(at, "Generate").click()
    run(at)
    errors = " ".join(e.value for e in at.error)
    assert "unexpected" in errors and "sk-test" not in errors
    assert at.session_state["workspace"].project is None
