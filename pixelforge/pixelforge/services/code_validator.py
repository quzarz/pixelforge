"""Validate and sanitise model-generated files.

Generated code is untrusted. This module (1) enforces safe file paths and size
limits, (2) strips Markdown fences, and (3) removes constructs that load remote
resources or enable navigation/embedding. It is defence in depth only: the real
isolation boundary is the sandboxed iframe + CSP built in ``preview_builder``.
"""

from __future__ import annotations

import re

from pixelforge.schemas import MAX_FILE_CHARS, GenerationResult, Project
from pixelforge.utils.errors import CodeValidationError

ALLOWED_EXTENSIONS = (".html", ".css", ".js")
MAX_TOTAL_CHARS = 1_000_000
MAX_PATH_DEPTH = 3
_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
_FENCE_RE = re.compile(r"^\s*```[A-Za-z0-9_+-]*[ \t]*\n(.*?)\n?```\s*$", re.S)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# --- HTML patterns -----------------------------------------------------------
_ATTRS = r"""(?:[^>"']|"[^"]*"|'[^']*')*"""
_SCRIPT_RE = re.compile(rf"<script\b({_ATTRS})>(.*?)</script\s*>", re.I | re.S)
_BLOCK_RE = re.compile(r"<(iframe|object|applet|frameset|noembed)\b[^>]*>.*?</\1\s*>", re.I | re.S)
_STRAY_RE = re.compile(rf"</?(?:iframe|object|applet|frameset|noembed|embed|frame|base|param)\b{_ATTRS}>", re.I)
_META_RE = re.compile(rf"<meta\b({_ATTRS})>", re.I)
_TAG_RE = re.compile(rf"<(link|img|source|video|audio|track|input|image|use|a|area|form)\b({_ATTRS})(/?)>", re.I)
_STYLE_BLOCK_RE = re.compile(r"(<style\b[^>]*>)(.*?)(</style\s*>)", re.I | re.S)
_STYLE_ATTR_RE = re.compile(r"""(\sstyle\s*=\s*)("([^"]*)"|'([^']*)')""", re.I)
_ATTR_RE = re.compile(r"""([^\s"'<>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?""")
_RESOURCE_ATTRS = ("src", "srcset", "poster", "data-src")
_BAD_SCHEMES = ("javascript:", "vbscript:", "data:text/html")

# --- CSS patterns ------------------------------------------------------------
_IMPORT_RE = re.compile(r"@import\b[^;]*;?", re.I)
_URL_RE = re.compile(r"""url\(\s*(['"]?)(.*?)\1\s*\)""", re.I | re.S)
_EMPTY_URL = 'url("data:,")'

# --- JS review hints ---------------------------------------------------------
_JS_RISKS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("eval()", re.compile(r"\beval\s*\(")),
    ("new Function()", re.compile(r"\bnew\s+Function\s*\(")),
    ("network access (fetch/XMLHttpRequest/WebSocket)", re.compile(r"\b(fetch\s*\(|XMLHttpRequest|WebSocket)")),
    ("cookie/storage access", re.compile(r"\b(document\.cookie|localStorage|sessionStorage)")),
    ("window.top/parent access", re.compile(r"\bwindow\.(top|parent)\b|\bparent\.|\btop\.location")),
    ("dynamic import()", re.compile(r"\bimport\s*\(")),
)


# --- paths & text ------------------------------------------------------------
def validate_path(path: str) -> str:
    """Return a normalised safe relative path or raise ``CodeValidationError``."""
    raw = (path or "").strip()
    if not raw or len(raw) > 100:
        raise CodeValidationError("A generated file has an empty or overly long name.")
    if _CONTROL_RE.search(raw) or "\\" in raw or raw.startswith(("/", "~")) or re.match(r"^[A-Za-z]:", raw):
        raise CodeValidationError(f"Unsafe file path rejected: {raw[:60]!r}.")
    raw = raw[2:] if raw.startswith("./") else raw
    segments = raw.split("/")
    if len(segments) > MAX_PATH_DEPTH:
        raise CodeValidationError(f"File path is nested too deeply: {raw[:60]!r}.")
    for segment in segments:
        if segment in ("", ".", "..") or not _SEGMENT_RE.match(segment):
            raise CodeValidationError(f"Unsafe file path rejected: {raw[:60]!r}.")
        if segment.split(".")[0].lower() in _WINDOWS_RESERVED or segment.endswith("."):
            raise CodeValidationError(f"Reserved file name rejected: {raw[:60]!r}.")
    if not raw.lower().endswith(ALLOWED_EXTENSIONS):
        raise CodeValidationError(
            f"File type not allowed: {raw[:60]!r}.", hint=f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}."
        )
    return raw


