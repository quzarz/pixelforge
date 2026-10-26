import io

import pytest
from PIL import Image

from pixelforge.config import Settings
from pixelforge.services import image_processor as ip
from pixelforge.utils.errors import ImageValidationError


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_supported_formats(make_image, settings, fmt):
    info = ip.inspect_image(make_image(fmt), settings)
    assert info.format == fmt and (info.width, info.height) == (400, 300)


@pytest.mark.parametrize("fmt", ["GIF", "BMP", "TIFF"])
def test_unsupported_formats_rejected(make_image, settings, fmt):
    with pytest.raises(ImageValidationError, match="Unsupported"):
        ip.inspect_image(make_image(fmt), settings)


def test_empty_and_malformed_inputs(settings):
    for data in (b"", b"not an image", b"<svg xmlns='http://www.w3.org/2000/svg'/>", b"\x89PNG\r\n\x1a\n" + b"0" * 20):
        with pytest.raises(ImageValidationError):
            ip.inspect_image(data, settings)


def test_truncated_image_is_rejected_during_preprocess(make_image, settings):
    data = make_image("PNG", (300, 300))
    with pytest.raises(ImageValidationError):
        ip.preprocess_image(data[: len(data) // 2], settings)


def test_oversized_file_rejected(make_image):
    small = Settings(max_upload_bytes=1000)
    noisy = io.BytesIO()
    Image.effect_noise((300, 300), 80).convert("RGB").save(noisy, "PNG")
    with pytest.raises(ImageValidationError, match="limit"):
        ip.inspect_image(noisy.getvalue(), small)


def test_dimension_limits(make_image, settings):
    with pytest.raises(ImageValidationError, match="too small"):
        ip.inspect_image(make_image(size=(20, 500)), settings)
    with pytest.raises(ImageValidationError, match="too large"):
        ip.inspect_image(make_image(size=(900, 900)), Settings(max_pixels=100_000))
    with pytest.raises(ImageValidationError, match="too large"):
        ip.inspect_image(make_image(size=(3000, 100)), Settings(max_dimension=2000))


def test_large_image_is_downscaled(make_image):
    out = ip.preprocess_image(make_image(size=(3000, 1500)), Settings(max_send_side=1000))
    assert (out.width, out.height) == (1000, 500) and out.was_resized
    assert (out.original_width, out.original_height) == (3000, 1500)


def test_alpha_is_flattened_to_white(make_image, settings):
    out = ip.preprocess_image(make_image("PNG", mode="RGBA", color=(0, 0, 0, 0)), settings)
    img = Image.open(io.BytesIO(out.data))
    assert img.mode == "RGB" and img.getpixel((5, 5)) == (255, 255, 255)


def test_exif_orientation_applied(settings):
    img = Image.new("RGB", (300, 100), "red")
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° CW
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    out = ip.preprocess_image(buf.getvalue(), settings)
    assert (out.width, out.height) == (100, 300)


def test_output_has_no_metadata_and_data_url(make_image, settings):
    out = ip.preprocess_image(make_image("JPEG"), settings)
    assert out.data_url.startswith("data:image/png;base64,")
    assert not Image.open(io.BytesIO(out.data)).info.get("exif")


def test_large_png_falls_back_to_jpeg(make_image, settings, monkeypatch):
    monkeypatch.setattr(ip, "PNG_MAX_BYTES", 10)
    assert ip.preprocess_image(make_image(), settings).mime == "image/jpeg"
