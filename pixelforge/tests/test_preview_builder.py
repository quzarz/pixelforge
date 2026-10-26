import re
from html.parser import HTMLParser

from pixelforge.services import preview_builder as pb


class _Collect(HTMLParser):
    def __init__(self):
        super().__init__()
        self.iframes: list[dict] = []

    def handle_starttag(self, tag, attrs):
        if tag == "iframe":
            self.iframes.append(dict(attrs))


def _parse(snippet: str) -> list[dict]:
    parser = _Collect()
    parser.feed(snippet)
    return parser.iframes


FILES = {
    "index.html": '<!DOCTYPE html><html><head><link rel="stylesheet" href="styles.css"></head><body><p>x</p><script src="script.js"></script></body></html>',
    "styles.css": "p{color:red}",
    "script.js": "document.title='t'",
}


def test_assets_are_inlined():
    doc = pb.inline_assets(FILES)
    assert "<style>" in doc and "p{color:red}" in doc and "document.title='t'" in doc
    assert 'href="styles.css"' not in doc and 'src="script.js"' not in doc


def test_missing_assets_are_dropped_and_closing_tags_escaped():
    files = {"index.html": '<link rel="stylesheet" href="nope.css"><script src="nope.js"></script><script src="a.js"></script>',
             "a.js": "var s='</script><img src=x onerror=alert(1)>'"}
    doc = pb.inline_assets(files)
    assert "nope" not in doc and doc.lower().count("</script>") == 1


def test_csp_precedes_generated_markup_and_blocks_network():
    doc = pb.build_preview_document({"index.html": "<!DOCTYPE html><html><body><script>1</script></body></html>"})
    assert doc.index("Content-Security-Policy") < doc.index("<script>")
    assert doc.count("<!DOCTYPE") == 1
    for directive in ("default-src 'none'", "connect-src 'none'", "form-action 'none'", "frame-src 'none'", "base-uri 'none'", "object-src 'none'"):
        assert directive in pb.CSP
    assert "http" not in pb.CSP and "*" not in pb.CSP


def test_iframe_is_sandboxed_without_same_origin():
    frames = _parse(pb.build_sandboxed_iframe(FILES))
    assert len(frames) == 1
    sandbox = frames[0]["sandbox"].split()
    assert sandbox == ["allow-scripts"]
    for forbidden in ("allow-same-origin", "allow-top-navigation", "allow-popups", "allow-forms", "allow-modals", "allow-downloads"):
        assert forbidden not in sandbox


def test_srcdoc_cannot_break_out_of_attribute():
    evil = '"><iframe sandbox="allow-same-origin allow-scripts" src="javascript:alert(1)"></iframe><x y="'
    files = {"index.html": f"<html><body>{evil}</body></html>"}
    snippet = pb.build_sandboxed_iframe(files)
    frames = _parse(snippet)
    assert len(frames) == 1 and frames[0]["sandbox"] == "allow-scripts"
    assert evil in frames[0]["srcdoc"]  # preserved as data, not interpreted


def test_viewport_width_applied():
    assert "width:390px" in pb.build_sandboxed_iframe(FILES, width=390)
    assert "width:1440px" in pb.build_sandboxed_iframe(FILES)


def test_srcdoc_roundtrip():
    frames = _parse(pb.build_sandboxed_iframe(FILES))
    assert re.search(r"<p>x</p>", frames[0]["srcdoc"])
