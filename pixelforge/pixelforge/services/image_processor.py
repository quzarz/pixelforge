"""Validate and preprocess uploaded screenshots (no network, no side effects)."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from pixelforge.config import Settings
from pixelforge.utils.errors import ImageValidationError

ALLOWED_FORMATS: dict[str, str] = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
PNG_MAX_BYTES = 4 * 1024 * 1024  # above this, re-encode as JPEG to save tokens/cost
JPEG_QUALITY = 88


@dataclass(frozen=True)
class ImageInfo:
    """Facts about an uploaded image, read without decoding all pixels."""

    width: int
    height: int
    format: str
    size_bytes: int


@dataclass(frozen=True)
class ProcessedImage:
    """Re-encoded, metadata-free image ready to send to the model."""

    data: bytes
    mime: str
    width: int
    height: int
    original_width: int
    original_height: int

    @property
    def data_url(self) -> str:
        """``data:`` URL for the vision API."""
        return f"data:{self.mime};base64,{base64.b64encode(self.data).decode('ascii')}"

    @property
    def was_resized(self) -> bool:
        return (self.width, self.height) != (self.original_width, self.original_height)


def inspect_image(data: bytes, settings: Settings) -> ImageInfo:
    """Validate type, size and dimensions; raise ``ImageValidationError`` otherwise."""
    if not data:
        raise ImageValidationError("The file is empty.", hint="Choose a PNG, JPG or WebP screenshot.")
    if len(data) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes // (1024 * 1024)
        raise ImageValidationError(
            f"The file is {len(data) / 1024 / 1024:.1f} MB; the limit is {limit_mb} MB.",
            hint="Crop or export a smaller screenshot (or raise PIXELFORGE_MAX_UPLOAD_MB).",
        )
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt, (width, height) = img.format or "", img.size
            if fmt not in ALLOWED_FORMATS:
                raise ImageValidationError(
                    f"Unsupported image format: {fmt or 'unknown'}.",
                    hint="Upload a PNG, JPG/JPEG or WebP file.",
                )
            _check_dimensions(width, height, settings)
            img.verify()
    except ImageValidationError:
        raise
    except Image.DecompressionBombError:
        raise ImageValidationError(
            "The image has too many pixels.", hint="Downscale the screenshot and try again."
        ) from None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise ImageValidationError(
            "The file is not a valid image or is corrupted.",
            hint="Re-export the screenshot as PNG, JPG or WebP.",
        ) from None
    return ImageInfo(width=width, height=height, format=fmt, size_bytes=len(data))


def _check_dimensions(width: int, height: int, s: Settings) -> None:
    if min(width, height) < s.min_dimension:
        raise ImageValidationError(
            f"The image is too small ({width}×{height}px).",
            hint=f"Both sides must be at least {s.min_dimension}px.",
        )
    if max(width, height) > s.max_dimension or width * height > s.max_pixels:
        raise ImageValidationError(
            f"The image is too large ({width}×{height}px).",
            hint=f"Max {s.max_dimension}px per side and {s.max_pixels:,} total pixels.",
        )


def preprocess_image(data: bytes, settings: Settings) -> ProcessedImage:
    """Validate, normalise orientation/colour, downscale and re-encode an image."""
    inspect_image(data, settings)
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()  # surfaces truncated files
            img = ImageOps.exif_transpose(img)
            img = _flatten_to_rgb(img)
    except (OSError, SyntaxError, ValueError):
        raise ImageValidationError(
            "The image data is truncated or corrupted.", hint="Re-export the screenshot."
        ) from None

    original_w, original_h = img.size
    if max(img.size) > settings.max_send_side:
        img.thumbnail((settings.max_send_side, settings.max_send_side), Image.Resampling.LANCZOS)

    payload, mime = _encode(img)
    return ProcessedImage(
        data=payload,
        mime=mime,
        width=img.width,
        height=img.height,
        original_width=original_w,
        original_height=original_h,
    )


def _flatten_to_rgb(img: Image.Image) -> Image.Image:
    """Composite transparency onto white and convert to RGB."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")


def _encode(img: Image.Image) -> tuple[bytes, str]:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    if buffer.tell() <= PNG_MAX_BYTES:
        return buffer.getvalue(), "image/png"
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue(), "image/jpeg"
