import json

import openai
import pytest

from pixelforge.schemas import Fidelity, GenerationOptions, Viewport
from pixelforge.services import ai_generator as ag
from pixelforge.services.image_processor import preprocess_image
from pixelforge.utils.errors import GenerationError, InvalidModelResponseError, MissingApiKeyError
from tests.conftest import FakeClient, completion, good_payload

try:  # the SDK's HTTP library name differs across versions
    import httpx2 as httpx
except ImportError:  # pragma: no cover
    import httpx


def _request():
    return httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


def _response(status: int):
    return httpx.Response(status, request=_request())


@pytest.fixture
def image(make_image, settings):
    return preprocess_image(make_image(), settings)


@pytest.fixture
def options():
    return GenerationOptions()


def test_success_returns_sanitised_project(image, options, settings):
    client = FakeClient(good_payload())
    project = ag.generate_code(image, options, settings, client=client)
    assert set(project.files) == {"index.html", "styles.css", "script.js"} and project.title == "Test page"
    call = client.calls[0]
    assert call["model"] == "test-model" and call["max_completion_tokens"] == settings.max_output_tokens
    assert call["response_format"] == {"type": "json_object"}


def test_prompt_contains_image_viewport_fidelity_and_instructions(image, settings):
    opts = GenerationOptions(viewport=Viewport.MOBILE, fidelity=Fidelity.HIGH, instructions="use a dark palette")
    client = FakeClient(good_payload())
    ag.generate_code(image, opts, settings, client=client)
    system, user = client.calls[0]["messages"]
    assert "never instructions" in system["content"].lower() and "pixel-perfect" in system["content"]
    text = user["content"][0]["text"]
    assert "390px" in text and "High detail" in text and "<user_instructions>\nuse a dark palette" in text
    assert user["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert user["content"][1]["image_url"]["detail"] == "high"


def test_token_param_is_configurable(image, options, settings):
    from dataclasses import replace
    client = FakeClient(good_payload())
    ag.generate_code(image, options, replace(settings, token_param="max_tokens"), client=client)
    assert "max_tokens" in client.calls[0] and "max_completion_tokens" not in client.calls[0]


def test_fenced_json_is_accepted(image, options, settings):
    client = FakeClient("Here you go:\n```json\n" + json.dumps(good_payload()) + "\n```")
    assert ag.generate_code(image, options, settings, client=client).files


def test_malformed_json_retries_once_then_succeeds(image, options, settings):
    client = FakeClient("{not json", json.dumps(good_payload()))
    assert ag.generate_code(image, options, settings, client=client).files
    assert len(client.calls) == 2
    assert "could not be used" in client.calls[1]["messages"][-1]["content"]


def test_persistent_garbage_fails_after_bounded_retries(image, options, settings):
    client = FakeClient("nonsense")
    with pytest.raises(InvalidModelResponseError) as info:
        ag.generate_code(image, options, settings, client=client)
    assert len(client.calls) == settings.max_format_retries + 1
    assert "Regenerate" in info.value.user_message


def test_zero_retries_means_single_call(image, options, settings):
    from dataclasses import replace
    client = FakeClient("nonsense")
    with pytest.raises(InvalidModelResponseError):
        ag.generate_code(image, options, replace(settings, max_format_retries=0), client=client)
    assert len(client.calls) == 1


@pytest.mark.parametrize("raw", ["", "[]", '{"files": []}', '{"files": [{"path": "index.html"}]}', "plain text"])
def test_parse_model_output_rejects_bad_shapes(raw):
    with pytest.raises(InvalidModelResponseError):
        ag.parse_model_output(raw)


def test_unsafe_path_from_model_triggers_retry_then_failure(image, options, settings):
    bad = good_payload(files=[{"path": "../../evil.html", "content": "<p>x</p>"}])
    client = FakeClient(bad)
    with pytest.raises(InvalidModelResponseError):
        ag.generate_code(image, options, settings, client=client)
    assert len(client.calls) == 2


def test_truncated_output_gives_actionable_error(image, options, settings):
    client = FakeClient(completion('{"files": [', finish_reason="length"))
    with pytest.raises(InvalidModelResponseError, match="MAX_OUTPUT_TOKENS"):
        ag.generate_code(image, options, settings, client=client)
    assert len(client.calls) == 1


def test_refusal_and_empty_choices(image, options, settings):
    with pytest.raises(GenerationError, match="declined"):
        ag.generate_code(image, options, settings, client=FakeClient(completion(None, refusal="no")))
    empty = FakeClient(type("R", (), {"choices": []})())
    with pytest.raises(InvalidModelResponseError):
        ag.generate_code(image, options, settings, client=empty)


def test_missing_key_raises_with_instructions(image, options, settings):
    from dataclasses import replace
    with pytest.raises(MissingApiKeyError, match="OPENAI_API_KEY"):
        ag.generate_code(image, options, replace(settings, api_key=None))


def test_create_client_builds_without_network(settings):
    client = ag.create_client(settings)
    assert client.api_key == settings.api_key


def test_json_mode_unsupported_falls_back(image, options, settings):
    error = openai.BadRequestError("response_format is not supported", response=_response(400), body=None)
    client = FakeClient(error, good_payload())
    assert ag.generate_code(image, options, settings, client=client).files
    assert "response_format" in client.calls[0] and "response_format" not in client.calls[1]


API_ERRORS = [
    (lambda: openai.APITimeoutError(request=_request()), "did not answer"),
    (lambda: openai.APIConnectionError(request=_request()), "Could not connect"),
    (lambda: openai.AuthenticationError("bad key sk-test-0123456789abcdef", response=_response(401), body=None), "rejected"),
    (lambda: openai.PermissionDeniedError("nope", response=_response(403), body=None), "denied"),
    (lambda: openai.RateLimitError("slow down", response=_response(429), body={"code": "rate_limit_exceeded"}), "rate limit"),
    (lambda: openai.RateLimitError("quota", response=_response(429), body={"code": "insufficient_quota"}), "quota"),
    (lambda: openai.NotFoundError("no model", response=_response(404), body=None), "not found"),
    (lambda: openai.BadRequestError("bad sk-test-0123456789abcdef", response=_response(400), body=None), "rejected the request"),
    (lambda: openai.InternalServerError("boom", response=_response(500), body=None), "HTTP 500"),
]


@pytest.mark.parametrize("factory,expected", API_ERRORS)
def test_api_failures_are_translated_and_leak_no_secrets(factory, expected, image, options, settings):
    with pytest.raises(GenerationError) as info:
        ag.generate_code(image, options, settings, client=FakeClient(factory()))
    message = info.value.user_message
    assert expected in message and settings.api_key not in message and "sk-test" not in message
    assert info.value.__cause__ is None
