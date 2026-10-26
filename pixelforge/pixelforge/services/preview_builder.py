"""Build an isolated preview document for untrusted generated HTML.

Isolation layers (outermost first):
1. ``<iframe sandbox="allow-scripts">``: no ``allow-same-origin`` (opaque origin, so
   no access to Streamlit's DOM, cookies or storage), no top navigation, popups,
   forms, downloads or modals.
2. A Content-Security-Policy ``<meta>`` injected before any generated markup that
   blocks all network access (``connect-src 'none'``, ``default-src 'none'``) and
   only allows inline CSS/JS plus ``data:`` images/fonts/media.
"""

from __future__ import annotations

import html
import re

CSP = (
    "default-src 'none'; img-src data:; media-src data:; font-src data:; "
    "style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; "
    "form-action 'none'; base-uri 'none'; frame-src 'none'; object-src 'none'"
)
IFRAME_SANDBOX = "allow-scripts"
DEFAULT_HEIGHT = 720

_LINK_RE = re.compile(r"<link\b[^>]*>", re.I)
_SCRIPT_SRC_RE = re.compile(r"""<script\b([^>]*?)\bsrc\s*=\s*(?:"([^"]*)"|'([^']*)')([^>]*)>\s*</script\s*>""", re.I)
_HREF_RE = re.compile(r"""\bhref\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
_DOCTYPE_RE = re.compile(r"^\s*<!doctype[^>]*>", re.I)


def _norm(ref: str) -> str:
    ref = ref.strip().split("#")[0].split("?")[0]
    return ref[2:] if ref.startswith("./") else ref


def inline_assets(files: dict[str, str], entry: str = "index.html") -> str:
    """Inline project-local stylesheets/scripts into the entry HTML document."""
    page = files.get(entry, "")

    def _link(match: re.Match[str]) -> str:
        tag = match.group(0)
        href = _HREF_RE.search(tag)
        if "stylesheet" not in tag.lower() or not href:
            return tag
        css = files.get(_norm(href.group(1) or href.group(2) or ""))
        if css is None:
            return ""
        return f"<style>\n{re.sub(r'</style', '<\\\\/style', css, flags=re.I)}\n</style>"

    def _script(match: re.Match[str]) -> str:
        js = files.get(_norm(match.group(2) or match.group(3) or ""))
        if js is None:
            return ""
        attrs = f"{match.group(1)} {match.group(4)}".strip()
        safe_js = re.sub(r"</script", r"<\\/script", js, flags=re.I)
        return f"<script {attrs}>\n{safe_js}\n</script>" if attrs else f"<script>\n{safe_js}\n</script>"

    page = _LINK_RE.sub(_link, page)
    return _SCRIPT_SRC_RE.sub(_script, page)


def build_preview_document(files: dict[str, str]) -> str:
    """Return a complete HTML document with the CSP placed before all generated markup."""
    body = _DOCTYPE_RE.sub("", inline_assets(files), count=1).lstrip()
    csp_meta = f'<meta http-equiv="Content-Security-Policy" content="{html.escape(CSP, quote=True)}">'
    return f"<!DOCTYPE html>\n{csp_meta}\n{body}"


_FIT_SCRIPT = (
    "<script>(function(){var W=__W__,H=__H__,f=document.getElementById('f'),h=document.getElementById('holder'),"
    "st=document.getElementById('stage');function fit(){var s=Math.min(1,(st.clientWidth-2)/W);"
    "f.style.transform='scale('+s+')';f.style.height=(H/s)+'px';h.style.width=(W*s)+'px';h.style.height=H+'px';}"
    "window.addEventListener('resize',fit);fit();})();</script>"
)


def build_sandboxed_iframe(files: dict[str, str], width: int = 1440, height: int = DEFAULT_HEIGHT) -> str:
    """HTML snippet embedding the preview in a sandboxed ``srcdoc`` iframe.

    The frame is laid out at the real viewport ``width`` (so media queries match the chosen
    viewport) and scaled down with CSS to fit the available space. The wrapper script only
    uses integers we control; generated content lives solely inside the escaped ``srcdoc``.
    """
    srcdoc = html.escape(build_preview_document(files), quote=True)
    width, height = int(width), int(height)
    script = _FIT_SCRIPT.replace("__W__", str(width)).replace("__H__", str(height))
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<style>html,body{margin:0;background:#0b0e14;}"
        "#holder{margin:0 auto;overflow:hidden;border:1px solid #2a3142;border-radius:8px;background:#fff;}"
        f"#f{{width:{width}px;border:0;display:block;transform-origin:0 0;background:#fff;}}</style></head><body>"
        f'<div id="stage"><div id="holder"><iframe id="f" title="Generated page preview" sandbox="{IFRAME_SANDBOX}" '
        f'referrerpolicy="no-referrer" srcdoc="{srcdoc}"></iframe></div></div>{script}</body></html>'
    )
