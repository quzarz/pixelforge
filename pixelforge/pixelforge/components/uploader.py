"""Screenshot uploader with validation and info display."""

from __future__ import annotations

import hashlib

import streamlit as st

from pixelforge.config import Settings
from pixelforge.state import Workspace
from pixelforge.utils.errors import ImageValidationError

ACCEPTED_TYPES = ["png", "jpg", "jpeg", "webp"]


def render_uploader(ws: Workspace, settings: Settings) -> None:
    """Render the dropzone, ingest new uploads into ``ws`` and show image details."""
    limit_mb = settings.max_upload_bytes // (1024 * 1024)
    uploaded = st.file_uploader(
        "Upload a screenshot",
        type=ACCEPTED_TYPES,
        key=f"uploader-{ws.uploader_nonce}",
        help=f"PNG, JPG or WebP · up to {limit_mb} MB · drag and drop supported",
    )
    if uploaded is not None:
        raw = uploaded.getvalue()
        if hashlib.sha256(raw).hexdigest() != ws.image_hash:
            try:
                ws.set_image(raw, uploaded.name, settings)
            except ImageValidationError as exc:
                st.error(exc.user_message, icon="🚫")
                return
    if ws.image is None or ws.image_info is None:
        return
    info, img = ws.image_info, ws.image
    st.image(img.data, caption=ws.image_name, width="stretch")
    cols = st.columns(3)
    cols[0].metric("Dimensions", f"{info.width}×{info.height}")
    cols[1].metric("Format", info.format)
    cols[2].metric("Size", f"{info.size_bytes / 1024:.0f} KB")
    if img.was_resized:
        st.caption(f"Downscaled to {img.width}×{img.height}px before sending to the model.")