def strip_code_fences(text: str) -> str:
    """Remove a wrapping Markdown code fence, if present."""
    match = _FENCE_RE.match(text)
    return match.group(1) if match else text


def normalize_text(text: str) -> str:
    """Normalise newlines and drop control characters (keeps tabs/newlines)."""
    return _CONTROL_RE.sub("", text.replace("\r\n", "\n").replace("\r", "\n")).strip("\n") + "\n"


# --- attribute helpers -------------------------------------------------------
def _get_attr(attrs: str, name: str) -> str | None:
    for match in _ATTR_RE.finditer(attrs):
        if match.group(1).lower() == name:
            return next((g for g in match.groups()[1:] if g is not None), "")
    return None


def _remove_attr(attrs: str, name: str) -> str:
    pattern = rf"""\s+{re.escape(name)}(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?(?=[\s/>]|$)"""
    return re.sub(pattern, "", attrs, flags=re.I)


def _set_attr(attrs: str, name: str, value: str) -> str:
    return _remove_attr(attrs, name) + f' {name}="{value}"'


def _local_ref(ref: str, local_paths: set[str]) -> str | None:
    """Return the project path ``ref`` points to, or ``None`` if not a project file."""
    cleaned = ref.strip().split("#")[0].split("?")[0]
    cleaned = cleaned[2:] if cleaned.startswith("./") else cleaned
    return cleaned if cleaned in local_paths else None


def _is_inert_resource(value: str) -> bool:
    v = value.strip().lower()
    return not v or v.startswith(("data:image/", "data:font/", "data:audio/", "data:video/", "data:application/font", "#"))


# --- sanitisers --------------------------------------------------------------
def sanitize_css(css: str) -> tuple[str, list[str]]:
    """Drop ``@import`` and replace non-``data:`` ``url()`` references."""
    warnings: list[str] = []
    if _IMPORT_RE.search(css):
        warnings.append("Removed CSS @import (external/extra stylesheets are not allowed).")
        css = _IMPORT_RE.sub("", css)

    def _url(match: re.Match[str]) -> str:
        target = match.group(2).strip()
        if _is_inert_resource(target):
            return match.group(0)
        warnings.append("Replaced a CSS url() pointing outside the project with an empty image.")
        return _EMPTY_URL

    return _URL_RE.sub(_url, css), warnings


