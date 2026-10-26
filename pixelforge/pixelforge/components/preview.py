"""Sandboxed live preview."""

from __future__ import annotations

import streamlit as st

from pixelforge.schemas import Viewport
from pixelforge.services.preview_builder import DEFAULT_HEIGHT, build_sandboxed_iframe
from pixelforge.state import Workspace

SANDBOX_NOTE = (
    "Preview runs in a sandboxed iframe (`allow-scripts` only, no same-origin access, no navigation, "
    "forms or popups) with a CSP that blocks all network requests."
)


def _embed(snippet: str, height: int) -> None:
    """Embed our (already sandboxed) wrapper page. Streamlit's own iframe is same-origin, so the
    isolation comes from the nested ``sandbox`` iframe inside ``snippet``, never from this call."""
    if hasattr(st, "iframe"):  # Streamlit >= 1.5x
        st.iframe(snippet, height=height)
    else:  # pragma: no cover - older Streamlit
        import streamlit.components.v1 as components

        components.html(snippet, height=height, scrolling=False)


def render_preview(ws: Workspace, viewport: Viewport) -> None:
    """Render the current (possibly edited) project in the isolated preview."""
    assert ws.project is not None
    snippet = build_sandboxed_iframe(ws.project.files, width=viewport.width, height=DEFAULT_HEIGHT)
    _embed(snippet, DEFAULT_HEIGHT + 16)
    st.caption(f"{SANDBOX_NOTE} Rendered at {viewport.width}px wide and scaled to fit.")
