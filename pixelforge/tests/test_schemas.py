import pytest
from pydantic import ValidationError

from pixelforge.schemas import Fidelity, GenerationOptions, GenerationResult, Viewport
from tests.conftest import good_payload


def test_valid_result_and_extra_fields_ignored():
    result = GenerationResult.model_validate({**good_payload(), "unexpected": 1})
    assert len(result.files) == 3 and result.title == "Test page"


@pytest.mark.parametrize("bad", [
    {"files": []},
    {"files": [{"path": "", "content": "x"}]},
    {"files": [{"path": "a.html"}]},
    {"files": "nope"},
    {"files": [{"path": "A.html", "content": "x"}, {"path": "a.html", "content": "y"}]},
])
def test_invalid_results_rejected(bad):
    with pytest.raises(ValidationError):
        GenerationResult.model_validate(bad)


def test_missing_files_key_rejected():
    with pytest.raises(ValidationError):
        GenerationResult.model_validate({"title": "x"})


def test_options_defaults_strip_and_limit():
    opts = GenerationOptions(instructions="  hello  ")
    assert opts.instructions == "hello" and opts.fidelity is Fidelity.BALANCED
    with pytest.raises(ValidationError):
        GenerationOptions(instructions="x" * 1001)


def test_viewport_widths():
    assert [v.width for v in Viewport] == [1440, 768, 390]
