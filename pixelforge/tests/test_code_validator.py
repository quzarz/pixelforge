import pytest

from pixelforge.schemas import GeneratedFile, GenerationResult
from pixelforge.services import code_validator as cv
from pixelforge.utils.errors import CodeValidationError


@pytest.mark.parametrize("path", ["index.html", "styles.css", "js/app.js", "assets/css/main.css", "./index.html"])
def test_valid_paths(path):
    assert cv.validate_path(path) == path.removeprefix("./")


@pytest.mark.parametrize("path", [
    "../evil.html", "a/../../b.js", "/etc/passwd.html", "C:/x.html", "C:\\x.html", "a\\b.html", "~/x.html",
    "", "   ", ".htaccess.html", "a//b.html", "con.html", "nul.js", "x.py", "x.exe", "x.svg", "no_extension",
    "a/b/c/d.html", "bad name.html", "x\x00.html", "x.html.", "a" * 120 + ".html",
])
def test_unsafe_paths_rejected(path):
    with pytest.raises(CodeValidationError):
        cv.validate_path(path)


def test_strip_code_fences():
    assert cv.strip_code_fences("```html\n<p>x</p>\n```") == "<p>x</p>"
    assert cv.strip_code_fences("<p>no fence</p>") == "<p>no fence</p>"


def html(body: str, local=("styles.css", "script.js")):
    return cv.sanitize_html(f"<!DOCTYPE html><html><head></head><body>{body}</body></html>", set(local))


def test_external_script_and_link_removed_local_kept():
    out, warnings = html('<script src="https://evil.test/x.js"></script><script src="script.js"></script>'
                         '<link rel="stylesheet" href="//cdn.test/a.css"><link rel="stylesheet" href="styles.css">')
    assert "evil.test" not in out and "cdn.test" not in out
    assert 'src="script.js"' in out and 'href="styles.css"' in out and warnings


@pytest.mark.parametrize("tag", [
    '<iframe src="https://x.test"></iframe>', "<iframe src=x>", '<object data="x"></object>', '<embed src="x">',
    '<base href="https://evil.test/">', '<meta http-equiv="refresh" content="0;url=https://evil.test">',
])
def test_dangerous_elements_removed(tag):
    out, warnings = html(tag)
    for needle in ("<iframe", "<object", "<embed", "<base", "http-equiv"):
        assert needle not in out.lower()
    assert warnings


def test_media_references():
    out, _ = html('<img src="https://x.test/a.png" alt="a"><img src="logo.png" alt="b"><img src="data:image/png;base64,AAAA" alt="c">')
    assert "x.test" not in out and "logo.png" not in out and "data:image/png;base64,AAAA" in out and 'alt="a"' in out


def test_javascript_links_neutralised_and_forms_disarmed():
    out, _ = html('<a href="javascript:alert(1)">x</a><a href="https://example.com">ok</a><form action="https://evil.test/p"><input></form>')
    assert "javascript:" not in out and "https://example.com" in out and "evil.test" not in out


def test_css_sanitisation():
    css, warnings = cv.sanitize_css('@import url("https://x.test/a.css");a{background:url(https://x.test/i.png)}'
                                    'b{background:url("data:image/svg+xml;utf8,<svg/>")}c{background:url(#grad)}')
    assert "x.test" not in css and "@import" not in css and "data:image/svg+xml" in css and "#grad" in css and warnings


def test_inline_style_and_style_block_urls_removed():
    out, _ = html('<div style="background:url(https://x.test/a.png)"></div><style>.a{background:url(http://x.test/b.png)}</style>')
    assert "x.test" not in out


def test_document_shell_added():
    out, _ = cv.sanitize_html("<html><head><title>x</title></head><body></body></html>")
    assert out.startswith("<!DOCTYPE html>") and 'name="viewport"' in out


def test_js_scan_flags_risky_code_without_modifying():
    assert len(cv.scan_js("eval('1'); fetch('/x'); document.cookie")) == 3
    assert cv.scan_js("document.querySelector('a')") == []


def result(**files):
    return GenerationResult(files=[GeneratedFile(path=p, content=c) for p, c in files.items()])


def test_sanitize_result_ok_with_fences_stripped():
    project = cv.sanitize_result(GenerationResult(files=[
        GeneratedFile(path="index.html", content="```html\n<html><head></head><body>x</body></html>\n```"),
        GeneratedFile(path="styles.css", content="```css\nbody{margin:0}\n```")]))
    assert "```" not in project.files["index.html"] and project.files["styles.css"] == "body{margin:0}\n"


def test_sanitize_result_requires_index_and_content():
    with pytest.raises(CodeValidationError, match="index.html"):
        cv.sanitize_result(result(**{"styles.css": "a{}"}))
    with pytest.raises(CodeValidationError, match="empty"):
        cv.sanitize_result(result(**{"index.html": "   "}))


def test_sanitize_result_rejects_unsafe_path_and_oversize():
    with pytest.raises(CodeValidationError):
        cv.sanitize_result(result(**{"index.html": "<p>x</p>", "../x.js": "1"}))
    with pytest.raises(CodeValidationError):
        cv.validate_files({"index.html": "x" * 400_001})
    with pytest.raises(CodeValidationError, match="too large"):
        cv.validate_files({f"f{i}.js": "x" * 300_000 for i in range(4)})


def test_validate_files_rejects_case_insensitive_duplicates():
    with pytest.raises(CodeValidationError, match="Duplicate"):
        cv.validate_files({"a.js": "1", "A.js": "2"})