def sanitize_html(html: str, local_paths: set[str] | None = None) -> tuple[str, list[str]]:
    """Remove embeds, remote resources, refresh/base tags and ``javascript:`` URLs."""
    local = local_paths or set()
    warnings: list[str] = []

    def _script(match: re.Match[str]) -> str:
        src = _get_attr(match.group(1), "src")
        if src is None or _local_ref(src, local):
            return match.group(0)
        warnings.append("Removed a <script> that loads an external file.")
        return ""

    def _tag(match: re.Match[str]) -> str:
        tag, attrs, slash = match.group(1).lower(), match.group(2), match.group(3)
        if tag == "link":
            href = _get_attr(attrs, "href") or ""
            if _local_ref(href, local) or href.lower().startswith("data:image/") or href.startswith("#"):
                return match.group(0)
            warnings.append("Removed a <link> that references an external resource.")
            return ""
        if tag in ("a", "area"):
            href = _get_attr(attrs, "href")
            if href is not None and href.strip().lower().startswith(_BAD_SCHEMES):
                warnings.append("Neutralised a javascript:/data: link.")
                attrs = _set_attr(attrs, "href", "#")
        elif tag == "form":
            if (_get_attr(attrs, "action") or "").strip() not in ("", "#"):
                warnings.append("Removed a form action (forms cannot submit in previews).")
            attrs = _set_attr(_remove_attr(attrs, "action"), "action", "#")
        else:
            for name in _RESOURCE_ATTRS:
                value = _get_attr(attrs, name)
                if value is not None and not _is_inert_resource(value):
                    warnings.append("Removed an external/unavailable media reference (use data: URIs or CSS/SVG).")
                    attrs = _remove_attr(attrs, name)
        return f"<{match.group(1)}{attrs}{slash}>"

    def _meta(match: re.Match[str]) -> str:
        equiv = (_get_attr(match.group(1), "http-equiv") or "").lower()
        if equiv in ("refresh", "set-cookie", "content-security-policy"):
            warnings.append(f"Removed <meta http-equiv={equiv!r}>.")
            return ""
        return match.group(0)

    def _style_block(match: re.Match[str]) -> str:
        css, css_warnings = sanitize_css(match.group(2))
        warnings.extend(css_warnings)
        return f"{match.group(1)}{css}{match.group(3)}"

    def _style_attr(match: re.Match[str]) -> str:
        quote = match.group(2)[0]
        css, css_warnings = sanitize_css(match.group(3) if match.group(3) is not None else match.group(4))
        warnings.extend(css_warnings)
        return f"{match.group(1)}{quote}{css}{quote}"

    if _BLOCK_RE.search(html) or _STRAY_RE.search(html):
        warnings.append("Removed embedding/base elements (iframe, object, embed, base, ...).")
    html = _BLOCK_RE.sub("", html)
    html = _STRAY_RE.sub("", html)
    html = _SCRIPT_RE.sub(_script, html)
    html = _META_RE.sub(_meta, html)
    html = _TAG_RE.sub(_tag, html)
    html = _STYLE_BLOCK_RE.sub(_style_block, html)
    html = _STYLE_ATTR_RE.sub(_style_attr, html)
    return _ensure_document_shell(html), list(dict.fromkeys(warnings))


def _ensure_document_shell(html: str) -> str:
    """Guarantee a doctype and a responsive viewport meta tag."""
    if not re.match(r"\s*<!doctype", html, re.I):
        html = "<!DOCTYPE html>\n" + html.lstrip()
    if not re.search(r"<meta[^>]+name=[\"']viewport[\"']", html, re.I):
        html = re.sub(
            r"(<head\b[^>]*>)",
            r'\1\n<meta name="viewport" content="width=device-width, initial-scale=1">',
            html,
            count=1,
            flags=re.I,
        )
    return html


def scan_js(js: str) -> list[str]:
    """Return review warnings for risky JavaScript constructs (code is not modified)."""
    return [f"JavaScript uses {label}; review before deploying." for label, rx in _JS_RISKS if rx.search(js)]


# --- orchestration -----------------------------------------------------------
def validate_files(files: dict[str, str]) -> None:
    """Check paths and size limits of an (edited) file mapping; raise on violation."""
    total = 0
    seen: set[str] = set()
    for path, content in files.items():
        validate_path(path)
        if path.lower() in seen:
            raise CodeValidationError(f"Duplicate file name: {path}.")
        seen.add(path.lower())
        if len(content) > MAX_FILE_CHARS:
            raise CodeValidationError(f"{path} is too large ({len(content):,} characters).")
        total += len(content)
    if total > MAX_TOTAL_CHARS:
        raise CodeValidationError("The generated project is too large.", hint="Try Fast fidelity or a simpler screenshot.")


def sanitize_result(result: GenerationResult) -> Project:
    """Turn a raw model result into a validated, sanitised ``Project``."""
    cleaned: dict[str, str] = {}
    for generated in result.files:
        path = validate_path(generated.path)
        content = normalize_text(strip_code_fences(generated.content))
        if not content.strip():
            raise CodeValidationError(f"{path} is empty.")
        cleaned[path] = content
    validate_files(cleaned)
    if "index.html" not in cleaned:
        raise CodeValidationError("The response did not include an index.html file.")

    warnings: list[str] = []
    local = set(cleaned)
    for path, content in list(cleaned.items()):
        lower = path.lower()
        if lower.endswith(".html"):
            cleaned[path], found = sanitize_html(content, local)
        elif lower.endswith(".css"):
            cleaned[path], found = sanitize_css(content)
        else:
            found = scan_js(content)
        warnings.extend(f"{path}: {w}" for w in found)
    return Project(title=result.title.strip() or "Generated page", files=cleaned, notes=result.notes.strip(), warnings=warnings)
