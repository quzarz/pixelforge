import pytest

from pixelforge.config import DEFAULT_MODEL, load_settings
from pixelforge.utils.errors import ConfigError


def test_defaults_without_key():
    s = load_settings({})
    assert not s.has_api_key and s.model == DEFAULT_MODEL and s.provider_host == "api.openai.com"


def test_reads_environment():
    s = load_settings({"OPENAI_API_KEY": "sk-abc12345678", "PIXELFORGE_MODEL": "m", "PIXELFORGE_MAX_UPLOAD_MB": "2",
                       "PIXELFORGE_BASE_URL": "https://proxy.example.com/v1"})
    assert s.has_api_key and s.model == "m" and s.max_upload_bytes == 2 * 1024 * 1024
    assert s.provider_host == "proxy.example.com"


def test_placeholder_key_is_ignored():
    assert not load_settings({"OPENAI_API_KEY": "your_api_key_here"}).has_api_key


@pytest.mark.parametrize("name,value", [("PIXELFORGE_TIMEOUT_SECONDS", "abc"), ("PIXELFORGE_TIMEOUT_SECONDS", "1"), ("PIXELFORGE_MAX_UPLOAD_MB", "999")])
def test_invalid_numbers_raise_config_error(name, value):
    with pytest.raises(ConfigError, match=name):
        load_settings({name: value})


def test_repr_hides_key(settings):
    assert "sk-test" not in repr(settings)


def test_with_api_key_ignores_blank(settings):
    assert settings.with_api_key("  ").api_key == settings.api_key
    assert settings.with_api_key("sk-new-key-1234").api_key == "sk-new-key-1234"
