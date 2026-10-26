"""Pydantic models and enums shared across the app."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_FILES = 12
MAX_FILE_CHARS = 400_000
MAX_INSTRUCTIONS_CHARS = 1000


class Framework(str, Enum):
    """Supported output frameworks. React is on the roadmap, not offered in the UI."""

    HTML_CSS_JS = "html"

    @property
    def label(self) -> str:
        return "HTML / CSS / JavaScript"


class Viewport(str, Enum):
    """Viewport the screenshot was captured at."""

    DESKTOP = "desktop"
    TABLET = "tablet"
    MOBILE = "mobile"

    @property
    def width(self) -> int:
        return {"desktop": 1440, "tablet": 768, "mobile": 390}[self.value]

    @property
    def label(self) -> str:
        return f"{self.value.title()} ({self.width}px)"


class Fidelity(str, Enum):
    """How much effort to spend matching fine visual detail."""

    FAST = "Fast"
    BALANCED = "Balanced"
    HIGH = "High detail"


class GenerationOptions(BaseModel):
    """User-selected generation settings."""

    framework: Framework = Framework.HTML_CSS_JS
    viewport: Viewport = Viewport.DESKTOP
    fidelity: Fidelity = Fidelity.BALANCED
    instructions: str = Field(default="", max_length=MAX_INSTRUCTIONS_CHARS)

    @field_validator("instructions")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class GeneratedFile(BaseModel):
    """One file returned by the model."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(min_length=1, max_length=120)
    content: str = Field(max_length=MAX_FILE_CHARS * 2)


class GenerationResult(BaseModel):
    """Structured model response (before sanitisation)."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(default="Generated page", max_length=120)
    files: list[GeneratedFile] = Field(min_length=1, max_length=MAX_FILES)
    notes: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def _unique_paths(self) -> GenerationResult:
        paths = [f.path.lower() for f in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("duplicate file paths in response")
        return self


class Project(BaseModel):
    """Sanitised, editable project held in the workspace."""

    title: str = "Generated page"
    files: dict[str, str]
    notes: str = ""
    warnings: list[str] = Field(default_factory=list)
