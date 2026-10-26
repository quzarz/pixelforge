"""Workspace state kept in ``st.session_state`` (per user session, never cached globally)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from pixelforge.config import Settings
from pixelforge.schemas import Project
from pixelforge.services.demo import DEMO_NAME, demo_project, demo_screenshot_png
from pixelforge.services.image_processor import ImageInfo, ProcessedImage, inspect_image, preprocess_image

SOURCE_AI = "ai"
SOURCE_DEMO = "demo"


@dataclass
class Workspace:
    """Everything the UI needs to survive Streamlit reruns."""

    image: ProcessedImage | None = None
    image_info: ImageInfo | None = None
    image_name: str = ""
    image_hash: str = ""
    project: Project | None = None
    project_source: str | None = None
    model_used: str = ""
    revision: int = 0  # bumps editor widget keys so regeneration replaces edited text
    uploader_nonce: int = 0  # bumps the uploader key so "Clear" empties the dropzone
    error: str | None = None
    flash: str | None = None
    session_api_key: str = ""  # kept in memory for this session only

    def set_image(self, raw: bytes, name: str, settings: Settings) -> None:
        """Validate and store a new image; clears any previous result. May raise ImageValidationError."""
        info = inspect_image(raw, settings)
        processed = preprocess_image(raw, settings)
        self.image, self.image_info, self.image_name = processed, info, name
        self.image_hash = hashlib.sha256(raw).hexdigest()
        self.project, self.project_source, self.error = None, None, None

    def set_project(self, project: Project, source: str, model: str = "") -> None:
        """Store a generated project and invalidate old editor widgets."""
        self.project, self.project_source, self.model_used = project, source, model
        self.revision += 1
        self.error = None

    def load_demo(self, settings: Settings) -> None:
        """Load the offline sample screenshot and its canned output (no API call)."""
        self.set_image(demo_screenshot_png(), DEMO_NAME, settings)
        self.set_project(demo_project(), SOURCE_DEMO)
        self.uploader_nonce += 1  # empty the dropzone so an old upload cannot override the demo

    def reset(self) -> None:
        """Clear image, results and messages (keeps the session API key)."""
        key, nonce, revision = self.session_api_key, self.uploader_nonce + 1, self.revision + 1
        self.__dict__.update(Workspace().__dict__)
        self.session_api_key, self.uploader_nonce, self.revision = key, nonce, revision


def get_workspace() -> Workspace:
    """Return this session's workspace, creating it on first use."""
    import streamlit as st

    if "workspace" not in st.session_state:
        st.session_state["workspace"] = Workspace()
    return st.session_state["workspace"]
