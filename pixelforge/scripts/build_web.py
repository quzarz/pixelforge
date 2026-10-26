#!/usr/bin/env python3
"""Build the standalone browser app as a single HTML file."""

from __future__ import annotations

import argparse
import base64
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLESHEET_RE = re.compile(r"<link\b[^>]*\bhref=[\"']styles\.css[\"'][^>]*>", re.I)
SCRIPT_RE = re.compile(r"<script\b[^>]*\bsrc=[\"']app\.js[\"'][^>]*>\s*</script\s*>", re.I)
PREVIEW_RE = re.compile(r"(\bsrc=[\"'])preview\.html([\"'])", re.I)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"Missing required file: {path}") from None


def build(root: Path = ROOT) -> str:
    html = read_text(root / "index.html")
    css = read_text(root / "styles.css")
    js = read_text(root / "app.js")
    preview = read_text(root / "preview.html")

    preview_url = "data:text/html;charset=utf-8;base64," + base64.b64encode(
        preview.encode("utf-8")
    ).decode("ascii")

    if not STYLESHEET_RE.search(html):
        raise SystemExit("index.html does not reference styles.css")
    if not SCRIPT_RE.search(html):
        raise SystemExit("index.html does not reference app.js")
    if not PREVIEW_RE.search(html):
        raise SystemExit("index.html does not reference preview.html")

    css = css.replace("</style", r"<\/style")
    js = js.replace("</script", r"<\/script")

    html = STYLESHEET_RE.sub(lambda _: f"<style>\n{css}\n</style>", html, count=1)
    html = SCRIPT_RE.sub(lambda _: f"<script>\n{js}\n</script>", html, count=1)
    html = PREVIEW_RE.sub(lambda match: f"{match.group(1)}{preview_url}{match.group(2)}", html, count=1)

    return html


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "pixelforge.html",
        help="Output path (default: pixelforge.html in the project root).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Directory containing index.html, styles.css, app.js and preview.html.",
    )
    args = parser.parse_args()

    output = build(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    print(f"Built {args.output} ({len(output.encode('utf-8')):,} bytes)")


if __name__ == "__main__":
    main()
