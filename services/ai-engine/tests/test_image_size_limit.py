"""Oversized compressed images must be rejected before OpenCV expands them."""

import base64
import struct
import sys
from io import BytesIO
from pathlib import Path

import cv2
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as ai_app  # noqa: E402
from app import _checked_image_bytes, create_app  # noqa: E402


@pytest.fixture(params=[8000], scope="module")
def oversized_png(request):
    output = BytesIO()
    Image.new("1", (request.param, request.param)).save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def test_image_at_pixel_limit_is_accepted():
    output = BytesIO()
    Image.new("1", (4096, 4096)).save(output, format="PNG")
    image_b64 = base64.b64encode(output.getvalue()).decode("ascii")
    assert _checked_image_bytes(image_b64) == output.getvalue()


@pytest.mark.parametrize("path", [
    "/pipeline/04_features/color_palette",
    "/pipeline/02_enhancement/blur",
    "/pipeline/03_segmentation/contours",
    "/pipeline/03_segmentation/remove-background",
    "/pipeline/04_features/auto_tag",
])
def test_oversized_png_is_rejected_before_full_decode(monkeypatch, oversized_png, path):
    def decode_was_called(*args, **kwargs):
        pytest.fail("oversized image reached cv2.imdecode")

    monkeypatch.setattr(cv2, "imdecode", decode_was_called)
    client = create_app({"TESTING": True, "AI_ENGINE_KEY": "test-engine-key"}).test_client()

    response = client.post(
        path,
        json={"image": oversized_png},
        headers={"X-LUMA-Engine-Key": "test-engine-key"},
    )
    assert response.status_code == 400
    assert "16.8" in response.json["error"]


def test_phone_photo_is_accepted_by_palette_route(monkeypatch):
    output = BytesIO()
    Image.new("RGB", (4032, 3024), "red").save(output, format="JPEG")
    image_b64 = base64.b64encode(output.getvalue()).decode("ascii")
    analyzed_sizes = []
    original_extract = ai_app.extract_palette

    def record_size(pixels, colors):
        analyzed_sizes.append(pixels.shape[:2])
        return original_extract(pixels, colors=colors)

    monkeypatch.setattr(ai_app, "extract_palette", record_size)
    client = create_app({"TESTING": True, "AI_ENGINE_KEY": "test-engine-key"}).test_client()

    response = client.post(
        "/pipeline/04_features/color_palette",
        json={"image": image_b64},
        headers={"X-LUMA-Engine-Key": "test-engine-key"},
    )

    assert response.status_code == 200
    assert response.json["metrics"]["color_palette"] == ["#fe0000"]
    assert max(analyzed_sizes[0]) <= 1024


def test_malformed_dds_header_returns_400():
    header = bytearray(120)
    struct.pack_into("<3I", header, 0, 0, 1, 1)
    struct.pack_into("<2I", header, 68, 32, 0x4000)
    image_b64 = base64.b64encode(b"DDS " + struct.pack("<I", 124) + header).decode("ascii")
    client = create_app({"TESTING": True, "AI_ENGINE_KEY": "test-engine-key"}).test_client()

    response = client.post(
        "/pipeline/04_features/color_palette",
        json={"image": image_b64},
        headers={"X-LUMA-Engine-Key": "test-engine-key"},
    )

    assert response.status_code == 400
