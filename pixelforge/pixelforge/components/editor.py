"""Editable code panels with a copy-friendly highlighted view."""

from __future__ import annotations

import streamlit as st

from pixelforge.schemas import MAX_FILE_CHARS
from pixelforge.state import Workspace

_LANGUAGES = {".html": "html", ".css": "css", ".js": "javascript"}


def _language(path: str) -> str:
    return _LANGUAGES.get(path[path.rfind(".") :].lower(), "text")


def render_file_editor(ws: Workspace, path: str) -> None:
    """Editable text area for one file; edits are written back to the workspace."""
    assert ws.project is not None
    current = ws.project.files[path]
    edited = st.text_area(
        path,
        value=current,
        height=460,
        max_chars=MAX_FILE_CHARS,
        key=f"edit-{ws.revision}-{path}",
        label_visibility="collapsed",
    )
    ws.project.files[path] = edited
    st.caption(f"{len(edited.splitlines())} lines · {len(edited.encode('utf-8')) / 1024:.1f} KB · edits update the preview and export")
    with st.expander("Highlighted view (use the copy icon to copy)"):
        st.code(edited, language=_language(path), line_numbers=True, wrap_lines=True)


def render_code_tab(ws: Workspace, extension: str, empty_hint: str) -> None:
    """Render all project files with ``extension`` (one editor each)."""
    assert ws.project is not None
    paths = sorted(p for p in ws.project.files if p.lower().endswith(extension))
    if not paths:
        st.info(empty_hint)
        return
    for path in paths:
        if len(paths) > 1:
            st.markdown(f"**{path}**")
        render_file_editor(ws, path)
